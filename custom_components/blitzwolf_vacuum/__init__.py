"""The BlitzWolf Vacuum integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SlamtecApi
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, PLATFORMS
from .coordinator import BlitzwolfMqttCoordinator

_LOGGER = logging.getLogger(__name__)

type BlitzwolfConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: BlitzwolfConfigEntry) -> bool:
    """Set up BlitzWolf Vacuum from a config entry."""
    session = async_get_clientsession(hass)
    api = SlamtecApi(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    # Authenticate and get user info
    await api.authenticate()
    user_id = entry.data.get("user_id")
    if not user_id:
        user_id = await api.get_user_id()
    else:
        api._user_id = user_id

    # Get device info
    device_id = entry.data["device_id"]
    devices = await api.get_devices()
    device_info = next(
        (d for d in devices if d["device_id"] == device_id),
        {"device_id": device_id, "device_name": "BlitzWolf Vacuum"},
    )

    # Create MQTT coordinator and connect
    coordinator = BlitzwolfMqttCoordinator(hass, api, device_id, device_info)
    await coordinator.async_connect()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Now that entities are listening, request a full data refresh
    # and start the periodic poll for non-streaming data
    await coordinator.async_request_full_update()
    await coordinator.async_start_refresh_loop()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BlitzwolfConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: BlitzwolfMqttCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_disconnect()
        await coordinator.api.close()
    return unload_ok
