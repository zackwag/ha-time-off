"""Time Off config flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import DOMAIN


class TimeOffConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for creating a new Time Off instance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            selected_entity = user_input["entity"]
            user_input_data = {"entities": [selected_entity]}

            for entry in self._async_current_entries():
                if selected_entity in entry.data.get("entities", []):
                    return self.async_abort(reason="already_configured")

            readable_name = selected_entity.split(".")[-1].replace("_", " ").title()
            return self.async_create_entry(title=readable_name, data=user_input_data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("entity"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            multiple=False,
                            filter=[
                                {"domain": "switch"},
                                {"domain": "light"},
                                {"domain": "fan"},
                                {"domain": "media_player"},
                                {"domain": "cover"},
                                {"domain": "climate"},
                                {"domain": "input_boolean"},
                                {"domain": "humidifier"},
                                {"domain": "siren"},
                                {"domain": "valve"},
                                {"domain": "vacuum"},
                            ],
                            exclude_entities=self._get_current_time_off_entities(),
                        )
                    ),
                }
            ),
        )

    def _get_current_time_off_entities(self) -> list[str]:
        ent_reg = er.async_get(self.hass)
        return [
            entity.entity_id
            for entity in ent_reg.entities.values()
            if entity.platform == DOMAIN
        ]
