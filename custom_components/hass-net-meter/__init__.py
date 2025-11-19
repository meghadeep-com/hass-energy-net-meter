"""The AMASTech integration."""
from __future__ import annotations
import logging


import async_timeout
import voluptuous as vol
import asyncio
from datetime import datetime

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)


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

_LOGGER = logging.getLogger(__name__)

RoysNetMeter_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(GEN_AMP_ENTITY, msg='Enter your generation amperage entity', description='Enter your generation amperage entity'): cv.string,
            vol.Required(CON_AMP_ENTITY, msg='Enter your consumption amperage entity', description='Enter your consumption amperage entity'): cv.string,
            vol.Required(FLOW_POWER_ENTITY, msg='Enter your flow power entity', description='Enter your flow power entity'): cv.string,
            vol.Required(FLOW_ENERGY_ENTITY, msg='Enter your flow energy entity', description='Enter your flow energy entity'): cv.string,
            vol.Required(GEN_POWER_ENTITY, msg='Enter your generation power entity', description='Enter your generation power entity'): cv.string,
            vol.Required(GEN_ENERGY_ENTITY, msg='Enter your generation energy entity', description='Enter your generation energy entity'): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [RoysNetMeter_SCHEMA]))},
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Roy's Net Meter integration."""

    hass.data[DOMAIN] = {}

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roy's Net Meter from a config entry."""

    gen_amp_entity = entry.data[GEN_AMP_ENTITY]
    con_amp_entity = entry.data[CON_AMP_ENTITY]
    flow_power_entity = entry.data[FLOW_POWER_ENTITY]
    flow_energy_entity = entry.data[FLOW_ENERGY_ENTITY]
    gen_power_entity = entry.data[GEN_POWER_ENTITY]
    gen_energy_entity = entry.data[GEN_ENERGY_ENTITY]
    name = entry.data[CONF_NAME]
    api = RoysNetMeter(gen_amp_entity, con_amp_entity, flow_power_entity, flow_energy_entity, gen_power_entity, gen_energy_entity, hass)
    if await api.authenticate():
        hass.config_entries.async_update_entry(entry, unique_id=('roys-net-meter'))
    else: raise ConfigEntryAuthFailed
    
    async def async_update_data() -> None:
        """Fetch data from events endpoint.

        """
        if api.event_listener:
            for i in api.event_listener:
                i()
        else:
            raise ConfigEntryNotReady


    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
        }

    await hass.config_entries.async_forward_entry_setups(entry, _async_platforms(entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _async_platforms(entry)):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
@callback
def _async_platforms(entry: ConfigEntry) -> list[Platform]:
    """Return platforms to be loaded / unloaded."""
    platforms = [Platform.SENSOR]
    return platforms


class RoysNetMeterEntity(CoordinatorEntity):
    """Representation of Roy's Net Meter entity."""

    def __init__(
        self,
        api: RoysNetMeter,
        coordinator: DataUpdateCoordinator,
        _name: str,
        _device_unique_id: str,
    ) -> None:
        """Initialize Roy's Net Meter entity."""
        super().__init__(coordinator)
        self.api = api
        self._name = _name
        self._device_unique_id = _device_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_unique_id)},
            name=self._name,
            manufacturer="Meghadeep Roy Chowdhury"
        )
