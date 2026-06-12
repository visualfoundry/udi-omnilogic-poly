"""
Chlorinator node (salt-cell chlorine generator).

Drivers:  ST  = enabled (0/1), GV0 = timed output percent (0–100%)
Commands: DON / DOF (enable/disable)

Level control is not available in pyomnilogic-local 0.0.5; only on/off
is supported via set_equipment. GV0 is read-only from telemetry.

>>> VERIFY <<< telemetry attribute names on real hardware:
  <Chlorinator systemId="6" enable="1" timedPercent="50" ... />
The attribute "enable" and "timedPercent" are best-effort guesses from
the OmniLogic XML protocol. Capture a real telemetry payload to confirm.
"""
import udi_interface

LOGGER = udi_interface.LOGGER


class Chlorinator(udi_interface.Node):
    id = "chlorinator"
    prefix = "chlor"
    drivers = [
        {"driver": "ST", "value": 0, "uom": 2},     # enabled (bool)
        {"driver": "GV0", "value": 0, "uom": 51},    # timed output %
    ]

    def __init__(self, polyglot, primary, address, name,
                 omni=None, pool_id=None, equipment_id=None):
        super().__init__(polyglot, primary, address, name)
        self.omni = omni
        self.pool_id = pool_id
        self.equipment_id = equipment_id

    def apply_telemetry(self, telem_map):
        # >>> VERIFY <<< element tag and attribute names from live controller
        elem = telem_map.get(self.equipment_id)
        if elem is None:
            return
        self.setDriver("ST", int(elem.get("enable", 0)))
        self.setDriver("GV0", int(elem.get("timedPercent", 0)))

    def cmd_on(self, command):
        self.omni.set_equipment(self.pool_id, self.equipment_id, True)
        self.setDriver("ST", 1)

    def cmd_off(self, command):
        self.omni.set_equipment(self.pool_id, self.equipment_id, False)
        self.setDriver("ST", 0)

    commands = {
        "DON": cmd_on,
        "DOF": cmd_off,
    }
