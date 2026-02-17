"""Sensor platform for BlitzWolf Vacuum."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, SWEEP_MODES
from .coordinator import BlitzwolfMqttCoordinator, VacuumData

ACTION_NAMES = {
    0: "Idle",
    1: "Sweeping",
    2: "Going home",
    3: "Charging",
    4: "Exploring",
    5: "Stuck",
    6: "Paused",
}

DEVICE_MODE_NAMES = {
    0: "Sweep",
    1: "Mop",
}


@dataclass(frozen=True, kw_only=True)
class BlitzwolfSensorDescription(SensorEntityDescription):
    """Describes a BlitzWolf sensor."""

    value_fn: Callable[[VacuumData, BlitzwolfMqttCoordinator], Any]


SENSOR_DESCRIPTIONS: tuple[BlitzwolfSensorDescription, ...] = (
    BlitzwolfSensorDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d, c: d.battery,
    ),
    BlitzwolfSensorDescription(
        key="temperature",
        translation_key="board_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: d.temperature,
    ),
    BlitzwolfSensorDescription(
        key="cleaning_time",
        translation_key="cleaning_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
        value_fn=lambda d, c: d.sweep_time if d.sweep_time else None,
    ),
    BlitzwolfSensorDescription(
        key="current_action",
        translation_key="current_action",
        icon="mdi:robot-vacuum",
        value_fn=lambda d, c: ACTION_NAMES.get(d.action, f"Unknown ({d.action})"),
    ),
    BlitzwolfSensorDescription(
        key="fan_speed",
        translation_key="fan_speed",
        icon="mdi:fan",
        value_fn=lambda d, c: SWEEP_MODES.get(d.sweep_mode, "Normal"),
    ),
    BlitzwolfSensorDescription(
        key="device_mode",
        translation_key="device_mode",
        icon="mdi:swap-horizontal",
        value_fn=lambda d, c: DEVICE_MODE_NAMES.get(d.device_mode, "Sweep"),
    ),
    BlitzwolfSensorDescription(
        key="position_x",
        translation_key="position_x",
        icon="mdi:map-marker",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: round(d.position_x, 3),
    ),
    BlitzwolfSensorDescription(
        key="position_y",
        translation_key="position_y",
        icon="mdi:map-marker",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: round(d.position_y, 3),
    ),
    BlitzwolfSensorDescription(
        key="yaw",
        translation_key="yaw",
        icon="mdi:compass-outline",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: round(d.yaw, 1),
    ),
    BlitzwolfSensorDescription(
        key="dock_position_x",
        translation_key="dock_position_x",
        icon="mdi:home-map-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: round(d.dock_x, 3),
    ),
    BlitzwolfSensorDescription(
        key="dock_position_y",
        translation_key="dock_position_y",
        icon="mdi:home-map-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: round(d.dock_y, 3),
    ),
    BlitzwolfSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: d.network_ssid,
    ),
    BlitzwolfSensorDescription(
        key="wifi_ip",
        translation_key="wifi_ip",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: d.network_ip,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlitzWolf vacuum sensors."""
    coordinator: BlitzwolfMqttCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BlitzwolfSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
    )


class BlitzwolfSensor(SensorEntity):
    """A sensor entity for BlitzWolf vacuum data."""

    _attr_has_entity_name = True
    entity_description: BlitzwolfSensorDescription

    def __init__(
        self,
        coordinator: BlitzwolfMqttCoordinator,
        entry: ConfigEntry,
        description: BlitzwolfSensorDescription,
    ) -> None:
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

        info = coordinator.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=MANUFACTURER,
            model=info.get("model", "BW-VC1"),
            name=info.get("device_name", "BlitzWolf Vacuum"),
        )

    async def async_added_to_hass(self) -> None:
        """Register for MQTT state updates."""
        self.async_on_remove(
            self._coordinator.add_listener(self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        """Handle data update from MQTT coordinator."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self._coordinator.data, self._coordinator
        )

    @property
    def available(self) -> bool:
        return self._coordinator.connected
