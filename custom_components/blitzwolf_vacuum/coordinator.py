"""MQTT coordinator for BlitzWolf Vacuum."""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any, Callable

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant, callback

from .api import SlamtecApi
from .const import (
    CMD_ACTION,
    CMD_DOCK,
    CMD_GET_BATTERY,
    CMD_GET_NETWORK,
    CMD_GET_STATUS,
    CMD_GET_SWEEP_MODE,
    CMD_SET_SWEEP_MODE,
    CMD_SPOT_CLEAN,
    CMD_START_UPDATE,
    CMD_STOP,
    CMD_STOP_UPDATE,
    MQTT_HOST,
    MQTT_PORT,
    RESP_BATTERY,
    RESP_CHARGING,
    RESP_CURRENT_ACTION,
    RESP_DC_CONNECTED,
    RESP_DOCK_POSE,
    RESP_NETWORK_INFO,
    RESP_POSE,
    RESP_SWEEP_MODE,
    RESP_SWEEP_MOP_MODE,
    RESP_SWEEP_TIME,
    RESP_SYSTEM_EVENT,
    RESP_TEMPERATURE,
    TOPIC_PUB,
    TOPIC_SUB,
    ACTION_CHARGING,
    ACTION_GOING_HOME,
    ACTION_IDLE,
    ACTION_PAUSED,
    ACTION_STUCK,
    ACTION_SWEEPING,
)

_LOGGER = logging.getLogger(__name__)

# Debounce window: collect rapid MQTT messages and notify once
_DEBOUNCE_SECONDS = 0.15
# Polling interval for non-streaming data
_POLL_INTERVAL = 30


class VacuumData:
    """Holds the current state of the vacuum."""

    def __init__(self) -> None:
        self.battery: int | None = None
        self.charging: bool = False
        self.dc_connected: bool = False
        self.temperature: float | None = None
        self.action: int = ACTION_IDLE
        self.action_name: str | None = None
        self.position_x: float = 0.0
        self.position_y: float = 0.0
        self.yaw: float = 0.0
        self.dock_x: float = 0.0
        self.dock_y: float = 0.0
        self.sweep_mode: int = 0
        self.sweep_time: int = 0
        self.device_mode: int = 0  # 0=sweep, 1=mop
        self.network_ssid: str | None = None
        self.network_ip: str | None = None


