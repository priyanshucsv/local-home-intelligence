# Luminas Local Home v0.6

## Local Home Digital Twin — Software Release Candidate

Luminas Local Home is a **local-first, privacy-first home intelligence runtime**.
v0.6 is a **software Digital Twin**: a complete, testable home intelligence loop —
events, context, reasoning, decisions and device actions — running entirely in one
local process with **no cloud, no paid API, no external AI service and no internet**.

> **Honesty statement:** all devices in v0.6 are Digital Twin components.
> No physical camera, sensor, AC or lighting controller is connected or claimed.
> Physical validation is the next milestone.

The core loop:

```text
DEVICE → LOCAL EVENT → LOCAL BRAIN → LOCAL DECISION → DEVICE ACTION
```

---

## The problem

Consumer smart homes push raw sensor data and camera footage to vendor clouds.
Luminas takes the opposite position: the intelligence lives **inside the home**,
devices authenticate to it locally, and nothing leaves the process. v0.6 proves
the software architecture end-to-end before a single wire is connected.

## Design principle

The Brain depends on **capability contracts**, never on device implementations:

```text
TODAY
Luminas Brain → ClimateController → Virtual AC (Digital Twin)

FUTURE
Luminas Brain → ClimateController → IR AC Adapter → REAL AC
```

The same principle applies to cameras, temperature sensors, motion sensors,
doors and lights. Replacing a Digital Twin with a physical adapter does not
touch the Brain, the reasoning layer or the decision engine.

## Architecture

```text
DEVICE (Digital Twin)
      ↓ local event (event bus, event IDs, deduplication, bounded history)
CONTEXT (occupancy & evidence from door / CCTV / motion)
      ↓
LOCAL REASONING (deterministic, structured OBSERVATION → CONTEXT → RULE → ACTION → RESULT)
      ↓
DECISION ENGINE (local policies over hardware-independent contracts)
      ↓ authenticated local command (HMAC-SHA256, sequence-validated)
DEVICE ACTION (Digital Twin state + telemetry)
```

Supporting layers:

- `core/event_bus.py` — local event transport with IDs, dedup and bounded history
- `core/device_network.py` — authenticated local mesh (HMAC-SHA256, replay, gap, tamper checks)
- `core/home_state.py` — single source of truth for the simulated home
- `intelligence/` — context engine, deterministic reasoner, decision engine
- `security/` — audit log, privacy monitor, local-only validator, threat suite, shared validation service
- `simulation/` — deterministic scenarios and the Digital Twin house view
- `hardware/` — the future physical adapter boundary (documented, deliberately unimplemented)

## Digital Twin, not a mock UI

The dashboard renders **runtime state only**. There are no decorative numbers:

- occupancy comes from door + CCTV + motion evidence in `ContextEngine`
- temperature comes from the virtual sensor and the AC thermal model
- every device card reports its real availability and state, labeled `DIGITAL TWIN`
- the demo button reflects the actual backend `demo_state`, not a timer

### Simulated cooling stays physical-shaped

The virtual AC changes room temperature gradually (0.14 °C per simulated second
toward the 24 °C setpoint) and stops at the target. The demo shows 31.4 °C →
24.0 °C step by step, exactly as the runtime computes it.

## Primary demo — Resident returns to a hot home

Initial state (always reset deterministically by the demo itself):

```text
Occupancy EMPTY · Temperature 31.4°C · AC OFF · Lights OFF · Door CLOSED
Internet NONE · Cloud NONE · External API NONE
```

Then:

```text
DOOR_OPENED → RESIDENT_DETECTED → OCCUPANCY_CONFIRMED → TEMPERATURE = 31.4°C
→ COMFORT_THRESHOLD_EXCEEDED → COMFORT_MODE_ACTIVATED → AC_POWER_ON
→ AC_TARGET = 24°C → LIGHT_ON → SIMULATED ROOM COOLING → TARGET REACHED
```

**You never reset manually — the RESIDENT RETURNS button does everything.**

## Security model (inherited from v0.5, still enforced)

