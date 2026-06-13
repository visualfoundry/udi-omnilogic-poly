"""
Heater node.

Drivers:  ST  = state (0 off / 1 heating), GV0 = setpoint deg F
Commands: DON / DOF (enable/disable), SET_SP (set target temp deg F)
"""
import udi_interface

LOGGER = udi_interface.LOGGER

TEMP_MIN_F = 40
TEMP_MAX_F = 104


class Heater(udi_interface.Node):
    id = "heater"
    prefix = "heater"
    drivers = [
        {"driver": "ST", "value": 0, "uom": 25},    # state index
        {"driver": "GV0", "value": 0, "uom": 17},    # setpoint deg F
    ]

    def __init__(self, polyglot, primary, address, name,
                 omni=None, pool_id=None, equipment_id=None):
        super().__init__(polyglot, primary, address, name)
        self.omni = omni
        self.pool_id = pool_id
        self.equipment_id = equipment_id

    def apply_telemetry(self, telem_map):
        # <VirtualHeater systemId="3" Current-Set-Point="88" enable="1" whyHeaterIsOn="1" />
        # enable: 0 = user turned heater off, 1 = heater scheduled/on.
        # whyHeaterIsOn: non-zero while actively firing (stays 1 even at setpoint when enabled).
        elem = telem_map.get(self.equipment_id)
        if elem is None:
            return
        self.setDriver("ST", int(elem.get("enable", 0)))
        self.setDriver("GV0", int(elem.get("Current-Set-Point", 0)))

    def cmd_on(self, command):
        self.omni.set_heater_enable(self.pool_id, self.equipment_id, True)
        self.setDriver("ST", 1)

    def cmd_off(self, command):
        self.omni.set_heater_enable(self.pool_id, self.equipment_id, False)
        self.setDriver("ST", 0)

    def cmd_set_setpoint(self, command):
        temp = int(command.get("value", 0))
        temp = max(TEMP_MIN_F, min(TEMP_MAX_F, temp))
        self.omni.set_heater_temperature(self.pool_id, self.equipment_id, temp)
        self.setDriver("GV0", temp)

    commands = {
        "DON": cmd_on,
        "DOF": cmd_off,
        "SET_SP": cmd_set_setpoint,
    }