class BlitzwolfMqttCoordinator:
    """Manages the MQTT connection and data updates for the vacuum."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SlamtecApi,
        device_id: str,
        device_info: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.api = api
        self.device_id = device_id
        self.device_info = device_info
        self.data = VacuumData()
        self._client: mqtt.Client | None = None
        self._connected = False
        self._listeners: list[Callable[[], None]] = []
        self._topic_pub = TOPIC_PUB.format(device_id)
        self._topic_sub = TOPIC_SUB.format(device_id)
        self._refresh_task: asyncio.Task | None = None
        self._debounce_handle: asyncio.TimerHandle | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Add a state update listener. Returns a callable to remove it."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def _notify_listeners(self) -> None:
        """Notify all listeners of a state update (runs on HA event loop)."""
        self._debounce_handle = None
        for listener in self._listeners:
            try:
                listener()
            except Exception:
                _LOGGER.exception("Error notifying listener")

    def _schedule_notify(self) -> None:
        """Debounced notification: coalesce rapid MQTT messages into one update."""
        if self._debounce_handle is not None:
            self._debounce_handle.cancel()
        self._debounce_handle = self.hass.loop.call_later(
            _DEBOUNCE_SECONDS, self._notify_listeners
        )

    async def async_connect(self) -> None:
        """Connect to MQTT broker."""
        token = await self.api.ensure_valid_token()
        user_id = self.api.user_id
        if not user_id:
            user_id = await self.api.get_user_id()

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=token,
        )
        self._client.username_pw_set(user_id, token)
        self._client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        _LOGGER.debug("Connecting to MQTT %s:%s", MQTT_HOST, MQTT_PORT)
        # connect() is blocking (TCP handshake + TLS), needs executor
        await self.hass.async_add_executor_job(
            self._client.connect, MQTT_HOST, MQTT_PORT, 60
        )
        self._client.loop_start()

    def _on_connect(
        self, client: mqtt.Client, userdata: Any, flags: Any, rc: Any, properties: Any = None
    ) -> None:
        """Handle MQTT connection."""
        if isinstance(rc, int):
            success = rc == 0
        else:
            success = rc == mqtt.CONNACK_ACCEPTED or rc.value == 0
        if success:
            self._connected = True
            client.subscribe(self._topic_sub)
            _LOGGER.info("MQTT connected, subscribed to %s", self._topic_sub)
            # Request full data update (works both on first connect and reconnect)
            self._subscribe_realtime()
            self._query_initial_state()
        else:
            _LOGGER.error("MQTT connection failed: rc=%s", rc)

    def _subscribe_realtime(self) -> None:
        """Subscribe to real-time push updates from the robot."""
        self._send_command(CMD_START_UPDATE, {
            "pose": True,
            "currentAction": True,
            "batteryPercentage": True,
            "batteryCharging": True,
            "dcConnected": True,
            "boardTemperature": True,
            "exploreMap": False,
            "sweepMap": False,
            "virtualWall": False,
            "sweepTime": True,
            "sweepArea": True,
            "dockPose": True,
            "sweepingRegion": False,
        })

    def _query_initial_state(self) -> None:
        """Send one-shot queries for data not included in the real-time stream."""
        self._send_command(CMD_GET_BATTERY)
        self._send_command(CMD_GET_STATUS)
        self._send_command(CMD_GET_SWEEP_MODE)
        self._send_command(CMD_GET_NETWORK)

    async def async_request_full_update(self) -> None:
        """Re-subscribe to real-time data and poll non-streaming values.

        Call this AFTER entities have been set up so listeners receive the data.
        """
        if not self._connected:
            return
        # publish() with loop_start() is non-blocking, no executor needed
        self._subscribe_realtime()
        self._query_initial_state()

    async def async_start_refresh_loop(self) -> None:
        """Start a periodic loop that re-polls non-streaming data."""
        if self._refresh_task is not None:
            return
        self._refresh_task = self.hass.async_create_task(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        """Periodically poll data that doesn't arrive via real-time push."""
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)
                if self._connected:
                    self._query_initial_state()
        except asyncio.CancelledError:
            pass

    def _on_disconnect(
        self, client: mqtt.Client, userdata: Any, *args: Any
    ) -> None:
        """Handle MQTT disconnect."""
        self._connected = False
        _LOGGER.warning("MQTT disconnected, will reconnect")

    def _on_message(
        self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage
    ) -> None:
        """Handle incoming MQTT messages from the robot."""
        try:
            payload = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        func = payload.get("f")
        param = payload.get("p")

        if func == RESP_BATTERY:
            self.data.battery = param
        elif func == RESP_CHARGING:
            self.data.charging = bool(param)
        elif func == RESP_DC_CONNECTED:
            self.data.dc_connected = bool(param)
        elif func == RESP_TEMPERATURE:
            self.data.temperature = param
        elif func == RESP_POSE and isinstance(param, dict):
            self.data.position_x = param.get("x", 0.0)
            self.data.position_y = param.get("y", 0.0)
            self.data.yaw = param.get("yaw", 0.0)
        elif func == RESP_CURRENT_ACTION:
            if isinstance(param, dict):
                self.data.action = param.get("an", ACTION_IDLE)
                self.data.action_name = param.get("actionName")
            else:
                self.data.action = ACTION_IDLE
        elif func == RESP_DOCK_POSE and isinstance(param, dict):
            self.data.dock_x = param.get("x", 0.0)
            self.data.dock_y = param.get("y", 0.0)
        elif func == RESP_SWEEP_MODE:
            self.data.sweep_mode = param if isinstance(param, int) else 0
        elif func == RESP_SWEEP_TIME:
            self.data.sweep_time = param if isinstance(param, int) else 0
        elif func == RESP_SWEEP_MOP_MODE and isinstance(param, dict):
            self.data.device_mode = param.get("device_mode", 0)
        elif func == RESP_NETWORK_INFO and isinstance(param, dict):
            self.data.network_ssid = param.get("ssid")
            self.data.network_ip = param.get("ip")
        elif func == RESP_SYSTEM_EVENT:
            _LOGGER.debug("System event: %s", param)
        else:
            _LOGGER.debug("MQTT recv f=%s p=%s", func, str(param)[:200])

        # Debounced: schedule notification on HA event loop
        self.hass.loop.call_soon_threadsafe(self._schedule_notify)

    def _send_command(self, function_code: int, param: Any = None) -> None:
        """Send a command to the robot via MQTT.

        paho-mqtt publish() with loop_start() is non-blocking and thread-safe,
        so this can be called from any thread including the asyncio event loop.
        """
        if not self._client or not self._connected:
            _LOGGER.warning("Cannot send command, MQTT not connected")
            return
        msg: dict[str, Any] = {"f": function_code}
        if param is not None:
            msg["p"] = param
        self._client.publish(self._topic_pub, json.dumps(msg))
        _LOGGER.debug("MQTT send f=%s p=%s", function_code, param)

    async def async_start(self) -> None:
        """Start cleaning."""
        self._send_command(CMD_ACTION, 1)

    async def async_pause(self) -> None:
        """Pause cleaning."""
        self._send_command(CMD_ACTION, 2)

    async def async_stop(self) -> None:
        """Stop cleaning."""
        self._send_command(CMD_STOP)

    async def async_return_to_base(self) -> None:
        """Return to charging dock."""
        self._send_command(CMD_DOCK)

    async def async_set_fan_speed(self, speed_int: int) -> None:
        """Set sweep mode (0=normal, 1=silence, 2=high, 3=full)."""
        self._send_command(CMD_SET_SWEEP_MODE, speed_int)

    async def async_spot_clean(self, x: float, y: float) -> None:
        """Start spot cleaning at coordinates."""
        self._send_command(CMD_SPOT_CLEAN, {"x": x, "y": y})

    async def async_disconnect(self) -> None:
        """Disconnect from MQTT."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None
        if self._debounce_handle is not None:
            self._debounce_handle.cancel()
            self._debounce_handle = None
        if self._client:
            self._send_command(CMD_STOP_UPDATE)
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            _LOGGER.info("MQTT disconnected")

    async def async_reconnect(self) -> None:
        """Reconnect with fresh token."""
        await self.async_disconnect()
        await self.api.ensure_valid_token()
        await self.async_connect()
