# OmniLogic (Local) — PG3 Node Server for eisy

Brings a Hayward OmniLogic/OmniPL pool controller into IoX over Hayward's
**local UDP protocol** (port 10444), using the reverse-engineered
[`pyomnilogic-local`](https://pypi.org/project/pyomnilogic-local/) library.
No cloud account, no Hayward servers in the path.

This is a **starter scaffold**, not a finished plugin. The structure is solid;
a handful of library specifics are marked `>>> VERIFY <<<` and must be checked
against the versions that actually install on your eisy.

## Architecture

```
omnilogic-poly.py        entry point: builds Interface, starts Controller
nodes/
  controller.py          config, OmniClient lifecycle, discovery, polling
  bow.py                 Body of Water  (read-only temp/active)
  pump.py                VSP pump       (DON/DOF/SETSPD)
  heater.py              heater         (DON/DOF/SET_SP)
omni/
  client.py              the ONLY file that touches pyomnilogic-local
profile/                 IoX nodedefs / editors / NLS
server.json              PG3 manifest
install.sh               pip install hook
requirements.txt
```

The one non-obvious design point: **udi_interface is threaded, pyomnilogic-local
is asyncio.** `omni/client.py` runs a single asyncio loop in a background thread
and marshals coroutines onto it with `run_coroutine_threadsafe()`, exposing plain
synchronous methods to the rest of the server. Keep all Hayward calls inside that
file so the async boundary stays in one place.

Data flow: `start()` -> `get_config()` -> build child nodes; then every
`shortPoll` -> `get_telemetry()` once -> each child reads its own slice via
`apply_telemetry()`. Commands from IoX call straight into `OmniClient`.

## What is reliable vs. what to verify

Reliable: the udi_interface lifecycle/subscription pattern, the node/driver/command
structure, the profile layout, and the async bridge.

Verify (all marked in-code):
1. `pyomnilogic-local` method names + arg order in `omni/client.py`
   (`async_get_config`, `async_get_telemetry`, `async_set_*`).
2. The model/dict shape returned by config + telemetry — wire
   `Controller._build_from_config()` and each node's `apply_telemetry()`.
3. `udi_interface.Interface.start()` signature and the exact `server.json`
   schema for your PG3 version.

Inspect the real surface before wiring:
```
python3 -c "from pyomnilogic_local.api import OmniLogicAPI; help(OmniLogicAPI)"
```

## Bring-up

1. Confirm no existing OmniLogic node server in the PG3 store / UD forums first.
2. Get the controller's LAN IP (set a DHCP reservation for it).
3. Load this as a local/dev node server in PG3, set `host` in Configuration.
4. First run uses example nodes (so it loads); replace discovery + telemetry
   wiring once you've inspected real config/telemetry payloads.
5. Add the remaining equipment types — chlorinator, lights, relays — by copying
   `pump.py`/`heater.py`; they follow the identical driver+command mold.

## Rollback to cloud

If local proves unworkable on your firmware, the node tree and profile stay the
same — only `omni/client.py` swaps to the HAAPI cloud wrapper (`omnilogic` on
PyPI) and `host`/`port` params become Hayward account credentials.
