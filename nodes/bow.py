"""Body of Water node: read-only water temperature and active flag."""
import udi_interface

LOGGER = udi_interface.LOGGER


class BodyOfWater(udi_interface.Node):
    id = "bow"
    prefix = "bow"
    drivers = [
        {"driver": "ST", "value": 0, "uom": 17},    # water temp, deg F
        {"driver": "GV0", "value": 0, "uom": 2},     # active / flow present
    ]

    def __init__(self, polyglot, primary, address, name, omni=None, pool_id=None):
        super().__init__(polyglot, primary, address, name)
        self.omni = omni
        self.pool_id = pool_id

    def apply_telemetry(self, telem_map):
        # telem_map is {systemId: xml_element} built in controller.update_telemetry()
        # <BodyOfWater systemId="1" waterTemp="88" flow="1" />
        elem = telem_map.get(self.pool_id)
        if elem is None:
            return
        self.setDriver("ST", int(elem.get("waterTemp", 0)))
        self.setDriver("GV0", int(elem.get("flow", 0)))

    commands = {}
