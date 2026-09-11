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
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    RoysNetMeter,
    RoysConsumptionMeter,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    MIN_TIME_BETWEEN_UPDATES,
    METER_TYPE,
    METER_TYPE_GRID,
    METER_TYPE_CONSUMPTION,
    GEN_AMP_ENTITY,
    CON_AMP_ENTITY,
    FLOW_POWER_ENTITY,
    FLOW_ENERGY_ENTITY,
    GEN_POWER_ENTITY,
    GEN_ENERGY_ENTITY,
    CON_POWER_ENTITY,
    CON_ENERGY_ENTITY
)

SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)

METER_TYPE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(
                value=METER_TYPE_GRID, label="Net grid meter (measures net import/export flow)"
            ),
            selector.SelectOptionDict(
                value=METER_TYPE_CONSUMPTION, label="Consumption meter (measures total home consumption)"
            ),
        ],
        mode=selector.SelectSelectorMode.LIST,
    )
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
        """Handle the first step: pick a name and which kind of meter to use."""
        if user_input is not None:
            self._config[CONF_NAME] = user_input[CONF_NAME]
            self._config[METER_TYPE] = user_input[METER_TYPE]
            if user_input[METER_TYPE] == METER_TYPE_CONSUMPTION:
                return await self.async_step_consumption_meter()
            return await self.async_step_grid_meter()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=DEFAULT_NAME
                    ): str,
                    vol.Required(
                        METER_TYPE, default=METER_TYPE_GRID
                    ): METER_TYPE_SELECTOR,
                }
            ),
        )

    async def async_step_grid_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity selection for a net grid meter setup."""
        errors = {}

        if user_input is not None:
            hub = RoysNetMeter(
                user_input[GEN_AMP_ENTITY],
                user_input[CON_AMP_ENTITY],
                user_input[FLOW_POWER_ENTITY],
                user_input[FLOW_ENERGY_ENTITY],
                user_input[GEN_POWER_ENTITY],
                user_input[GEN_ENERGY_ENTITY],
                self.hass,
            )

            try:
                authenticated = await hub.authenticate()
            except ConfigEntryNotReady:
                authenticated = False

            if authenticated:
                self._config.update(user_input)
                return self.async_create_entry(
                    title=self._config[CONF_NAME],
                    data=self._config,
                )
            errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="grid_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        GEN_AMP_ENTITY,
                        default=user_input.get(GEN_AMP_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        CON_AMP_ENTITY,
                        default=user_input.get(CON_AMP_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        FLOW_POWER_ENTITY,
                        default=user_input.get(FLOW_POWER_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        FLOW_ENERGY_ENTITY,
                        default=user_input.get(FLOW_ENERGY_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_POWER_ENTITY,
                        default=user_input.get(GEN_POWER_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_ENERGY_ENTITY,
                        default=user_input.get(GEN_ENERGY_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_consumption_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity selection for a direct consumption meter setup."""
        errors = {}

        if user_input is not None:
            hub = RoysConsumptionMeter(
                user_input[CON_POWER_ENTITY],
                user_input[CON_ENERGY_ENTITY],
                user_input[GEN_POWER_ENTITY],
                user_input[GEN_ENERGY_ENTITY],
                self.hass,
            )

            try:
                authenticated = await hub.authenticate()
            except ConfigEntryNotReady:
                authenticated = False

            if authenticated:
                self._config.update(user_input)
                return self.async_create_entry(
                    title=self._config[CONF_NAME],
                    data=self._config,
                )
            errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="consumption_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CON_POWER_ENTITY,
                        default=user_input.get(CON_POWER_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        CON_ENERGY_ENTITY,
                        default=user_input.get(CON_ENERGY_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_POWER_ENTITY,
                        default=user_input.get(GEN_POWER_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_ENERGY_ENTITY,
                        default=user_input.get(GEN_ENERGY_ENTITY, vol.UNDEFINED),
                    ): SENSOR_SELECTOR,
                }
            ),
            errors=errors,
        )
