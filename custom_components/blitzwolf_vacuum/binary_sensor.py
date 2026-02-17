"""Binary sensor platform for BlitzWolf Vacuum."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import BlitzwolfMqttCoordinator, VacuumData


@dataclass(frozen=True, kw_only=True)
class BlitzwolfBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a BlitzWolf binary sensor."""

    value_fn: Callable[[VacuumData, BlitzwolfMqttCoordinator], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[BlitzwolfBinarySensorDescription, ...] = (
    BlitzwolfBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d, c: d.charging,
    ),
    BlitzwolfBinarySensorDescription(
        key="dc_connected",
        translation_key="dc_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda d, c: d.dc_connected,
    ),
    BlitzwolfBinarySensorDescription(
        key="mqtt_connected",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: c.connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlitzWolf vacuum binary sensors."""
    coordinator: BlitzwolfMqttCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BlitzwolfBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class BlitzwolfBinarySensor(BinarySensorEntity):
    """A binary sensor entity for BlitzWolf vacuum data."""

    _attr_has_entity_name = True
    entity_description: BlitzwolfBinarySensorDescription

    def __init__(
        self,
        coordinator: BlitzwolfMqttCoordinator,
        entry: ConfigEntry,
        description: BlitzwolfBinarySensorDescription,
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
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(
            self._coordinator.data, self._coordinator
        )

    @property
    def available(self) -> bool:
        # MQTT connectivity sensor should always be available
        if self.entity_description.key == "mqtt_connected":
            return True
        return self._coordinator.connected
