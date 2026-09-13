"""Constants for the Roy's Net Meter integration."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final
from dataclasses import dataclass
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import logging, asyncio
import aiohttp
import async_timeout
from datetime import datetime
from typing import Any
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass, SensorStateClass
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
CON_POWER_ENTITY: Final = 'con_power_entity'
CON_ENERGY_ENTITY: Final = 'con_energy_entity'
METER_TYPE: Final = 'meter_type'
METER_TYPE_GRID: Final = 'grid'
METER_TYPE_CONSUMPTION: Final = 'consumption'
MAX_POWER: Final = 'max_power'
DEFAULT_MAX_POWER: Final = 20000

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

def validate_power(name: str, value: float, max_power: float, last_good: dict) -> float:
    """Replace an implausible power reading with the last known-good one.

    Same job as the manual "hold last good value" template sensors some
    users wire in front of a flaky power meter: a negative or too-large
    reading falls back to whatever this same field last read as valid,
    instead of being used as-is. This is deliberately NOT the same as the
    sensor being genuinely unavailable/unknown (parse_sensor_state already
    raises ConfigEntryNotReady for that, which the caller should let
    propagate) - here the sensor is answering, just with a number that
    can't be real, so we keep going rather than failing the whole update.

    Raises ConfigEntryNotReady only if there's no known-good value yet to
    fall back to (e.g. right at startup) - genuinely nothing better to do
    at that point.
    """
    if value < 0 or value > max_power:
        if name not in last_good:
            raise ConfigEntryNotReady(
                f"implausible {name} reading: {value}W (limit is {max_power}W), and no known-good value yet"
            )
        _LOGGER.warning(
            "Ignoring implausible %s reading: %sW (limit is %sW); using last known-good value %sW",
            name, value, max_power, last_good[name],
        )
        return last_good[name]
    last_good[name] = value
    return value

class RoysNetMeter:
    """Roy's Net Meter class to check configuration and get related entity info.

    """

    def __init__(self, gen_amp_entity: str, con_amp_entity: str, flow_power_entity: str, flow_energy_entity: str, gen_power_entity: str, gen_energy_entity: str, hass: HomeAssistant, max_power: float = DEFAULT_MAX_POWER) -> None:
        """Initialize."""
        self.gen_amp_entity = gen_amp_entity
        self.con_amp_entity = con_amp_entity
        self.flow_power_entity = flow_power_entity
        self.flow_energy_entity = flow_energy_entity
        self.gen_power_entity = gen_power_entity
        self.gen_energy_entity = gen_energy_entity
        self.hass = hass
        self.loop = hass.loop
        self.ready = False
        self.max_power = max_power
        self._last_good_power = {}

        self.tracked_entities = [
            gen_amp_entity,
            con_amp_entity,
            flow_power_entity,
            flow_energy_entity,
            gen_power_entity,
            gen_energy_entity,
        ]

        self.event_listener = []
        self.old_state = {}
        self.new_state = {}
        self.transient_state = {}
        self.stale_state = {}

        self.old_state['power'] = {}
        self.old_state['energy'] = {}
        self.old_state['power']['flow'] = 0
        self.old_state['power']['generation'] = 0
        self.old_state['power']['consumption'] = 0
        self.old_state['energy']['flow'] = 0
        self.old_state['energy']['generation'] = 0
        self.old_state['energy']['consumption'] = 0
        self.old_state['energy']['import'] = 0
        self.old_state['energy']['export'] = 0
        self.stale_state['energy'] = {}
        self.stale_state['energy']['flow'] = 0
        self.transient_state['energy'] = {}
        self.transient_state['energy']['flow'] = 0
        self.new_state['sensors'] = {}
        self.new_state['sensors']['consumption_energy'] = 0
        self.new_state['sensors']['import_energy'] = 0
        self.new_state['sensors']['export_energy'] = 0
        self.new_state['sensors']['consumption_power'] = 0
        self.new_state['sensors']['import_power'] = 0
        self.new_state['sensors']['export_power'] = 0
        self.new_state['sensors']['grid_power'] = 0

    async def authenticate(self) -> bool:
        """Try to read a baseline from the configured entities.

        Returns False (never raises) if they don't exist or aren't ready
        yet, so callers can retry later instead of failing outright -
        important at Home Assistant startup, when the entities this
        integration depends on may not have loaded yet.
        """
        if not (self.hass.states.get(self.gen_amp_entity) and self.hass.states.get(self.con_amp_entity) and self.hass.states.get(self.flow_power_entity) and self.hass.states.get(self.flow_energy_entity) and self.hass.states.get(self.gen_power_entity) and self.hass.states.get(self.gen_energy_entity)):
            return False
        try:
            self.old_state['energy']['generation'] = parse_sensor_state(self.hass.states.get(self.gen_energy_entity))
            self.old_state['energy']['flow'] = parse_sensor_state(self.hass.states.get(self.flow_energy_entity))
        except ConfigEntryNotReady:
            return False
        self.stale_state['energy']['flow'] = self.old_state['energy']['flow']
        return True
        
    async def perform_calculations(self) -> None:
        """Perform calculations to store new states"""
        gen_amp = parse_sensor_state(self.hass.states.get(self.gen_amp_entity))
        con_amp = parse_sensor_state(self.hass.states.get(self.con_amp_entity))
        if gen_amp not in [STATE_UNAVAILABLE, STATE_UNKNOWN] and con_amp not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            # Generation is more than consumption
            if gen_amp > con_amp:
                # Calculate power
                gen_power = validate_power('gen_power', parse_sensor_state(self.hass.states.get(self.gen_power_entity)), self.max_power, self._last_good_power)
                flow_power = -1*validate_power('flow_power', parse_sensor_state(self.hass.states.get(self.flow_power_entity)), self.max_power, self._last_good_power)
                self.new_state['sensors']['consumption_power'] = gen_power + flow_power
                self.new_state['sensors']['import_power'] = 0
                self.new_state['sensors']['export_power'] = -1*flow_power
                self.new_state['sensors']['grid_power'] = flow_power
                self.old_state['power']['consumption'] = self.new_state['sensors']['consumption_power']
                self.old_state['power']['generation'] = gen_power
                self.old_state['power']['flow'] = flow_power
                # Calculate energy
                gen_energy = parse_sensor_state(self.hass.states.get(self.gen_energy_entity))
                flow_energy = parse_sensor_state(self.hass.states.get(self.flow_energy_entity))
                if gen_energy == self.old_state['energy']['generation']:
                    self.transient_state['energy']['flow'] = self.transient_state['energy']['flow'] - (flow_energy - self.old_state['energy']['flow'])
                else:
                    self.new_state['sensors']['consumption_energy'] = self.old_state['energy']['consumption'] + ((gen_energy - self.old_state['energy']['generation']) - (flow_energy - self.old_state['energy']['flow'])) + self.transient_state['energy']['flow']
                    self.new_state['sensors']['export_energy'] = self.old_state['energy']['export'] + (flow_energy - self.old_state['energy']['flow'] - self.transient_state['energy']['flow'])
                    self.transient_state['energy']['flow'] = 0
                    self.old_state['energy']['consumption'] = self.new_state['sensors']['consumption_energy']
                    self.old_state['energy']['export'] = self.new_state['sensors']['export_energy']
                if self.new_state['sensors']['export_energy'] < 0:
                    _LOGGER.warning('Old export: ' + str(self.old_state['energy']['export']) + 'New flow energy: ' + str(flow_energy) + ', Old flow energy: ' + str(flow_energy))
                
                self.old_state['energy']['flow'] = flow_energy
                self.old_state['energy']['generation'] = gen_energy
            # Consumption is more than generation
            else:
                # Calculate power
                gen_power = validate_power('gen_power', parse_sensor_state(self.hass.states.get(self.gen_power_entity)), self.max_power, self._last_good_power)
                flow_power = validate_power('flow_power', parse_sensor_state(self.hass.states.get(self.flow_power_entity)), self.max_power, self._last_good_power)
                self.new_state['sensors']['consumption_power'] = gen_power + flow_power
                self.new_state['sensors']['import_power'] = flow_power
                self.new_state['sensors']['export_power'] = 0
                self.new_state['sensors']['grid_power'] = flow_power
                self.old_state['power']['consumption'] = self.new_state['sensors']['consumption_power']
                self.old_state['power']['generation'] = gen_power
                self.old_state['power']['flow'] = flow_power
                # Calculate energy
                gen_energy = parse_sensor_state(self.hass.states.get(self.gen_energy_entity))
                flow_energy = parse_sensor_state(self.hass.states.get(self.flow_energy_entity))
                if self.transient_state['energy']['flow'] == 0:
                    self.new_state['sensors']['consumption_energy'] = self.old_state['energy']['consumption'] + (gen_energy - self.old_state['energy']['generation']) + (flow_energy - self.old_state['energy']['flow'])
                else:
                    if abs((gen_energy - self.old_state['energy']['generation']) + (flow_energy - self.old_state['energy']['flow'])) > abs(self.transient_state['energy']['flow']):
                        self.new_state['sensors']['consumption_energy'] = self.old_state['energy']['consumption'] + (gen_energy - self.old_state['energy']['generation']) + (flow_energy - self.old_state['energy']['flow']) + self.transient_state['energy']['flow']
                        self.new_state['sensors']['export_energy'] = self.old_state['energy']['export'] - self.transient_state['energy']['flow']
                        self.transient_state['energy']['flow'] = 0
                        self.old_state['energy']['export'] = self.new_state['sensors']['export_energy']
                self.new_state['sensors']['import_energy'] = self.old_state['energy']['import'] + (flow_energy - self.old_state['energy']['flow'])
                self.old_state['energy']['consumption'] = self.new_state['sensors']['consumption_energy']
                self.old_state['energy']['import'] = self.new_state['sensors']['import_energy']
                self.old_state['energy']['flow'] = flow_energy
                self.old_state['energy']['generation'] = gen_energy


class RoysConsumptionMeter:
    """Roy's Net Meter class for a direct home-consumption meter setup.

    Unlike RoysNetMeter (which derives consumption from a net-flow meter
    plus generation), this reads total home consumption directly and
    derives the grid import/export by comparing it against generation.
    """

    def __init__(self, con_power_entity: str, con_energy_entity: str, gen_power_entity: str, gen_energy_entity: str, hass: HomeAssistant, max_power: float = DEFAULT_MAX_POWER) -> None:
        """Initialize."""
        self.con_power_entity = con_power_entity
        self.con_energy_entity = con_energy_entity
        self.gen_power_entity = gen_power_entity
        self.gen_energy_entity = gen_energy_entity
        self.hass = hass
        self.loop = hass.loop
        self.ready = False
        self.max_power = max_power
        self._last_good_power = {}

        self.tracked_entities = [
            con_power_entity,
            con_energy_entity,
            gen_power_entity,
            gen_energy_entity,
        ]

        self.old_state = {}
        self.old_state['energy'] = {}
        self.old_state['energy']['consumption'] = 0
        self.old_state['energy']['generation'] = 0
        self.old_state['energy']['consumption_total'] = 0
        self.old_state['energy']['import'] = 0
        self.old_state['energy']['export'] = 0

        self.new_state = {}
        self.new_state['sensors'] = {}
        self.new_state['sensors']['consumption_energy'] = 0
        self.new_state['sensors']['import_energy'] = 0
        self.new_state['sensors']['export_energy'] = 0
        self.new_state['sensors']['consumption_power'] = 0
        self.new_state['sensors']['import_power'] = 0
        self.new_state['sensors']['export_power'] = 0
        self.new_state['sensors']['grid_power'] = 0

    async def authenticate(self) -> bool:
        """Try to read a baseline from the configured entities.

        Returns False (never raises) if they don't exist or aren't ready
        yet, so callers can retry later instead of failing outright.
        """
        if not (self.hass.states.get(self.con_power_entity) and self.hass.states.get(self.con_energy_entity) and self.hass.states.get(self.gen_power_entity) and self.hass.states.get(self.gen_energy_entity)):
            return False
        try:
            # Snapshot the meters' absolute readings as a baseline, so
            # consumption_energy/import_energy/export_energy accumulate
            # from zero from this point on, instead of jumping straight
            # to the meters' lifetime totals.
            self.old_state['energy']['consumption'] = parse_sensor_state(self.hass.states.get(self.con_energy_entity))
            self.old_state['energy']['generation'] = parse_sensor_state(self.hass.states.get(self.gen_energy_entity))
        except ConfigEntryNotReady:
            return False
        return True

    async def perform_calculations(self) -> None:
        """Perform calculations to store new states."""
        con_power = validate_power('con_power', parse_sensor_state(self.hass.states.get(self.con_power_entity)), self.max_power, self._last_good_power)
        gen_power = validate_power('gen_power', parse_sensor_state(self.hass.states.get(self.gen_power_entity)), self.max_power, self._last_good_power)
        con_energy = parse_sensor_state(self.hass.states.get(self.con_energy_entity))
        gen_energy = parse_sensor_state(self.hass.states.get(self.gen_energy_entity))

        # Positive grid_power means importing, negative means exporting.
        grid_power = con_power - gen_power

        self.new_state['sensors']['consumption_power'] = con_power
        self.new_state['sensors']['grid_power'] = grid_power
        self.new_state['sensors']['import_power'] = max(grid_power, 0)
        self.new_state['sensors']['export_power'] = max(-grid_power, 0)

        delta_consumption = con_energy - self.old_state['energy']['consumption']
        delta_generation = gen_energy - self.old_state['energy']['generation']
        net_delta = delta_consumption - delta_generation

        self.old_state['energy']['consumption_total'] += delta_consumption
        if net_delta > 0:
            self.old_state['energy']['import'] += net_delta
        else:
            self.old_state['energy']['export'] += -net_delta

        self.old_state['energy']['consumption'] = con_energy
        self.old_state['energy']['generation'] = gen_energy

        self.new_state['sensors']['consumption_energy'] = self.old_state['energy']['consumption_total']
        self.new_state['sensors']['import_energy'] = self.old_state['energy']['import']
        self.new_state['sensors']['export_energy'] = self.old_state['energy']['export']


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
        state_class=SensorStateClass.MEASUREMENT
    ),
    RoysNetMeterSensorEntityDescription(
        key="consumption_energy",
        name="Consumed Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:home-lightning-bolt-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING
    ),
    RoysNetMeterSensorEntityDescription(
        key="grid_power",
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT
    ),
    RoysNetMeterSensorEntityDescription(
        key="export_power",
        name="Export Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT
    ),
    RoysNetMeterSensorEntityDescription(
        key="export_energy",
        name="Exported Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING
    ),
    RoysNetMeterSensorEntityDescription(
        key="import_power",
        name="Import Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT
    ),
    RoysNetMeterSensorEntityDescription(
        key="import_energy",
        name="Imported Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING
    ),
)