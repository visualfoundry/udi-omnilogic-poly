"""
Pump node (variable-speed filter pump).

Drivers:  ST  = speed %, GV0 = running (0/1)
Commands: DON / DOF (on/off), SETSPD (set speed %)

OmniLogic VSPs are driven by percent at the local protocol level, so speed is
modeled as a percentage (0-100) rather than raw RPM.
"""
import udi_interface


class Pump(udi_interface.Node):
    id = "pump"
    prefix = "pump"
    drivers = [
        {"driver": "ST", "value": 0, "uom": 51},    # speed %
        {"driver": "GV0", "value": 0, "uom": 2},     # running
    ]

    def __init__(self, polyglot, primary, address, name,
                 omni=None, pool_id=None, equipment_id=None):
        super().__init__(polyglot, primary, address, name)
        self.omni = omni
        self.pool_id = pool_id
        self.equipment_id = equipment_id
        self._ready = False

    def apply_telemetry(self, telem_map):
        # filterSpeed=0 when running on a schedule; lastSpeed holds the actual speed then.
        # filterSpeed>0 when a direct speed is set; lastSpeed holds the prior manual speed.
        # Use filterSpeed when non-zero, else fall back to lastSpeed.
        elem = telem_map.get(self.equipment_id)
        if elem is None:
            return
        filter_state = int(elem.get("filterState", 0))
        if filter_state:
            fs = int(elem.get("filterSpeed", 0))
            speed = fs if fs else int(elem.get("lastSpeed", 0))
        else:
            speed = 0
        self.setDriver("ST", speed)
        if self.setDriver("GV0", filter_state) and self._ready:
            self.reportCmd("DON" if filter_state else "DOF")
        self._ready = True

    def cmd_on(self, command):
        self.omni.set_equipment(self.pool_id, self.equipment_id, True)
        self.setDriver("GV0", 1)

    def cmd_off(self, command):
        self.omni.set_equipment(self.pool_id, self.equipment_id, False)
        self.setDriver("GV0", 0)
        self.setDriver("ST", 0)

    def cmd_set_speed(self, command):
        speed = int(command.get("value", 0))
        speed = max(0, min(100, speed))
        self.omni.set_filter_speed(self.pool_id, self.equipment_id, speed)
        self.setDriver("ST", speed)
        self.setDriver("GV0", 1 if speed > 0 else 0)

    commands = {
        "DON": cmd_on,
        "DOF": cmd_off,
        "SETSPD": cmd_set_speed,
    }
