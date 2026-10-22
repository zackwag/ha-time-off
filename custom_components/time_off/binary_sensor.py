"""Time Off binary sensor — Timer Active."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .coordinator import TimeOffCoordinator, signal_update

_REFRESH_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TimeOffCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([TimeOffActiveSensor(coordinator)])


class TimeOffActiveSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "timer_active"
    _attr_should_poll = False
    # Exclude "remaining" from recorder — it drifts every 30s tick.
    _unrecorded_attributes = frozenset({"remaining"})

    def __init__(self, coordinator: TimeOffCoordinator) -> None:
        self._target_id = coordinator.entity_id
        self._attr_unique_id = f"{DOMAIN}_{coordinator.slug}_active"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"binary_sensor.{coordinator.slug}_timer_active"
        self._unsub_interval: CALLBACK_TYPE | None = None

    @property
    def is_on(self) -> bool:
        return self.hass.data[DOMAIN]["global_expiry"].get(self._target_id) is not None

    @property
    def icon(self) -> str:
        return "mdi:timer-play" if self.is_on else "mdi:timer-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        exp_str = self.hass.data[DOMAIN]["global_expiry"].get(self._target_id)
        if not exp_str:
            return {"expiry": None, "remaining": "0m 0s"}

        expiry = dt_util.parse_datetime(exp_str)
        if not expiry:
            return {"expiry": None, "remaining": "0m 0s"}

        diff = expiry - dt_util.now()
        seconds = max(0, int(diff.total_seconds()))
        return {"expiry": exp_str, "remaining": f"{seconds // 60}m {seconds % 60}s"}

    async def async_added_to_hass(self) -> None:
        @callback
        def _update() -> None:
            self.async_write_ha_state()
            if self.is_on:
                self._start_interval()
            else:
                self._stop_interval()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_update(self._target_id), _update)
        )
        self.async_on_remove(self._stop_interval)

        if self.is_on:
            self._start_interval()

    def _start_interval(self) -> None:
        if self._unsub_interval is None:
            self._unsub_interval = async_track_time_interval(
                self.hass, self._tick, _REFRESH_INTERVAL
            )

    def _stop_interval(self) -> None:
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None

    @callback
    def _tick(self, now: datetime) -> None:
        self.async_write_ha_state()
