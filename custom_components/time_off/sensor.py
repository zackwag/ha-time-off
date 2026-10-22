"""Time Off sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
    async_add_entities([OffAfterSensor(coordinator)])


class OffAfterSensor(SensorEntity, RestoreEntity):
    """Read-only display of the active Off After duration."""

    _attr_has_entity_name = True
    _attr_translation_key = "off_after"
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TimeOffCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_{coordinator.slug}_off_after"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"sensor.{coordinator.slug}_off_after"

    @property
    def native_value(self) -> float:
        return self._coordinator.off_after_value

    @property
    def icon(self) -> str:
        return "mdi:timer-sand" if (self.native_value or 0) > 0 else "mdi:timer-sand-empty"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            try:
                restored = float(state.state)
            except (ValueError, TypeError):
                restored = 0.0
            # Only keep restored value if a saved expiry exists to resume;
            # otherwise it's stale from an unclean shutdown.
            domain_data = self.hass.data.get(DOMAIN, {})
            if domain_data.get("global_expiry", {}).get(self._coordinator.entity_id):
                self._coordinator.off_after_value = restored
            else:
                self._coordinator.off_after_value = 0.0

        self._coordinator.off_after_sensor = self
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._coordinator.off_after_sensor is self:
            self._coordinator.off_after_sensor = None
