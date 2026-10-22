"""Time Off coordinator."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event

from .const import DOMAIN

if TYPE_CHECKING:
    from .number import TimeOffDefaultNumber
    from .sensor import OffAfterSensor
    from .switch import TimeOffTriggerSwitch

_LOGGER = logging.getLogger(__name__)

_INACTIVE_STATES = frozenset(
    {STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN, "closed", "closing", "idle", "docked", "standby"}
)

RECOVERY_GRACE_SECONDS = 30


def signal_update(entity_id: str) -> str:
    return f"{DOMAIN}_update_{entity_id}"


def _is_active(state_obj: State | None) -> bool:
    return bool(state_obj and state_obj.state not in _INACTIVE_STATES)


async def _async_turn_off_entity(hass: HomeAssistant, entity_id: str) -> None:
    domain = entity_id.split(".")[0]
    if domain == "cover":
        service_domain, service = "cover", "close_cover"
    elif domain == "valve":
        service_domain, service = "valve", "close_valve"
    elif domain == "vacuum":
        service_domain, service = "vacuum", "return_to_base"
    else:
        service_domain, service = "homeassistant", "turn_off"
    await hass.services.async_call(
        service_domain, service, {"entity_id": entity_id}, context=Context()
    )


class TimeOffCoordinator:
    """Owns the timer state and logic for one managed device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, entity_id: str) -> None:
        self.hass = hass
        self.entry = entry
        self.entity_id = entity_id
        self.slug = entity_id.split(".")[-1]

        self.device_info: DeviceInfo | None = None
        self.device_registry_id: str | None = None
        # Suppresses auto-start during startup recovery
        self.is_recovering = True
        self.off_after_value: float = 0.0

        # Registered by each entity in async_added_to_hass; falls back to state machine before that
        self.number_entity: TimeOffDefaultNumber | None = None
        self.switch_entity: TimeOffTriggerSwitch | None = None
        self.off_after_sensor: OffAfterSensor | None = None

        self._unsub_expiry: CALLBACK_TYPE | None = None
        self.recover_task: asyncio.Task | None = None

    @property
    def default_duration(self) -> float:
        if self.number_entity is not None and self.number_entity.hass is not None:
            return float(self.number_entity.native_value or 0.0)
        state = self.hass.states.get(f"number.{self.slug}_time_off")
        try:
            return float(state.state) if state else 0.0
        except (ValueError, TypeError):
            return 0.0

    @property
    def trigger_only(self) -> bool:
        if self.switch_entity is not None and self.switch_entity.hass is not None:
            return bool(self.switch_entity.is_on)
        state = self.hass.states.get(f"switch.{self.slug}_trigger_only")
        return bool(state and state.state == STATE_ON)

    async def async_setup(self) -> None:
        self._link_device()
        self._clean_ghost_entities()
        store = self.hass.data[DOMAIN]["store"]
        raw = await store.async_load() or {}
        self.hass.data[DOMAIN]["global_expiry"].update(raw.get("expires", {}))

    def _link_device(self) -> None:
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        target_entry = ent_reg.async_get(self.entity_id)
        if target_entry and target_entry.device_id:
            phys_dev = dev_reg.async_get(target_entry.device_id)
            if phys_dev:
                self.device_info = DeviceInfo(identifiers=phys_dev.identifiers)
                self.device_registry_id = phys_dev.id
                return

        readable_name = self.slug.replace("_", " ").title()
        virtual_identifiers = {(DOMAIN, self.entry.entry_id)}
        virtual_dev = dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers=virtual_identifiers,
            name=readable_name,
        )
        self.device_info = DeviceInfo(identifiers=virtual_identifiers, name=readable_name)
        self.device_registry_id = virtual_dev.id

    def _clean_ghost_entities(self) -> None:
        """Remove stale helper entities left after a managed-device rename."""
        ent_reg = er.async_get(self.hass)
        expected_unique_ids = {
            f"{DOMAIN}_{self.slug}_time_off",
            f"{DOMAIN}_{self.slug}_trigger_only",
            f"{DOMAIN}_{self.slug}_active",
            f"{DOMAIN}_{self.slug}_off_after",
        }
        for reg_entry in er.async_entries_for_config_entry(ent_reg, self.entry.entry_id):
            if reg_entry.unique_id not in expected_unique_ids:
                ent_reg.async_remove(reg_entry.entity_id)

    async def async_unload(self) -> None:
        if self.recover_task is not None:
            self.recover_task.cancel()
            self.recover_task = None
        self._cancel_scheduling()

    @callback
    def async_handle_shutdown(self, event: Event) -> None:
        self._cancel_scheduling()

    async def async_start_countdown(self, expiry_override: str | None = None) -> None:
        self._cancel_scheduling()

        # If off_after is 0, copy the default in; non-zero means an automation pre-set it
        if self.off_after_value <= 0.0:
            self._set_off_after_value(self.default_duration)

        delay = self.off_after_value
        state_obj = self.hass.states.get(self.entity_id)
        if delay <= 0 or not _is_active(state_obj):
            await self._async_clear(reset_off_after=True)
            return

        expiry = dt_util.parse_datetime(expiry_override) if expiry_override else None
        if expiry is None:
            expiry = dt_util.now() + timedelta(minutes=delay)

        self.hass.data[DOMAIN]["global_expiry"][self.entity_id] = expiry.isoformat()
        await self._async_save()

        # Re-check: device may have turned off during the async save
        if not _is_active(self.hass.states.get(self.entity_id)):
            await self._async_clear(reset_off_after=True)
            return

        self._notify_update()
        self._unsub_expiry = async_track_point_in_time(
            self.hass, self._async_handle_expiry, expiry
        )

    async def async_stop_timer(self) -> None:
        await self._async_clear(reset_off_after=True)

    async def async_set_off_after(self, minutes: float) -> None:
        self._set_off_after_value(minutes)
        if minutes <= 0:
            await self.async_stop_timer()
        else:
            await self.async_start_countdown()

    async def _async_handle_expiry(self, now: datetime) -> None:
        self._unsub_expiry = None
        expired_event = {
            "entity_id": self.entity_id,
            "device_id": self.device_registry_id,
        }

        if self.trigger_only:
            self.hass.bus.async_fire("time_off_timer_expired", expired_event)
            await self.async_start_countdown()
            return

        await _async_turn_off_entity(self.hass, self.entity_id)
        self.hass.bus.async_fire("time_off_timer_expired", expired_event)
        await self._async_clear(reset_off_after=True)

    def _cancel_scheduling(self) -> None:
        if self._unsub_expiry is not None:
            self._unsub_expiry()
            self._unsub_expiry = None

    async def _async_clear(self, reset_off_after: bool) -> None:
        self._cancel_scheduling()
        self.hass.data[DOMAIN]["global_expiry"].pop(self.entity_id, None)
        await self._async_save()
        self._notify_update()
        if reset_off_after:
            self._set_off_after_value(0.0)

    def _set_off_after_value(self, value: float) -> None:
        self.off_after_value = float(value)
        if self.off_after_sensor is not None and self.off_after_sensor.hass is not None:
            self.off_after_sensor.async_write_ha_state()

    def _notify_update(self) -> None:
        async_dispatcher_send(self.hass, signal_update(self.entity_id))

    async def _async_save(self) -> None:
        if self.hass.is_stopping:
            return
        async with self.hass.data[DOMAIN]["save_lock"]:
            await self.hass.data[DOMAIN]["store"].async_save(
                {"expires": dict(self.hass.data[DOMAIN]["global_expiry"])}
            )

    async def async_handle_state_change(self, event: Event) -> None:
        if self.is_recovering:
            return
        new_s = event.data.get("new_state")
        old_s = event.data.get("old_state")
        # Ignore unavailable/unknown — connectivity noise, not device activity
        if new_s is None or new_s.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if old_s is not None and new_s.state == old_s.state:
            return

        if _is_active(new_s) and not _is_active(old_s):
            if self._unsub_expiry is None:
                await self.async_start_countdown()
        elif not _is_active(new_s) and self._unsub_expiry is not None:
            await self._async_clear(reset_off_after=True)

    async def async_handle_registry_update(self, event: Event) -> None:
        data = event.data
        if data.get("action") == "remove":
            _LOGGER.warning(
                "Time Off: managed entity %s was removed from the entity "
                "registry; remove or reconfigure its Time Off entry",
                data.get("entity_id"),
            )
            return
        if data.get("action") != "update" or "old_entity_id" not in data:
            return

        old_id = data["old_entity_id"]
        new_id = data["entity_id"]
        _LOGGER.warning(
            "Time Off: managed entity %s was renamed to %s; reloading",
            old_id, new_id,
        )
        exp = self.hass.data[DOMAIN]["global_expiry"].pop(old_id, None)
        if exp:
            self.hass.data[DOMAIN]["global_expiry"][new_id] = exp
            await self._async_save()
        new_entities = [
            new_id if eid == old_id else eid
            for eid in self.entry.data.get("entities", [])
        ]
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, "entities": new_entities}
        )
        self.hass.config_entries.async_schedule_reload(self.entry.entry_id)

    async def async_recover(self) -> None:
        eid = self.entity_id
        try:
            if self.hass.data[DOMAIN]["global_expiry"].get(eid):
                await self._async_wait_for_real_state(eid)
            exp_str = self.hass.data[DOMAIN]["global_expiry"].get(eid)
            if exp_str:
                await self._async_recover_one(eid, exp_str)
        finally:
            self.is_recovering = False

    async def _async_wait_for_real_state(self, eid: str) -> None:
        """Wait for entity to report a real state, or grace cap expires."""
        state = self.hass.states.get(eid)
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        ready: asyncio.Future[None] = self.hass.loop.create_future()

        @callback
        def _resolve(*_args: object) -> None:
            if not ready.done():
                ready.set_result(None)

        @callback
        def _on_state_change(event: Event) -> None:
            new_s = event.data.get("new_state")
            if new_s is not None and new_s.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                _resolve()

        unsub_state = async_track_state_change_event(self.hass, [eid], _on_state_change)
        unsub_cap = async_track_point_in_time(
            self.hass, _resolve,
            dt_util.now() + timedelta(seconds=RECOVERY_GRACE_SECONDS),
        )
        try:
            await ready
        finally:
            unsub_state()
            unsub_cap()

    async def _async_recover_one(self, eid: str, exp_str: str) -> None:
        expiry = dt_util.parse_datetime(exp_str)
        state = self.hass.states.get(eid)

        if expiry and expiry > dt_util.now():
            if _is_active(state):
                await self.async_start_countdown(exp_str)
            else:
                await self._async_clear(reset_off_after=False)
            return

        await self._async_clear(reset_off_after=False)

        if expiry is None:
            _LOGGER.warning("Time Off: discarded unparseable saved expiry for %s", eid)
            return

        _LOGGER.debug("Time Off: timer for %s expired during shutdown, acting now", eid)
        expired_event = {"entity_id": eid, "device_id": self.device_registry_id}
        if self.trigger_only:
            self.hass.bus.async_fire("time_off_timer_expired", expired_event)
            if _is_active(state):
                await self.async_start_countdown()
        elif _is_active(state):
            await _async_turn_off_entity(self.hass, eid)
            self.hass.bus.async_fire("time_off_timer_expired", expired_event)