- authenticated device identities (fresh ephemeral **demo-only** secrets per runtime)
- HMAC-SHA256 frame signing, recipient binding
- monotonic sequence validation, replay and sequence-gap rejection
- tamper, bad-signature, unknown-identity and revoked-device rejection
- payload size/type validation, malformed-frame rejection
- external route blocking at the application transport boundary
- full local audit logging

The secrets in `core/runtime.py` are generated at runtime (`secrets.token_hex(32)`),
are different on every start, and are **not production credentials**. No production
key provisioning exists or is claimed.

## Privacy measurement — precise scope

The validation reports exactly this:

```text
CORE NETWORK DEPENDENCY     NONE
CLOUD DEPENDENCY            NONE
EXTERNAL API DEPENDENCY     NONE
EXTERNAL TRANSMISSION       0 B
MEASUREMENT SCOPE           APPLICATION LEVEL
```

with the note: *Application-level measurement. Host-level packet capture is not claimed.*

This is not a security certification. The counters cover what the Luminas process
itself sends through its guarded transport boundaries; the OS's own traffic is out of scope.

## Failure scenarios (real, not decorative)

Each scenario runs on a fresh runtime and produces real state changes plus audit entries:

| Scenario | Behavior |
|---|---|
| Temperature failure | TEMP-01 → UNAVAILABLE; temperature-based automation withheld; no invented values |
| CCTV offline | no `RESIDENT_DETECTED` can be fabricated; other sensors keep working |
| AC failure | comfort decision still made; `AC command → FAILED` visible and audited; lights unaffected |
| Stale sensor | freshness window exceeded → data invalidated, automation withheld |
| Unknown person | `SECURITY ATTENTION`; resident comfort automation NOT triggered |
| Conflicting sensors | `OCCUPANCY EVIDENCE CONFLICT` surfaced as attention, not false certainty |
| Duplicate event | rejected by event-bus deduplication |
| Malformed message | rejected by the authenticated mesh |
| Unknown device | rejected by identity registry |
| External route block | blocked; external bytes remain 0 at the application boundary |

## Running

```bash
# dashboard (primary demo path)
python dashboard.py            # → http://127.0.0.1:8765 (localhost only)

# the single authoritative validation (unit tests actually executed)
python main.py --validate

# one deterministic scenario
python main.py --scenario resident_returns_hot

# full unit suite
python -m unittest discover -s tests -v
```

Windows one-click: `START_DASHBOARD.bat` and `RUN_FULL_VALIDATION.bat`
(both call the same code paths as the commands above — there is only one
validation implementation, in `security/validation.py`).

The project uses **only the Python standard library** (`requirements.txt` is
intentionally dependency-free) and runs fully offline.

## What is real / simulated / not validated

### WORKING NOW (software)
local runtime · event bus with dedup · context engine · deterministic reasoning ·
decision engine · virtual devices · authenticated local messaging · failure
simulation · audit logging · application-level local-only validation · dashboard ·
Demo Mode with real runtime demo state · tests

### SIMULATED (Digital Twin)
camera detection · temperature sensor · motion sensor · door · AC · lights ·
room cooling · all physical device I/O

### NOT PHYSICALLY VALIDATED
real camera · real sensors · real AC · real light controller · electrical wiring ·
SBC deployment · real-world network isolation · physical safety · appliance compatibility

### NEXT STEP
Physical validation using real hardware adapters behind the existing contracts.
See `HARDWARE_ROADMAP.md` and `hardware/HARDWARE_BRIDGE.md`.

## Documentation

- `ARCHITECTURE.md` — runtime flow, contracts, simulation clock, failure model
- `DEMO_GUIDE.md` — recording script, timing, narration, disclaimers
- `HARDWARE_ROADMAP.md` — vendor-neutral physical plan and safety boundary
- `hardware/HARDWARE_BRIDGE.md` — exactly what to replace when hardware arrives
- `hardware/PROTOTYPE_ARCHITECTURE.md` — future SBC stack sketch

## Project status

**v0.6 — Software Digital Twin release candidate.** All validation passes
(`python main.py --validate` → exit code 0). The project is honest about its
boundary: working local software, simulated devices, physical validation next.
