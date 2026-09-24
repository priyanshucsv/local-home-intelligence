from datetime import datetime, timezone
import math
from devices.device_base import LocalDevice


class TemperatureSensor(LocalDevice):
    STALE_AFTER_SECONDS = 30.0

    def __init__(self, bus, state, network, audit, device_id="TEMP-01"):
        super().__init__(
            device_id, "TEMP_SENSOR", "LIVING_ROOM", network, audit,
            capabilities=("temperature", "telemetry"),
        )
        self.bus = bus
        self.state = state
        self.last_reading_sim_seconds = 0.0

    def set_temperature(self, temperature_c):
        try:
            temperature_c = float(temperature_c)
        except (TypeError, ValueError):
            return self.inject_invalid()
        if not math.isfinite(temperature_c) or not -20.0 <= temperature_c <= 70.0:
            return self.inject_invalid()
        return self._publish_temperature(temperature_c)

    def _publish_temperature(self, temperature_c):
        if not self.online:
            self.last_error = "SENSOR_OFFLINE"
            self.audit.record("SECURITY", "Temperature reading withheld: sensor offline", kind="SECURITY EVENT")
            return False
        ok = self.send("BRAIN-CORE", {"type": "telemetry", "temperature_c": temperature_c})
        if not ok:
            return False
        self.state.temperature_c = float(temperature_c)
        self.state.devices["ac"]["room_temperature_c"] = float(temperature_c)
        self.state.temperature_available = True
        self.state.temperature_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.state.devices["temperature_sensor"].update({
            "online": True, "available": True, "last_value_c": float(temperature_c),
            "age_seconds": 0.0,
        })
        self.last_reading_sim_seconds = self.state.simulation_seconds
        self.audit.record("TEMPERATURE", f"READ {temperature_c:.1f}C", kind="OBSERVATION")
        return self.bus.publish(
            "temperature_changed", {"temperature_c": float(temperature_c), "source": self.device_id}, source=self.device_id
        )

    def report_current(self):
        if not self.online:
            self.state.temperature_available = False
            return False
        self.state.devices["temperature_sensor"]["age_seconds"] = max(
            0.0, self.state.simulation_seconds - self.last_reading_sim_seconds
        )
        return self._publish_temperature(self.state.temperature_c)

    def inject_invalid(self):
        self.state.temperature_available = False
        self.state.devices["temperature_sensor"].update({"available": False, "last_value_c": None})
        self.last_error = "INVALID_READING"
        self.audit.record("SECURITY", "TEMPERATURE_INVALID_READING", kind="SECURITY EVENT")
        return self.bus.publish(
            "sensor_fault",
            {"sensor_id": self.device_id, "fault": "INVALID_READING"},
            source=self.device_id,
        )

    def set_online(self, online: bool):
        result = super().set_online(online)
        self.state.devices["temperature_sensor"]["online"] = result
        self.state.temperature_available = result
        self.state.devices["temperature_sensor"]["available"] = result
        if not result:
            self.bus.publish(
                "sensor_fault",
                {"sensor_id": self.device_id, "fault": "OFFLINE"},
                source=self.device_id,
            )
        return result

    def read(self):
        if not self.online or not self.state.temperature_available:
            return None
        return self.state.temperature_c

    def state_snapshot(self):
        data = self.health()
        data.update({
            "available": self.state.temperature_available,
            "value_c": self.state.temperature_c if self.state.temperature_available else None,
            "age_seconds": max(0.0, self.state.simulation_seconds - self.last_reading_sim_seconds),
        })
        return data
