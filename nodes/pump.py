"""
Pump node (variable-speed filter pump).

Drivers:  ST  = speed %, GV0 = running (0/1)
Commands: DON / DOF (on/off), SETSPD (set speed %)

OmniLogic VSPs are driven by percent at the local protocol level, so speed is
modeled as a percentage (0-100) rather than raw RPM.
"""
import time

import udi_interface

# OmniLogic filterState values that mean the pump is on because it was asked to be.
# Everything else is off or the controller winding down after an off
# (3/4/11 waiting to turn off, 5/6/8 heater/CSAD extend and cool-down, 7 suspended):
# the pump may still spin, but reporting those as running echoes a DON back to
# IoX, and the programs mirroring the pump then turn it straight back on.
RUNNING_STATES = {1, 2, 9, 10}  # on, priming, superchlorinate, force priming

# After we command the pump, ignore telemetry that disagrees for this long so a
# poll landing mid-transition can't flip GV0 and echo the opposite command.
COMMAND_GRACE_SECONDS = 90


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
        self._running = None      # running state last reported to IoX
        self._commanded = None    # running state we last commanded
        self._grace_until = 0.0

    def apply_telemetry(self, telem_map):
        # filterSpeed=0 when running on a schedule; lastSpeed holds the actual speed then.
        # filterSpeed>0 when a direct speed is set; lastSpeed holds the prior manual speed.
        # Use filterSpeed when non-zero, else fall back to lastSpeed.
        elem = telem_map.get(self.equipment_id)
        if elem is None:
            return
        running = int(elem.get("filterState", 0)) in RUNNING_STATES
        if (time.monotonic() < self._grace_until
                and self._commanded is not None and running != self._commanded):
            return
        if running:
            fs = int(elem.get("filterSpeed", 0))
            speed = fs if fs else int(elem.get("lastSpeed", 0))
        else:
            speed = 0
        self.setDriver("ST", speed)
        self.setDriver("GV0", 1 if running else 0)
        if self._ready and running != self._running:
            self.reportCmd("DON" if running else "DOF")
        self._running = running
        self._ready = True

    def _set_commanded(self, running):
        self._commanded = running
        self._running = running
        self._grace_until = time.monotonic() + COMMAND_GRACE_SECONDS

    def cmd_on(self, command):
        self.omni.set_equipment(self.pool_id, self.equipment_id, True)
        self._set_commanded(True)
        self.setDriver("GV0", 1)

    def cmd_off(self, command):
        self.omni.set_equipment(self.pool_id, self.equipment_id, False)
        self._set_commanded(False)
        self.setDriver("GV0", 0)
        self.setDriver("ST", 0)

    def cmd_set_speed(self, command):
        speed = int(command.get("value", 0))
        speed = max(0, min(100, speed))
        self.omni.set_filter_speed(self.pool_id, self.equipment_id, speed)
        self._set_commanded(speed > 0)
        self.setDriver("ST", speed)
        self.setDriver("GV0", 1 if speed > 0 else 0)

    commands = {
        "DON": cmd_on,
        "DOF": cmd_off,
        "SETSPD": cmd_set_speed,
    }
