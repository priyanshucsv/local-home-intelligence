# Hardware Bridge — Luminas Local Home v0.6

v0.6 is a **software Digital Twin**. This document answers exactly one question:
**"If hardware support arrives tomorrow, what do I replace?"** The answer is
always the same shape — swap the Digital Twin implementation behind its existing
capability contract. The Brain, reasoning and decision logic never change.

## Temperature

```text
VirtualTemperatureSensor (devices/sensors.py)
         ↓
Sensor contract (devices/contracts.py)
         ↓
Real sensor adapter (hardware/adapters.py::TemperatureSensorAdapter)
         ↓
Real temperature sensor
```

Replace: `LuminasRuntime.temperature` construction only. The context engine,
decision engine and stale-data handling are untouched.

## AC

```text
VirtualAC (devices/ac.py)
   ↓
ClimateController contract
   ↓
IR / local AC adapter (hardware/adapters.py::ClimateControllerAdapter)
   ↓
Real AC
```

Replace: the `LuminasRuntime.ac` construction only. Comfort policies, setpoint
handling and the gradual thermal model's *role* stay; the adapter reports real
state instead of simulating it.

## Camera

```text
Virtual CCTV (devices/cctv.py)
   ↓
Camera contract
   ↓
Local camera adapter (hardware/adapters.py::CameraAdapter)
   ↓
Real camera (local inference, local events only)
```

Replace: the `LuminasRuntime.cctv` construction only. Detection events still
flow through the same authenticated local mesh and event bus.

## Motion / Door / Lights

```text
VirtualMotionSensor → Sensor        → MotionSensorAdapter
VirtualDoor         → DoorSensor    → DoorSensorAdapter
VirtualLight        → LightController → LightControllerAdapter
```

## Rules that do not change

- The Brain depends on `devices/contracts.py`, never on device class names,
  vendor SDKs, GPIO pins or cloud credentials.
- `hardware/adapters.py` raises `NotImplementedError` by design: an adapter that
  has not been physically validated cannot silently pretend to work.
- Identity/secrets on real hardware are provisioned per device at setup time —
  the demo-only ephemeral runtime secrets are replaced, not reused.
- Every failure path (offline, stale, malformed, untrusted) applies to real
  devices exactly as it does to the Digital Twin.

## Safety boundary

This repository contains **no mains control**. Mains interfaces require
appropriately rated isolation, protection, enclosures and qualified physical
testing. See `HARDWARE_ROADMAP.md` for the safety checklist.

## Physical validation goal

Replace **one** Digital Twin at a time, verify the adapter against its contract,
verify authenticated local messaging, and exercise the existing failure/audit
paths with the physical device disconnected and reconnected. Only after that
does the project describe the corresponding device as "validated".
