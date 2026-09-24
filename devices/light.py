from devices.device_base import LocalDevice


class Light(LocalDevice):
    def __init__(self, bus, state, audit, network, device_id="LIGHT-01"):
        super().__init__(
            device_id, "LIGHT", "LIVING_ROOM", network, audit,
            capabilities=("switch", "brightness"),
        )
        self.bus = bus
        self.state = state

    def turn_on(self):
        if not self.online:
            self.last_error = "DEVICE_OFFLINE"
            self.audit.record("LIGHTS", "POWER_ON FAILURE: DEVICE_OFFLINE", kind="RESULT")
            self.state.add_alert("Living room light unavailable")
            return False
        if self.state.devices["lights"]["power"]:
            return True
        if not self.network.send_command("LIGHT_ON", self.device_id):
            self.audit.record("LIGHTS", "POWER_ON FAILURE: COMMAND_REJECTED", kind="RESULT")
            self.state.add_alert("Living room light command rejected")
            return False
        self.state.devices["lights"]["power"] = True
        self.audit.record("LIGHTS", "POWER_ON SUCCESS", kind="RESULT")
        self.send("BRAIN-CORE", {"type": "telemetry", "power": True})
        return True

    def turn_off(self):
        if not self.online:
            self.last_error = "DEVICE_OFFLINE"
            return False
        if not self.state.devices["lights"]["power"]:
            return True
        if not self.network.send_command("LIGHT_OFF", self.device_id):
            self.audit.record("LIGHTS", "POWER_OFF FAILURE: COMMAND_REJECTED", kind="RESULT")
            return False
        self.state.devices["lights"]["power"] = False
        self.audit.record("LIGHTS", "POWER_OFF SUCCESS", kind="RESULT")
        self.send("BRAIN-CORE", {"type": "telemetry", "power": False})
        return True

    def set_brightness(self, brightness):
        brightness = max(0, min(100, float(brightness)))
        if not self.online:
            return False
        if not self.network.send_command("LIGHT_BRIGHTNESS", self.device_id, {"brightness": brightness}):
            return False
        self.state.devices["lights"]["brightness"] = brightness
        self.audit.record("LIGHTS", f"BRIGHTNESS {brightness:.0f}%", kind="RESULT")
        return True

    def state_snapshot(self):
        data = self.health()
        data.update({
            "power": self.state.devices["lights"]["power"],
            "brightness": self.state.devices["lights"]["brightness"],
        })
        return data
