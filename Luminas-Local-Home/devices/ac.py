from devices.device_base import LocalDevice


class AirConditioner(LocalDevice):
    COOLING_RATE_C_PER_SECOND = 0.14

    def __init__(self, bus, state, audit, network, device_id="AC-01"):
        super().__init__(
            device_id, "AC", "LIVING_ROOM", network, audit,
            capabilities=("power", "temperature_setpoint", "cooling", "fan", "telemetry"),
        )
        self.bus = bus
        self.state = state

    def turn_on(self):
        if not self.online:
            self.last_error = "DEVICE_OFFLINE"
            self.state.add_alert("Living room AC unavailable")
            self.audit.record("AC", "POWER_ON FAILURE: DEVICE_OFFLINE", kind="RESULT")
            return False
        if self.state.devices["ac"]["power"]:
            return True
        if not self.network.send_command("AC_POWER_ON", self.device_id):
            self.audit.record("AC", "POWER_ON FAILURE: COMMAND_REJECTED", kind="RESULT")
            return False
        self.state.devices["ac"]["power"] = True
        self.state.devices["ac"]["cooling"] = self.state.temperature_c > self.state.devices["ac"]["temperature_c"]
        self.audit.record("AC", "POWER_ON SUCCESS", kind="RESULT")
        self.send("BRAIN-CORE", {"type": "telemetry", "power": True})
        return True

    def turn_off(self):
        if not self.online:
            return False
        if not self.state.devices["ac"]["power"]:
            return True
        if not self.network.send_command("AC_POWER_OFF", self.device_id):
            self.audit.record("AC", "POWER_OFF FAILURE: COMMAND_REJECTED", kind="RESULT")
            return False
        self.state.devices["ac"]["power"] = False
        self.state.devices["ac"]["cooling"] = False
        self.audit.record("AC", "POWER_OFF SUCCESS", kind="RESULT")
        self.send("BRAIN-CORE", {"type": "telemetry", "power": False})
        return True

    def set_temperature(self, temperature_c):
        temperature_c = float(temperature_c)
        if not self.online:
            self.last_error = "DEVICE_OFFLINE"
            self.audit.record("AC", "SETPOINT FAILURE: DEVICE_OFFLINE", kind="RESULT")
            return False
        temperature_c = max(16.0, min(30.0, temperature_c))
        if self.state.devices["ac"]["temperature_c"] == temperature_c:
            return True
        if not self.network.send_command("AC_SETPOINT", self.device_id, {"target_c": temperature_c}):
            self.audit.record("AC", "SETPOINT FAILURE: COMMAND_REJECTED", kind="RESULT")
            return False
        self.state.devices["ac"]["temperature_c"] = temperature_c
        self.state.devices["ac"]["cooling"] = self.state.devices["ac"]["power"] and self.state.temperature_c > temperature_c
        self.audit.record("AC", f"SET_TEMPERATURE {temperature_c:.1f}C SUCCESS", kind="RESULT")
        self.send("BRAIN-CORE", {"type": "telemetry", "target_c": temperature_c})
        return True

    def simulate_step(self, seconds):
        seconds = max(0.0, float(seconds))
        ac = self.state.devices["ac"]
        if not self.online or not ac["power"]:
            ac["cooling"] = False
            ac["room_temperature_c"] = self.state.temperature_c
            return False
        target = float(ac["temperature_c"])
        current = float(self.state.temperature_c)
        if current <= target:
            ac["cooling"] = False
            ac["room_temperature_c"] = current
            return False
        delta = min(current - target, self.COOLING_RATE_C_PER_SECOND * seconds)
        # Stop cooling at the setpoint instead of overshooting below it.
        new_temp = max(target, round(current - delta, 2))
        self.state.temperature_c = new_temp
        ac["room_temperature_c"] = new_temp
        ac["cooling"] = new_temp > target
        return True

    def set_online(self, online: bool):
        result = super().set_online(online)
        self.state.devices["ac"]["online"] = result
        if not result:
            self.state.devices["ac"]["cooling"] = False
        return result

    def state_snapshot(self):
        data = self.health()
        data.update(self.state.devices["ac"].copy())
        return data
