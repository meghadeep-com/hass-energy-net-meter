"""Constants for the AMASTech integration."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final
from dataclasses import dataclass
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import logging, asyncio
import aiohttp
import async_timeout
from datetime import timedelta, datetime
from typing import Any
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfEnergy, UnitOfPower, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.event import async_track_state_change_event, async_track_template_result
from binascii import a2b_base64
from json import loads, dumps

_LOGGER = logging.getLogger(__name__)


DOMAIN: Final = 'roys-net-meter'
DEFAULT_NAME: Final = "Roy's Net Meter"
DATA_KEY_API: Final = 'api'
DATA_KEY_COORDINATOR: Final = 'coordinator'
GEN_AMP_ENTITY: Final = 'gen_amp_entity'
CON_AMP_ENTITY: Final = 'con_amp_entity'
FLOW_POWER_ENTITY: Final = 'flow_power_entity'
FLOW_ENERGY_ENTITY: Final = 'flow_energy_entity'
GEN_POWER_ENTITY: Final = 'gen_power_entity'
GEN_ENERGY_ENTITY: Final = 'gen_energy_entity'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=0.5)

def parse_sensor_state(state):
    """Parse the state of a sensor into open/closed/unavailable/unknown."""
    if not state or not state.state:
        raise ConfigEntryNotReady
    elif state.state == STATE_UNAVAILABLE:
        raise ConfigEntryNotReady
    else:
        try:
            return float(state.state)
        except:
            raise ConfigEntryNotReady

class RoysNetMeter:
    """Roy's Net Meter class to check configuration and get related entity info.

    """

    def __init__(self, gen_amp_entity: str, con_amp_entity: str, flow_power_entity: str, flow_energy_entity: str, gen_power_entity: str, gen_energy_entity: str, hass: HomeAssistant) -> None:
        """Initialize."""
        self.gen_amp_entity = gen_amp_entity
        self.con_amp_entity = con_amp_entity
        self.flow_power_entity = flow_power_entity
        self.flow_energy_entity = flow_energy_entity
        self.gen_power_entity = gen_power_entity
        self.gen_energy_entity = gen_energy_entity
        self.hass = hass
        self.loop = hass.loop

        self.event_listener = []
        self.old_state = {}
        self.new_state = {}
        self.transient_state = {}

        self.old_state['power'] = {}
        self.old_state['energy'] = {}
        self.old_state['power']['flow'] = 0
        self.old_state['power']['generation'] = 0
        self.old_state['energy']['flow'] = 0
        self.old_state['energy']['generation'] = 0
        self.transient_state['power'] = {}
        self.transient_state['energy'] = {}
        self.transient_state['power']['flow'] = 0
        self.transient_state['power']['generation'] = 0
        self.transient_state['energy']['flow'] = 0
        self.transient_state['energy']['generation'] = 0
        self.new_state['power'] = {}
        self.new_state['energy'] = {}
        self.new_state['power']['flow'] = 0
        self.new_state['power']['generation'] = 0
        self.new_state['energy']['flow'] = 0
        self.new_state['energy']['generation'] = 0
        self.new_state['sensors'] = {}
        self.new_state['sensors']['consumption_energy'] = 0
        self.new_state['sensors']['import_energy'] = 0
        self.new_state['sensors']['export_energy'] = 0
        self.new_state['sensors']['consumption_power'] = 0
        self.new_state['sensors']['import_power'] = 0
        self.new_state['sensors']['export_power'] = 0

    async def authenticate(self) -> bool:
        """Test if we can get current states."""
        try:
            if self.hass.states.get(self.gen_amp_entity) and self.hass.states.get(self.con_amp_entity) and self.hass.states.get(self.flow_power_entity) and self.hass.states.get(self.flow_energy_entity) and self.hass.states.get(self.gen_power_entity) and self.hass.states.get(self.gen_energy_entity):

                gen_amp = parse_sensor_state(self.hass.states.get(self.gen_amp_entity))
                con_amp = parse_sensor_state(self.hass.states.get(self.con_amp_entity))
                if gen_amp > con_amp:
                    self.old_state['energy']['flow'] = (-1)*parse_sensor_state(self.hass.states.get(self.flow_energy_entity))
                    self.old_state['power']['flow'] = (-1)*parse_sensor_state(self.hass.states.get(self.flow_power_entity))
                else:
                    self.old_state['energy']['flow'] = parse_sensor_state(self.hass.states.get(self.flow_energy_entity))
                    self.old_state['power']['flow'] = parse_sensor_state(self.hass.states.get(self.flow_power_entity))
                self.old_state['energy']['generation'] = parse_sensor_state(self.hass.states.get(self.gen_energy_entity))
                self.old_state['power']['generation'] = parse_sensor_state(self.hass.states.get(self.gen_power_entity))
                return True
        except Exception as e:
            _LOGGER.fatal("Failed: %s", str(e))
            raise ConfigEntryNotReady
        
    async def perform_calculations(self) -> None:
        """Perform calculations to store new states"""
        gen_amp = parse_sensor_state(self.hass.states.get(self.gen_amp_entity))
        con_amp = parse_sensor_state(self.hass.states.get(self.con_amp_entity))
        if gen_amp not in [STATE_UNAVAILABLE, STATE_UNKNOWN] and con_amp not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            # Generation is more than consumption
            if gen_amp > con_amp:
                # Calculate power
                gen_power = parse_sensor_state(self.hass.states.get(self.gen_power_entity))
                flow_power = (-1)*parse_sensor_state(self.hass.states.get(self.flow_power_entity))
                self.new_state['sensors']['consumption_power'] = gen_power + flow_power
                self.new_state['sensors']['import_power'] = 0
                self.new_state['sensors']['export_power'] = (-1)*flow_power
            # Consumption is more than generation
            else:
                # Calculate power
                gen_power = parse_sensor_state(self.hass.states.get(self.gen_power_entity))
                flow_power = parse_sensor_state(self.hass.states.get(self.flow_power_entity))
                self.new_state['sensors']['consumption_power'] = gen_power + flow_power
                self.new_state['sensors']['import_power'] = flow_power
                self.new_state['sensors']['export_power'] = 0
                # Calculate energy
                # Check if flow sign is changing

@dataclass
class RoysNetMeterSensorEntityDescription(SensorEntityDescription):
    """Describes Roy's Net Meter sensor entities."""

    icon: str = "mdi:tranmission-tower"


SENSOR_TYPES: tuple[RoysNetMeterSensorEntityDescription, ...] = (
    RoysNetMeterSensorEntityDescription(
        key="consumption_power",
        name="Consumption Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash-outline",
        device_class=SensorDeviceClass.POWER,
    ),
    RoysNetMeterSensorEntityDescription(
        key="consumption_energy",
        name="Consumed Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
    ),
    RoysNetMeterSensorEntityDescription(
        key="export_power",
        name="Export Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
    ),
    RoysNetMeterSensorEntityDescription(
        key="export_energy",
        name="Exported Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.ENERGY,
    ),
    RoysNetMeterSensorEntityDescription(
        key="import_power",
        name="Import Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash-outline",
        device_class=SensorDeviceClass.POWER,
    ),
    RoysNetMeterSensorEntityDescription(
        key="import_energy",
        name="Imported Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
    ),
)