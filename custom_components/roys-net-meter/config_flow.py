"""Config flow for Roy's Net Meter integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE
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
    CON_ENERGY_ENTITY,
    MAX_POWER,
    DEFAULT_MAX_POWER,
)

SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)

MAX_POWER_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="W"
    )
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

    @property
    def _reconfigure_entry(self) -> config_entries.ConfigEntry | None:
        """Return the entry being reconfigured, if this is a reconfigure flow."""
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry()
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of a fresh setup: name and meter type."""
        return await self._async_step_meter_type(user_input, step_id="user")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of a reconfigure: name and meter type."""
        return await self._async_step_meter_type(user_input, step_id="reconfigure")

    async def _async_step_meter_type(
        self, user_input: dict[str, Any] | None, step_id: str
    ) -> FlowResult:
        """Shared logic for the name/meter-type step, for both setup and reconfigure."""
        current = self._reconfigure_entry.data if self._reconfigure_entry else {}

        if user_input is not None:
            self._config[CONF_NAME] = user_input[CONF_NAME]
            self._config[METER_TYPE] = user_input[METER_TYPE]
            if user_input[METER_TYPE] == METER_TYPE_CONSUMPTION:
                return await self.async_step_consumption_meter()
            return await self.async_step_grid_meter()

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=current.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        METER_TYPE, default=current.get(METER_TYPE, METER_TYPE_GRID)
                    ): METER_TYPE_SELECTOR,
                }
            ),
        )

    def _finish(self, data: dict) -> FlowResult:
        """Create a new entry, or update+reload the one being reconfigured."""
        reconfigure_entry = self._reconfigure_entry
        if reconfigure_entry is not None:
            return self.async_update_reload_and_abort(reconfigure_entry, data=data)
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    async def async_step_grid_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity selection for a net grid meter setup."""
        errors = {}
        current = self._reconfigure_entry.data if self._reconfigure_entry else {}

        if user_input is not None:
            hub = RoysNetMeter(
                user_input[GEN_AMP_ENTITY],
                user_input[CON_AMP_ENTITY],
                user_input[FLOW_POWER_ENTITY],
                user_input[FLOW_ENERGY_ENTITY],
                user_input[GEN_POWER_ENTITY],
                user_input[GEN_ENERGY_ENTITY],
                self.hass,
                max_power=user_input.get(MAX_POWER, DEFAULT_MAX_POWER),
            )

            if await hub.authenticate():
                self._config.update(user_input)
                return self._finish(self._config)
            errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="grid_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        GEN_AMP_ENTITY,
                        default=user_input.get(GEN_AMP_ENTITY, current.get(GEN_AMP_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        CON_AMP_ENTITY,
                        default=user_input.get(CON_AMP_ENTITY, current.get(CON_AMP_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        FLOW_POWER_ENTITY,
                        default=user_input.get(FLOW_POWER_ENTITY, current.get(FLOW_POWER_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        FLOW_ENERGY_ENTITY,
                        default=user_input.get(FLOW_ENERGY_ENTITY, current.get(FLOW_ENERGY_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_POWER_ENTITY,
                        default=user_input.get(GEN_POWER_ENTITY, current.get(GEN_POWER_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_ENERGY_ENTITY,
                        default=user_input.get(GEN_ENERGY_ENTITY, current.get(GEN_ENERGY_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Optional(
                        MAX_POWER,
                        default=user_input.get(MAX_POWER, current.get(MAX_POWER, DEFAULT_MAX_POWER)),
                    ): MAX_POWER_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_consumption_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity selection for a direct consumption meter setup."""
        errors = {}
        current = self._reconfigure_entry.data if self._reconfigure_entry else {}

        if user_input is not None:
            hub = RoysConsumptionMeter(
                user_input[CON_POWER_ENTITY],
                user_input[CON_ENERGY_ENTITY],
                user_input[GEN_POWER_ENTITY],
                user_input[GEN_ENERGY_ENTITY],
                self.hass,
                max_power=user_input.get(MAX_POWER, DEFAULT_MAX_POWER),
            )

            if await hub.authenticate():
                self._config.update(user_input)
                return self._finish(self._config)
            errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="consumption_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CON_POWER_ENTITY,
                        default=user_input.get(CON_POWER_ENTITY, current.get(CON_POWER_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        CON_ENERGY_ENTITY,
                        default=user_input.get(CON_ENERGY_ENTITY, current.get(CON_ENERGY_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_POWER_ENTITY,
                        default=user_input.get(GEN_POWER_ENTITY, current.get(GEN_POWER_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Required(
                        GEN_ENERGY_ENTITY,
                        default=user_input.get(GEN_ENERGY_ENTITY, current.get(GEN_ENERGY_ENTITY, vol.UNDEFINED)),
                    ): SENSOR_SELECTOR,
                    vol.Optional(
                        MAX_POWER,
                        default=user_input.get(MAX_POWER, current.get(MAX_POWER, DEFAULT_MAX_POWER)),
                    ): MAX_POWER_SELECTOR,
                }
            ),
            errors=errors,
        )
