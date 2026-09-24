"""Hardware-independent device contracts used by the Luminas Brain.

These are Python Protocols rather than simulator-specific base classes.  A
future physical adapter only needs to implement the same public behavior.
"""
from typing import Any, Dict, Protocol, Sequence, runtime_checkable


@runtime_checkable
class Device(Protocol):
    device_id: str
    device_type: str
    zone: str
    kind: str
    online: bool

    def health(self) -> Dict[str, Any]: ...
    def state_snapshot(self) -> Dict[str, Any]: ...


@runtime_checkable
class Sensor(Device, Protocol):
    def read(self) -> Any: ...


@runtime_checkable
class Actuator(Device, Protocol):
    def turn_on(self) -> bool: ...
    def turn_off(self) -> bool: ...


@runtime_checkable
class Camera(Sensor, Protocol):
    def detect_resident(self, location: str = "front entrance", confidence: float = 0.96) -> bool: ...


@runtime_checkable
class ClimateController(Actuator, Protocol):
    def set_temperature(self, temperature_c: float) -> bool: ...
    def simulate_step(self, seconds: float) -> bool: ...


@runtime_checkable
class LightController(Actuator, Protocol):
    def set_brightness(self, brightness: float) -> bool: ...


@runtime_checkable
class DoorSensor(Sensor, Protocol):
    def open(self) -> bool: ...
    def close(self) -> bool: ...


def capability_names(device: Device) -> Sequence[str]:
    """Return stable capability names for UI/adapter discovery."""
    return tuple(getattr(device, "capabilities", ()))
