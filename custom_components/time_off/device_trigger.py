"""Time Off device triggers."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.device_automation import \
    DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import \
    event as event_trigger
from homeassistant.const import (CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM,
                                 CONF_TYPE)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

TRIGGER_TYPES = {"timer_expired"}

# Must extend DEVICE_TRIGGER_BASE_SCHEMA, not cv.TRIGGER_BASE_SCHEMA — the
# generic base rejects device_id/domain keys and breaks saved automations.
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "timer_expired",
        }
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    # Must validate through event trigger schema — it normalises event_type
    # into a list. A raw dict leaves it as a string, which gets iterated
    # char-by-char and the trigger never fires.
    event_config = event_trigger.TRIGGER_SCHEMA({
        CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: "time_off_timer_expired",
        event_trigger.CONF_EVENT_DATA: {
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        },
    })

    return await event_trigger.async_attach_trigger(
        hass,
        event_config,
        action,
        trigger_info,
        platform_type="device"
    )
