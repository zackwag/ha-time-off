"""Time Off trigger-only switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import TimeOffCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TimeOffCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([TimeOffTriggerSwitch(coordinator)])


class TimeOffTriggerSwitch(SwitchEntity, RestoreEntity):
    """OFF = auto-off mode (turn device off at expiry). ON = trigger-only (fire event, leave device alone)."""

    _attr_has_entity_name = True
    _attr_translation_key = "trigger_only"
    _attr_should_poll = False

    def __init__(self, coordinator: TimeOffCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_{coordinator.slug}_trigger_only"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"switch.{coordinator.slug}_trigger_only"
        self._attr_is_on = False

    @property
    def icon(self) -> str:
        return "mdi:alert-octagon-outline" if self.is_on else "mdi:auto-fix"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._attr_is_on = state.state == STATE_ON
        self._coordinator.switch_entity = self
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._coordinator.switch_entity is self:
            self._coordinator.switch_entity = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
