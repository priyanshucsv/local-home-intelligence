# Physical Prototype Architecture — v0.6

## Status

The software architecture is locked for a **vendor-neutral physical validation path**. The current release is still 100% software / Digital Twin.

```text
                 ┌──────────────────────────────┐
                 │       LOCAL COMPUTE          │
                 │       Luminas Brain          │
                 │     (future physical SBC)    │
                 └──────────────┬───────────────┘
                                │
                      authenticated local bus
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
         Camera node       Sensor nodes       Device adapters
         local CCTV        TEMP / MOTION      AC / LIGHT / etc.
                                                   │
                                         certified isolation
                                                   │
                                             real appliance
```

## Locked software boundaries

- `devices/contracts.py` = hardware-independent capability interfaces
- `core/device_network.py` = authenticated local transport
- `core/event_bus.py` = local event transport
- `intelligence/context.py` = observation → context
- `intelligence/reasoner.py` = deterministic structured explanation
- `intelligence/decision.py` = policy/action selection
- `core/home_state.py` = runtime state
- `hardware/adapters.py` = future physical-driver boundary

## Physical prototype requirements

The physical build should use:

- protected low-voltage logic
- appropriately rated isolation
- enclosure and strain relief
- watchdog/recovery behavior
- local device identity provisioning
- authenticated local messaging
- no default internet route
- explicit service/reset procedure

**Never connect an SBC GPIO directly to mains.**

## Example replacement

```text
v0.6
Virtual AC
   ↓
ClimateController
   ↓
Luminas Brain

future
Real AC interface
   ↓
ClimateControllerAdapter
   ↓
Luminas Brain
```

The Brain and Decision Engine should remain unchanged.

## What is still open

The exact SBC, sensor vendor, camera model, AC interface, enclosure, PCB and production BOM remain open until bench testing or a hardware partner establishes the right physical components.
