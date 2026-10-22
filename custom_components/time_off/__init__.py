"""Time Off integration."""

from __future__ import annotations

import asyncio
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import TimeOffCoordinator

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.timers"
PLATFORMS = ["number", "switch", "binary_sensor", "sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SCHEMA_ENTITY = vol.Schema({vol.Required("entity_id"): cv.entity_id})
SERVICE_SCHEMA_SET_OFF_AFTER = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("minutes"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1440)),
    }
)


def _find_coordinator(hass: HomeAssistant, entity_id: str) -> TimeOffCoordinator:
    for coordinator in hass.data.get(DOMAIN, {}).get("coordinators", {}).values():
        if coordinator.entity_id == entity_id:
            return coordinator
    raise ServiceValidationError(
        f"{entity_id} is not managed by Time Off. The entity_id must be the "
        "managed device (e.g. fan.bathroom_fan), not a Time Off helper entity."
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register domain-level services."""
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.debug("Time Off %s: registering services", integration.version)

    async def handle_start_timer(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data["entity_id"])
        await coordinator.async_start_countdown()

    async def handle_stop_timer(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data["entity_id"])
        await coordinator.async_stop_timer()

    async def handle_set_off_after(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data["entity_id"])
        await coordinator.async_set_off_after(call.data["minutes"])

    hass.services.async_register(
        DOMAIN, "start_timer", handle_start_timer, schema=SERVICE_SCHEMA_ENTITY
    )
    hass.services.async_register(
        DOMAIN, "stop_timer", handle_stop_timer, schema=SERVICE_SCHEMA_ENTITY
    )
    hass.services.async_register(
        DOMAIN, "set_off_after", handle_set_off_after, schema=SERVICE_SCHEMA_SET_OFF_AFTER
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Time Off config entry."""
    domain_data = hass.data.setdefault(
        DOMAIN,
        {
            "global_expiry": {},
            "save_lock": asyncio.Lock(),
            "store": Store(hass, STORAGE_VERSION, STORAGE_KEY),
            "coordinators": {},
        },
    )

    targets = list(entry.data.get("entities", []))
    if not targets:
        _LOGGER.error(
            "Time Off: config entry %s has no managed entity; cannot set up",
            entry.entry_id,
        )
        return False

    coordinator = TimeOffCoordinator(hass, entry, targets[0])
    domain_data["coordinators"][entry.entry_id] = coordinator

    await coordinator.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def _schedule_recover() -> None:
        coordinator.recover_task = hass.async_create_background_task(
            coordinator.async_recover(), name=f"time_off_recover_{entry.entry_id}"
        )

    if hass.state == CoreState.running:
        _schedule_recover()
    else:

        async def _on_started(event) -> None:
            _schedule_recover()

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
        )

    entry.async_on_unload(
        async_track_state_change_event(
            hass, targets, coordinator.async_handle_state_change
        )
    )
    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, targets, coordinator.async_handle_registry_update
        )
    )
    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, coordinator.async_handle_shutdown
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: TimeOffCoordinator | None = hass.data[DOMAIN]["coordinators"].get(
        entry.entry_id
    )
    if coordinator is not None:
        await coordinator.async_unload()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN]["coordinators"].pop(entry.entry_id, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear persisted timer data when an entry is permanently removed."""
    domain_data = hass.data.get(DOMAIN)
    if not domain_data:
        return

    changed = False
    for eid in entry.data.get("entities", []):
        if domain_data["global_expiry"].pop(eid, None) is not None:
            changed = True

    if changed:
        async with domain_data["save_lock"]:
            await domain_data["store"].async_save(
                {"expires": dict(domain_data["global_expiry"])}
            )
