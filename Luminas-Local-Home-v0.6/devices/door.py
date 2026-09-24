from devices.device_base import LocalDevice


class EntryDoor(LocalDevice):
    def __init__(self, bus, audit, state=None, device_id="DOOR-01"):
        super().__init__(
            device_id, "DOOR_SENSOR", "FRONT_DOOR", None, audit,
            capabilities=("door_state", "entry_event"),
        )
        self.bus = bus
        self.state = state
        self.open_state = False

    def open(self):
        if not self.online:
            self.last_error = "SENSOR_OFFLINE"
            self.audit.record("SECURITY", "Door event withheld: sensor offline", kind="SECURITY EVENT")
            return False
        self.open_state = True
        if self.state is not None:
            self.state.devices["door"]["open"] = True
        return bool(self.bus.publish("door_opened", {"door_id": self.device_id, "location": "front_door"}, source=self.device_id))

    def close(self):
        if not self.online:
            return False
        self.open_state = False
        if self.state is not None:
            self.state.devices["door"]["open"] = False
        return bool(self.bus.publish("door_closed", {"door_id": self.device_id, "location": "front_door"}, source=self.device_id))

    def read(self):
        return self.open_state if self.online else None

    def state_snapshot(self):
        data = self.health()
        data.update({"open": self.open_state if self.online else None})
        return data
