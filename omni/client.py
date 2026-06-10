"""
OmniClient: the only file that touches pyomnilogic-local directly.

Why this exists
---------------
udi_interface is threaded and calls our handlers synchronously (start, poll,
command callbacks). pyomnilogic-local is asyncio. Rather than make the whole
node server async, we run ONE asyncio event loop in a background thread and
marshal coroutines onto it with run_coroutine_threadsafe(). Every method below
is safe to call from any udi_interface callback.

>>> VERIFY BEFORE TRUSTING <<<
The method names on OmniLogicAPI (async_get_config / async_get_telemetry /
async_set_*) and their argument order have shifted across pyomnilogic-local
releases. After `pip install`, confirm the real surface with:

    python3 -c "from pyomnilogic_local.api import OmniLogicAPI; help(OmniLogicAPI)"

and adjust the thin wrappers in the "Hayward calls" section only. Nothing
outside this file should need to change.
"""
import asyncio
import threading

import udi_interface

LOGGER = udi_interface.LOGGER

# Local OmniLogic/OmniPL UDP control port (XML protocol).
DEFAULT_PORT = 10444
DEFAULT_TIMEOUT = 5.0

try:
    from pyomnilogic_local.api import OmniLogicAPI
except ImportError:
    OmniLogicAPI = None  # surfaced cleanly at start() instead of crashing import


class OmniClient:
    def __init__(self, host, port=DEFAULT_PORT, timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="omni-asyncio", daemon=True
        )
        self._api = None

    # ----- event-loop plumbing -------------------------------------------
    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro):
        """Block the calling (udi) thread until the coroutine completes."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self.timeout + 5)

    async def _async_init_api(self):
        # OmniLogicAPI.__init__ calls asyncio.get_running_loop(), so it must be
        # created from inside the running event loop, not from the udi thread.
        self._api = OmniLogicAPI((self.host, self.port), self.timeout)

    def start(self):
        if OmniLogicAPI is None:
            raise RuntimeError(
                "python-omnilogic-local is not installed; check install.sh / requirements.txt"
            )
        self._thread.start()
        # Instantiate the API inside the event loop so get_running_loop() succeeds.
        future = asyncio.run_coroutine_threadsafe(self._async_init_api(), self._loop)
        future.result(timeout=10)
        LOGGER.info("OmniClient targeting %s:%s", self.host, self.port)

    def stop(self):
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            LOGGER.exception("Error stopping asyncio loop")

    # ----- Hayward calls (VERIFY names/args against installed lib) --------
    def get_config(self):
        """Full MSP config (the equipment tree). Used for discovery."""
        return self._run(self._api.async_get_config())

    def get_telemetry(self):
        """Live state for all equipment. Used every shortPoll."""
        return self._run(self._api.async_get_telemetry())

    def set_equipment(self, pool_id, equipment_id, is_on):
        return self._run(
            self._api.async_set_equipment(pool_id, equipment_id, is_on)
        )

    def set_filter_speed(self, pool_id, equipment_id, speed_pct):
        return self._run(
            self._api.async_set_filter_speed(pool_id, equipment_id, int(speed_pct))
        )

    def set_heater_enable(self, pool_id, equipment_id, enabled):
        return self._run(
            self._api.async_set_heater_enable(pool_id, equipment_id, enabled)
        )

    def set_heater_temperature(self, pool_id, equipment_id, temp_f):
        return self._run(
            self._api.async_set_heater(pool_id, equipment_id, int(temp_f), "F")
        )
