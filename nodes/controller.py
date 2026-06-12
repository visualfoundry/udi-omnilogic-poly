"""
Controller node — owns configuration, the OmniClient, discovery, and polling.

On START it reads the controller IP from custom params, connects, discovers
the equipment tree, and builds child nodes. On each shortPoll it pulls
telemetry once and pushes values into the children.
"""
import os
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
load_dotenv()  # no-op on eisy where .env won't exist

import udi_interface

from omni.client import OmniClient
from nodes.bow import BodyOfWater
from nodes.pump import Pump
from nodes.heater import Heater
from nodes.chlorinator import Chlorinator

LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom


class Controller(udi_interface.Node):
    id = "controller"
    drivers = [
        {"driver": "ST", "value": 0, "uom": 2},    # 0/1 online
        {"driver": "GV0", "value": 0, "uom": 56},   # equipment node count
    ]

    def __init__(self, polyglot, primary, address, name):
        super().__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.omni = None
        self.host = os.environ.get("OMNI_HOST")
        self.port = int(os.environ.get("OMNI_PORT", 10444))
        self.params = Custom(polyglot, "customparams")
        self.children = {}  # system_id -> node

        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameter_handler)
        polyglot.subscribe(polyglot.POLL, self.poll)
        polyglot.subscribe(polyglot.STOP, self.stop)

        polyglot.ready()
        polyglot.addNode(self)

    # ----- configuration --------------------------------------------------
    def parameter_handler(self, params):
        self.params.load(params)
        # Ensure the fields exist in PG3's DB so they appear in the Configuration tab.
        # Custom.__setitem__ auto-saves to PG3 on each assignment.
        if 'host' not in self.params:
            self.params['host'] = ''
        if 'port' not in self.params:
            self.params['port'] = '10444'

        # PG3 custom params take priority; fall back to .env / environment variables.
        new_host = self.params.get("host") or os.environ.get("OMNI_HOST")
        pg3_port = self.params.get("port")
        new_port = int(pg3_port) if pg3_port else int(os.environ.get("OMNI_PORT", 10444))

        self.poly.Notices.clear()
        if not new_host:
            self.poly.Notices["host"] = (
                "Set 'host' (OmniLogic controller IP) in Configuration, then restart."
            )
            return

        host_changed = (new_host != self.host or new_port != self.port)
        self.host = new_host
        self.port = new_port

        if self.omni is None:
            self.start()
        elif host_changed:
            LOGGER.info("Host/port changed; restarting OmniClient")
            self.omni.stop()
            self.omni = None
            self.children.clear()
            self.start()

    # ----- lifecycle ------------------------------------------------------
    def start(self):
        LOGGER.info("Controller starting")
        if not self.host:
            LOGGER.warning("No host configured; waiting for custom params.")
            return
        if self.omni is not None:
            LOGGER.info("OmniClient already running.")
            return
        try:
            self.omni = OmniClient(self.host, self.port)
            self.omni.start()
            self.setDriver("ST", 1)
            self.discover()
            # Request PG3 to (re)start the poll timers. Guards against
            # the case where PG3's startNs threw after spawning this
            # process, which would leave the NS running but with no
            # active shortPoll timer.
            cfg = self.poly.config or {}
            self.poly.send({
                'polls': {
                    'short': cfg.get('shortPoll', 30),
                    'long': cfg.get('longPoll', 300),
                }
            }, 'system')
        except Exception:
            LOGGER.exception("Failed to start OmniClient")
            self.setDriver("ST", 0)

    def stop(self):
        if self.omni:
            self.omni.stop()
        self.setDriver("ST", 0)

    # ----- discovery ------------------------------------------------------
    def discover(self):
        """
        Build child nodes from the MSP config.

        >>> VERIFY <<< The attribute path below (config.backyard.bodies_of_water,
        bow.systems, etc.) reflects pyomnilogic-local's pydantic models, whose
        names vary by version. Inspect a real config first:

            python3 -c "from pyomnilogic_local.api import OmniLogicAPI; \
              import asyncio; \
              print(asyncio.run(OmniLogicAPI('<IP>',10444,5).async_get_config()))"

        Until that's wired, the except branch builds a representative tree so
        the node server loads and you can see nodes in the admin console.
        """
        try:
            config = self.omni.get_config()
            self._build_from_config(config)
        except Exception:
            LOGGER.exception("Config parse not yet wired; using example nodes")
            self._build_example_nodes()

        self.setDriver("GV0", len(self.children))

    def _build_from_config(self, config_xml):
        root = ET.fromstring(config_xml)
        backyard = root.find("Backyard")
        for bow_elem in backyard.findall("Body-of-water"):
            bow_id = int(bow_elem.findtext("System-Id"))
            bow_name = bow_elem.findtext("Name")
            self._add(BodyOfWater, bow_id, bow_name, pool_id=bow_id)

            flt = bow_elem.find("Filter")
            if flt is not None:
                flt_id = int(flt.findtext("System-Id"))
                flt_name = flt.findtext("Name")
                self._add(Pump, flt_id, flt_name, pool_id=bow_id, equipment_id=flt_id)

            heater = bow_elem.find("Heater")
            if heater is not None:
                htr_id = int(heater.findtext("System-Id"))
                self._add(Heater, htr_id, f"{bow_name} Heater",
                          pool_id=bow_id, equipment_id=htr_id)

            chlor = bow_elem.find("Chlorinator")
            if chlor is not None:
                chlor_id = int(chlor.findtext("System-Id"))
                self._add(Chlorinator, chlor_id, f"{bow_name} Chlorinator",
                          pool_id=bow_id, equipment_id=chlor_id)

    def _build_example_nodes(self):
        self._add(BodyOfWater, 7, "Pool", pool_id=7)
        self._add(Pump, 8, "Filter Pump", pool_id=7, equipment_id=8)
        self._add(Heater, 9, "Heater", pool_id=7, equipment_id=9)
        self._add(Chlorinator, 6, "Chlorinator", pool_id=7, equipment_id=6)

    def _add(self, cls, system_id, name, **kw):
        address = f"{cls.prefix}{system_id}"
        node = cls(self.poly, self.address, address, name, omni=self.omni, **kw)
        self.poly.addNode(node)
        self.children[system_id] = node
        return node

    # ----- polling --------------------------------------------------------
    def poll(self, polltype):
        if "shortPoll" in polltype:
            self.update_telemetry()

    def update_telemetry(self):
        if not self.omni:
            return
        try:
            telemetry = self.omni.get_telemetry()
        except Exception:
            LOGGER.exception("Telemetry fetch failed")
            self.setDriver("ST", 0)
            return

        self.setDriver("ST", 1)
        telem_root = ET.fromstring(telemetry)
        telem_map = {
            int(e.get("systemId")): e
            for e in telem_root
            if e.get("systemId") is not None
        }
        for system_id, node in self.children.items():
            try:
                node.apply_telemetry(telem_map)
            except Exception:
                LOGGER.exception("apply_telemetry failed for %s", system_id)

    commands = {"DISCOVER": discover}
