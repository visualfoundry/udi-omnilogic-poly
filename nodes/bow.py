"""Body of Water node: water temp, chemistry, air temp, pump power, salt, heater/chlor state."""
import udi_interface

LOGGER = udi_interface.LOGGER


class BodyOfWater(udi_interface.Node):
    id = "bow"
    prefix = "bow"
    drivers = [
        {"driver": "ST",  "value": 0, "uom": 17},   # water temp °F
        {"driver": "GV0", "value": 0, "uom": 2},    # active / flow present
        {"driver": "GV1", "value": 0, "uom": 56},   # pH (prec 1)
        {"driver": "GV2", "value": 0, "uom": 56},   # ORP mV
        {"driver": "GV3", "value": 0, "uom": 17},   # air temp °F
        {"driver": "GV4", "value": 0, "uom": 56},   # pump power W
        {"driver": "GV5", "value": 0, "uom": 56},   # instant salt PPM
        {"driver": "GV6", "value": 0, "uom": 56},   # avg salt PPM
        {"driver": "GV7", "value": 0, "uom": 2},    # physical heater firing
        {"driver": "GV8", "value": 0, "uom": 2},    # chlorinator alert
        {"driver": "GV9", "value": 0, "uom": 2},    # chlorinator error
    ]

    def __init__(self, polyglot, primary, address, name, omni=None, pool_id=None):
        super().__init__(polyglot, primary, address, name)
        self.omni = omni
        self.pool_id = pool_id

    def apply_telemetry(self, telem_map):
        # telem_map is {systemId: xml_element} built in controller.update_telemetry()
        elem = telem_map.get(self.pool_id)
        if elem is None:
            return
        self.setDriver("ST",  int(elem.get("waterTemp", 0)))
        self.setDriver("GV0", int(elem.get("flow", 0)))

        # Backyard element (systemId=0) carries air temperature.
        backyard = telem_map.get(0)
        if backyard is not None:
            self.setDriver("GV3", int(backyard.get("airTemp", 0)))

        # Remaining drivers come from sub-equipment; find by XML tag (single-pool install).
        for e in telem_map.values():
            tag = e.tag
            if tag == "CSAD":
                self.setDriver("GV1", float(e.get("ph", 0.0)))
                self.setDriver("GV2", int(e.get("orp", 0)))
            elif tag == "Filter":
                self.setDriver("GV4", int(e.get("power", 0)))
            elif tag == "Heater":
                self.setDriver("GV7", int(e.get("heaterState", 0)))
            elif tag == "Chlorinator":
                self.setDriver("GV5", int(e.get("instantSaltLevel", 0)))
                self.setDriver("GV6", int(e.get("avgSaltLevel", 0)))
                self.setDriver("GV8", int(e.get("chlrAlert", 0)))
                self.setDriver("GV9", int(e.get("chlrError", 0)))

    commands = {}
