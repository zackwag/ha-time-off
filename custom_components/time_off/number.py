"""Time Off number platform."""

from __future__ import annotations

from homeassistant.components.number import (NumberDeviceClass, NumberEntity,
                                             NumberMode)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    async_add_entities([TimeOffDefaultNumber(coordinator)])


class TimeOffDefaultNumber(NumberEntity, RestoreEntity):
    """User-facing default timer duration for a managed device."""

    _attr_has_entity_name = True
    _attr_translation_key = "time_off"
    _attr_should_poll = False
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.0
    _attr_native_max_value = 1440.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: TimeOffCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_{coordinator.slug}_time_off"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"number.{coordinator.slug}_time_off"
        self._attr_native_value = 0.0

    @property
    def icon(self) -> str:
        return "mdi:timer-sand" if (self._attr_native_value or 0) > 0 else "mdi:timer-sand-empty"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            try:
                self._attr_native_value = float(state.state)
            except (ValueError, TypeError):
                self._attr_native_value = 0.0

        self._coordinator.number_entity = self
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._coordinator.number_entity is self:
            self._coordinator.number_entity = None

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = float(value)
        self.async_write_ha_state()
