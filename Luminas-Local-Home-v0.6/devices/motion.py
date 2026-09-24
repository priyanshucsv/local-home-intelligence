from devices.device_base import LocalDevice


class MotionSensor(LocalDevice):
    def __init__(self, bus, audit, state=None, device_id="MOTION-01"):
        super().__init__(
            device_id, "MOTION_SENSOR", "LIVING_ROOM", None, audit,
            capabilities=("motion", "occupancy_evidence"),
        )
        self.bus = bus
        self.state = state
        self.motion = False

    def detect(self, location="living room"):
        if not self.online:
            self.last_error = "SENSOR_OFFLINE"
            self.audit.record("SECURITY", "Motion event withheld: sensor offline", kind="SECURITY EVENT")
            return False
        self.motion = True
        if self.state is not None:
            self.state.devices["motion_sensor"]["motion"] = True
        return bool(self.bus.publish("motion_detected", {"location": location, "sensor_id": self.device_id}, source=self.device_id))

    def clear(self):
        if not self.online:
            return False
        self.motion = False
        if self.state is not None:
            self.state.devices["motion_sensor"]["motion"] = False
        return bool(self.bus.publish("motion_cleared", {"sensor_id": self.device_id}, source=self.device_id))

    def read(self):
        return self.motion if self.online else None

    def state_snapshot(self):
        data = self.health()
        data.update({"motion": self.motion if self.online else None})
        return data
