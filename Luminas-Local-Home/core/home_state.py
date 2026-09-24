from datetime import datetime, timezone


class HomeState:
    """Single source of truth for the simulated home's runtime state."""

    def __init__(self, initial_temperature=31.4):
        initial_temperature = float(initial_temperature)
        self.occupied = False
        self.guest_present = False
        self.temperature_c = initial_temperature
        self.temperature_available = True
        self.temperature_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.resident_location = None
        self.last_motion_minutes = 0.0
        self.mode = "EMPTY"
        self.last_event = "System initialized"
        self.last_decision = "Waiting for local events"
        self.decision_chain = []
        self.confidence = None
        self.occupancy_confidence = 0.0
        self.occupancy_evidence = []
        self.alerts = []
        self.security_state = "NORMAL"
        self.simulation_seconds = 0.0
        self.devices = {
            "cctv": {
                "device_id": "CCTV-01", "online": True, "location": "front_door",
                "mode": "LOCAL_EVENT_ONLY", "kind": "DIGITAL_TWIN",
            },
            "temperature_sensor": {
                "device_id": "TEMP-01", "online": True, "available": True,
                "location": "living_room", "kind": "DIGITAL_TWIN",
            },
            "motion_sensor": {
                "device_id": "MOTION-01", "online": True, "motion": False,
                "location": "living_room", "kind": "DIGITAL_TWIN",
            },
            "door": {
                "device_id": "DOOR-01", "online": True, "open": False,
                "location": "front_door", "kind": "DIGITAL_TWIN",
            },
            "ac": {
                "device_id": "AC-01", "online": True, "power": False,
                "temperature_c": 24.0, "room_temperature_c": initial_temperature,
                "mode": "COOL", "fan": "AUTO", "cooling": False,
                "kind": "DIGITAL_TWIN",
            },
            "lights": {
                "device_id": "LIGHT-01", "online": True, "power": False,
                "brightness": 80, "location": "living_room", "kind": "DIGITAL_TWIN",
            },
        }

    def add_alert(self, text):
        if text not in self.alerts:
            self.alerts.append(text)
        self.security_state = "ATTENTION"

    def clear_alert(self, text=None):
        if text is None:
            self.alerts = []
        else:
            self.alerts = [a for a in self.alerts if a != text]
        if not self.alerts:
            self.security_state = "NORMAL"

    def record_decision(self, steps):
        self.decision_chain = [dict(step) for step in steps]
        action_texts = [step["text"] for step in self.decision_chain if step.get("type") == "ACTION"]
        self.last_decision = action_texts[-1] if action_texts else self.decision_chain[-1]["text"] if self.decision_chain else "No action"

    def snapshot(self):
        return {
            "occupied": self.occupied,
            "guest_present": self.guest_present,
            "temperature_c": self.temperature_c,
            "temperature_available": self.temperature_available,
            "temperature_timestamp": self.temperature_timestamp,
            "resident_location": self.resident_location,
            "last_motion_minutes": self.last_motion_minutes,
            "mode": self.mode,
            "last_event": self.last_event,
            "last_decision": self.last_decision,
            "decision_chain": [dict(x) for x in self.decision_chain],
            "confidence": self.confidence,
            "occupancy_confidence": self.occupancy_confidence,
            "occupancy_evidence": list(self.occupancy_evidence),
            "alerts": list(self.alerts),
            "security_state": self.security_state,
            "simulation_seconds": self.simulation_seconds,
            "devices": {name: state.copy() for name, state in self.devices.items()},
        }
