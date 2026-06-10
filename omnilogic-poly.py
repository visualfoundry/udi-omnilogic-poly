#!/usr/bin/env python3
"""
Hayward OmniLogic (local protocol) node server for Polyglot v3 / PG3 on eisy.

Entry point: builds the Interface, hands control to the Controller node,
then runs forever. All real work happens in nodes/ and omni/.
"""
import sys

import udi_interface

from nodes.controller import Controller

LOGGER = udi_interface.LOGGER

VERSION = "0.1.0"

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        # NOTE: confirm start() signature for your installed udi_interface.
        # Recent PG3 accepts a version string here.
        polyglot.start(VERSION)

        # The controller registers its own event subscriptions in __init__.
        Controller(polyglot, "controller", "controller", "OmniLogic")

        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt; shutting down.")
        sys.exit(0)
    except Exception:
        LOGGER.exception("Fatal error in main")
        sys.exit(1)
