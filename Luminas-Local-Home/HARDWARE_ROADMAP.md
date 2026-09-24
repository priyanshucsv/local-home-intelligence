# Hardware Roadmap — Luminas Local Home

## Current milestone

**v0.6 — Software Digital Twin.** All device behavior is simulated. No physical
hardware is connected, and **no physical component, BOM item or wiring scheme
mentioned below has been validated**. Every physical claim remains future work.

## Candidate physical classes (vendor-neutral, unvalidated)

- local SBC / mini-PC class compute
- local USB or IP camera
- temperature sensor (I²C/1-wire sensor class)
- motion sensor (PIR/mmWave class)
- magnetic/reed or equivalent entry sensor
- IR transmitter or manufacturer-supported local AC interface
- certified isolated lighting/actuator interface
- local network switch/AP with no required cloud uplink

Specific vendors, boards and BOM items are chosen only after bench testing and
safety review. Naming a class does **not** validate it.

## Replacement map

| Digital Twin | Contract | Future adapter boundary |
|---|---|---|
| `TemperatureSensor` | `Sensor` | `TemperatureSensorAdapter` |
| `MotionSensor` | `Sensor` | `MotionSensorAdapter` |
| `EntryDoor` | `DoorSensor` | `DoorSensorAdapter` |
| `CCTV` | `Camera` | `CameraAdapter` |
| `AirConditioner` | `ClimateController` | `ClimateControllerAdapter` |
| `Light` | `LightController` | `LightControllerAdapter` |

The Brain/Decision Engine must remain unchanged when a Digital Twin is replaced
with a validated physical adapter. `hardware/adapters.py` already sketches the
adapter classes and refuses to simulate (`NotImplementedError`) so nothing can
pretend to be hardware.

## Electrical safety boundary

The v0.6 repository intentionally contains **no mains control of any kind**.

Mains-voltage interfaces require appropriate **isolation, protection, ratings,
enclosure, wiring, connectors and qualified physical testing**. Do not connect
an SBC GPIO pin directly to mains voltage. AC/light interfaces are
safety-critical hardware and must be validated independently from this software
demo by qualified personnel.

## Physical validation milestone

Build the first bench slice in layers:

```text
LOCAL COMPUTE (SBC class)
  ├── temperature sensor + motion sensor (low voltage)
  ├── local camera
  └── entry sensor
        ↓
    Luminas Brain (unchanged)
        ↓
    ONE isolated actuator interface → safe bench load
```

## Physical validation checklist (all items pending)

1. validate the power/control interface on a safe bench load
2. verify galvanic isolation and ratings
3. verify watchdog/recovery behavior
4. verify local device identity provisioning (real secrets, not demo secrets)
5. verify authenticated messages on the chosen transport
6. verify operation with the internet path physically absent
7. verify failure handling with the real device disconnected
8. document the exact tested hardware revision

## Sponsorship / partner handoff

A hardware company can integrate at the adapter boundary without taking
ownership of the Brain architecture. The key integration question is:

```text
Can the hardware expose a local implementation of the existing capability contract?
```

That keeps the project vendor-neutral while making the integration point
concrete. See `hardware/HARDWARE_BRIDGE.md` for the exact replacement path.
