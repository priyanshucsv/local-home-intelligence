# Luminas Local Home — Architecture v0.6

## 1. Runtime flow

```text
Virtual / future physical device
        ↓
Device capability contract
        ↓
Local event / authenticated local message
        ↓
Context Engine
        ↓
Home State
        ↓
Deterministic Local Reasoner
        ↓
Decision Engine
        ↓
Capability interface
        ↓
Virtual device / future hardware adapter
```

## 2. Layer by layer

### `core/event_bus.py`
In-process event transport with event IDs, timestamps, bounded history and
duplicate rejection (`inject_duplicate` proves replayed event IDs are refused).

### `core/device_network.py`
Authenticated local transport: unique identity, trust/revocation, HMAC-SHA256,
recipient binding, sequence monotonicity, replay and sequence-gap detection,
payload size/type validation, malformed-frame rejection and the local-only
route guard. Identities are registered at runtime with fresh ephemeral
**demo-only** secrets (`secrets.token_hex(32)`); the repository contains no
reusable production credentials.

### `core/home_state.py`
Single runtime source of truth: home mode, occupancy evidence, temperature and
its availability, alerts, decisions, simulation clock and per-device state.
Every device is labeled `DIGITAL_TWIN`.

### `intelligence/context.py`
Converts observations into context. Occupancy is supported by local evidence
(door entry, CCTV resident identity, motion) rather than a UI toggle. It also
consumes `sensor_conflict` events and surfaces **occupancy evidence conflict**
as an attention state instead of silently picking a side.

### `intelligence/reasoner.py`
Deterministic, structured explanation only:

```text
OBSERVATION  Resident detected at front door.
CONTEXT      Home appears occupied.
OBSERVATION  Temperature = 31.4°C.
RULE         Temperature exceeds the comfort threshold.
ACTION       Activate comfort mode.
RESULT       AC power on: SUCCESS
```

No hidden chain-of-thought is exposed and no model API is called. The correct
public terms are **Local Reasoning**, **Deterministic Decision Engine** and
**Structured Decision Explanation** — not "AI reasoning" by an LLM.

### `intelligence/decision.py`
Local deterministic policies (resident / guest / energy-saving / empty-home /
safe-hold) written against the hardware-independent contracts. When the room
reaches the AC setpoint the engine keeps comfort mode active and maintains the
target instead of flapping the AC off.

## 3. Device contracts

`devices/contracts.py` defines the boundary the Brain depends on:

`Device` · `Sensor` · `Actuator` · `Camera` · `ClimateController` ·
`LightController` · `DoorSensor`

The current implementations are Digital Twin devices (`kind="DIGITAL_TWIN"`);
the decision layer cannot tell the difference and must never need to.

## 4. Digital Twin devices

`devices/` contains `CCTV`, `TemperatureSensor`, `MotionSensor`, `EntryDoor`,
`AirConditioner` and `Light`. Each exposes availability/health and state; a
device that is offline **withholds** its events rather than fabricating them.

## 5. Simulation clock

`LuminasRuntime.advance(seconds)` is the deterministic simulation clock. It
advances contextual time, vacancy timing and the AC thermal state, and
optionally emits a fresh temperature observation. It is intentionally separate
from wall-clock time so tests, CLI scenarios and recorded demos are
deterministic. The primary dashboard demo ticks 10 simulated seconds per
1.1 real seconds, so cooling 31.4 °C → 24 °C takes about 7 seconds and the
whole demo about 12 seconds.

## 6. Failure model

Failures are injected inside the same runtime boundaries:

```text
offline device · stale data · invalid data · conflicting evidence
duplicate event · malformed frame · unknown device · blocked external route
```

A failure becomes unavailable/failed state plus an audit/security event.
Nothing is silently replaced with invented values: if temperature is
unavailable, temperature-based automation is **withheld**.

## 7. Privacy measurement

`security/privacy.py` and `security/local_only.py` make an **application-level**
claim only: dependency flags, blocked external attempts, bytes recorded at
Luminas transport boundaries and a source scan for forbidden cloud/API import
roots. They do **not** perform host NIC packet capture and no host-level or
OS-level isolation is claimed.

## 8. Demo state machine

`core/runtime.py::DemoController` owns the public demo:

```text
IDLE → RESETTING → DOOR_OPEN → DETECTING_RESIDENT → CONFIRMING_OCCUPANCY
     → EVALUATING_COMFORT → ACTIVATING_COMFORT → AC_COOLING → COMPLETE
                                (any failure → FAILED)
```

The demo resets the Digital Twin to the canonical hot-empty start, replays the
same deterministic sequence every run and exposes `demo_state` so the dashboard
button/progress reflect **actual runtime state** — the UI polls the backend and
never uses a fixed timeout as the source of truth.

## 9. Hardware replacement path

```text
TODAY
VirtualTemperatureSensor → Sensor contract → Luminas Brain

FUTURE
BME280Adapter / other local driver → Sensor contract → Luminas Brain
```

The same pattern applies to camera, motion, door, AC and light adapters.
Hardware-specific concerns (GPIO pins, mains voltage, vendor SDKs, cloud
credentials) belong at the adapter boundary and nowhere else. See
`hardware/HARDWARE_BRIDGE.md` for the concrete replacement map.
