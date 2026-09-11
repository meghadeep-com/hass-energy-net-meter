"""Config flow for Roy's Net Meter integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_NAME
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    DOMAIN, 
    DEFAULT_NAME, 
    RoysNetMeter,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    MIN_TIME_BETWEEN_UPDATES,
    GEN_AMP_ENTITY,
    CON_AMP_ENTITY,
    FLOW_POWER_ENTITY,
    FLOW_ENERGY_ENTITY,
    GEN_POWER_ENTITY,
    GEN_ENERGY_ENTITY
)


class RoysNetMeter_flow_handler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Roy's Net Meter config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None, is_import: bool = False
    ) -> FlowResult:
        """Handle init step of a flow."""
        errors = {}

        if user_input is not None:
            gen_amp_entity = user_input[GEN_AMP_ENTITY]
            con_amp_entity = user_input[CON_AMP_ENTITY]
            flow_power_entity = user_input[FLOW_POWER_ENTITY]
            flow_energy_entity = user_input[FLOW_ENERGY_ENTITY]
            gen_power_entity = user_input[GEN_POWER_ENTITY]
            gen_energy_entity = user_input[GEN_ENERGY_ENTITY]
            name = user_input[CONF_NAME]
            
            hub = RoysNetMeter(gen_amp_entity, con_amp_entity, flow_power_entity, flow_energy_entity, gen_power_entity, gen_energy_entity, self.hass)

            if await hub.authenticate():
                self._config[CONF_NAME] = name
                self._config[GEN_AMP_ENTITY] = gen_amp_entity
                self._config[CON_AMP_ENTITY] = con_amp_entity
                self._config[FLOW_POWER_ENTITY] = flow_power_entity
                self._config[FLOW_ENERGY_ENTITY] = flow_energy_entity
                self._config[GEN_POWER_ENTITY] = gen_power_entity
                self._config[GEN_ENERGY_ENTITY] = gen_energy_entity
                return self.async_create_entry(
                title=self._config[CONF_NAME],
                data={
                    **self._config,
                },
                )
            else:
                raise ConfigEntryAuthFailed

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        GEN_AMP_ENTITY,
                        default=user_input.get(GEN_AMP_ENTITY, ''),
                    ): str,
                    vol.Required(
                        CON_AMP_ENTITY,
                        default=user_input.get(CON_AMP_ENTITY, ''),
                    ): str,
                    vol.Required(
                        FLOW_POWER_ENTITY,
                        default=user_input.get(FLOW_POWER_ENTITY, ''),
                    ): str,
                    vol.Required(
                        FLOW_ENERGY_ENTITY,
                        default=user_input.get(FLOW_ENERGY_ENTITY, ''),
                    ): str,
                    vol.Required(
                        GEN_POWER_ENTITY,
                        default=user_input.get(GEN_POWER_ENTITY, ''),
                    ): str,
                    vol.Required(
                        GEN_ENERGY_ENTITY,
                        default=user_input.get(GEN_ENERGY_ENTITY, ''),
                    ): str,
                }
            ),
            errors=errors,
        )
