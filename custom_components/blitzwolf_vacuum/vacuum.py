"""Vacuum platform for BlitzWolf Vacuum."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION_CHARGING,
    ACTION_GOING_HOME,
    ACTION_IDLE,
    ACTION_PAUSED,
    ACTION_STUCK,
    ACTION_SWEEPING,
    DOMAIN,
    MANUFACTURER,
    SWEEP_MODE_LIST,
    SWEEP_MODE_TO_INT,
    SWEEP_MODES,
)
from .coordinator import BlitzwolfMqttCoordinator

_LOGGER = logging.getLogger(__name__)

# Map robot action codes to HA vacuum states
ACTION_TO_STATE = {
    ACTION_IDLE: "idle",
    ACTION_SWEEPING: "cleaning",
    ACTION_GOING_HOME: "returning",
    ACTION_CHARGING: "docked",
    ACTION_STUCK: "error",
    ACTION_PAUSED: "paused",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlitzWolf vacuum from a config entry."""
    coordinator: BlitzwolfMqttCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BlitzwolfVacuumEntity(coordinator, entry)])


class BlitzwolfVacuumEntity(StateVacuumEntity):
    """Representation of a BlitzWolf robot vacuum."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATE
    )
    _attr_fan_speed_list = SWEEP_MODE_LIST

    def __init__(
        self,
        coordinator: BlitzwolfMqttCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = coordinator.device_id

        info = coordinator.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=MANUFACTURER,
            model=info.get("model", "BW-VC1"),
            name=info.get("device_name", "BlitzWolf Vacuum"),
            sw_version=info.get("software_version"),
            hw_version=info.get("hardware_version"),
        )

    async def async_added_to_hass(self) -> None:
        """Register for MQTT state updates when entity is added."""
        self.async_on_remove(
            self._coordinator.add_listener(self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        """Handle data update from MQTT coordinator."""
        self.async_write_ha_state()

    @property
    def state(self) -> str:
        """Return the vacuum state."""
        data = self._coordinator.data
        if data.charging:
            return "docked"
        return ACTION_TO_STATE.get(data.action, "idle")

    @property
    def battery_level(self) -> int | None:
        return self._coordinator.data.battery

    @property
    def fan_speed(self) -> str | None:
        return SWEEP_MODES.get(self._coordinator.data.sweep_mode, "Normal")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._coordinator.data
        attrs: dict[str, Any] = {}
        if data.position_x != 0 or data.position_y != 0:
            attrs["position_x"] = round(data.position_x, 3)
            attrs["position_y"] = round(data.position_y, 3)
            attrs["yaw"] = round(data.yaw, 3)
        if data.temperature is not None:
            attrs["temperature"] = data.temperature
        if data.sweep_time:
            attrs["sweep_time_seconds"] = data.sweep_time
        if data.device_mode == 1:
            attrs["device_mode"] = "mop"
        else:
            attrs["device_mode"] = "sweep"
        if data.network_ssid:
            attrs["wifi_ssid"] = data.network_ssid
        if data.network_ip:
            attrs["wifi_ip"] = data.network_ip
        attrs["mqtt_connected"] = self._coordinator.connected
        return attrs

    @property
    def available(self) -> bool:
        return self._coordinator.connected

    async def async_start(self) -> None:
        """Start cleaning."""
        await self._coordinator.async_start()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        await self._coordinator.async_stop()

    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._coordinator.async_pause()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return to charging dock."""
        await self._coordinator.async_return_to_base()

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        speed_int = SWEEP_MODE_TO_INT.get(fan_speed, 0)
        await self._coordinator.async_set_fan_speed(speed_int)
