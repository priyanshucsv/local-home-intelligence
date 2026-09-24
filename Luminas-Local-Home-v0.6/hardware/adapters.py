"""Future physical-adapter boundary.

No GPIO, mains, Bluetooth, cloud, or vendor SDK code belongs here in v0.6.
The Brain consumes the same contracts used by the Digital Twin. A future
adapter implements those contracts and becomes the only layer aware of the
physical protocol.
"""
from typing import Any, Dict


class DeviceAdapter:
    kind = "HARDWARE_ADAPTER"

    def __init__(self, device_id):
        self.device_id = device_id
        self.online = False

    def health(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "driver": self.__class__.__name__,
            "kind": self.kind,
            "online": self.online,
            "simulation": False,
            "requires_physical_validation": True,
        }

    def state_snapshot(self):
        return self.health()


class ClimateControllerAdapter(DeviceAdapter):
    def set_power(self, on: bool):
        raise NotImplementedError("Attach a safety-reviewed isolated AC driver.")

    def set_temperature(self, temperature_c: float):
        raise NotImplementedError("Attach a safety-reviewed local AC protocol driver.")


class LightControllerAdapter(DeviceAdapter):
    def set_power(self, on: bool):
        raise NotImplementedError("Attach a safety-reviewed isolated lighting driver.")

    def set_brightness(self, brightness: float):
        raise NotImplementedError("Attach a safety-reviewed lighting controller.")


class CameraAdapter(DeviceAdapter):
    def emit_local_event(self, event_type: str, payload: Dict[str, Any]):
        raise NotImplementedError("Attach a local camera driver that emits only local events.")


class TemperatureSensorAdapter(DeviceAdapter):
    def read_celsius(self) -> float:
        raise NotImplementedError("Attach a validated temperature sensor driver.")


class MotionSensorAdapter(DeviceAdapter):
    def read_motion(self) -> bool:
        raise NotImplementedError("Attach a validated motion sensor driver.")


class DoorSensorAdapter(DeviceAdapter):
    def read_open(self) -> bool:
        raise NotImplementedError("Attach a validated entry sensor driver.")
