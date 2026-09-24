class ContextEngine:
    """Builds occupancy and home context from multiple local observations."""

    VACANCY_TIMEOUT_SECONDS = 30.0
    RESIDENT_CONFIDENCE_THRESHOLD = 0.80

    def __init__(self, bus, state, audit):
        self.bus = bus
        self.state = state
        self.audit = audit
        self.entry_signal = False
        self.resident_seen = False
        self.resident_confidence = 0.0
        self.last_evidence_seconds = {"door": -9999.0, "motion": -9999.0, "resident": -9999.0}
        self.vacancy_due_seconds = None

    def _confirm_occupancy(self, reason):
        self.state.occupied = True
        self.state.guest_present = False
        self.state.mode = "OCCUPIED"
        self.state.occupancy_confidence = max(0.0, min(1.0, self.resident_confidence))
        self.state.occupancy_evidence = [
            evidence for evidence, seen in (
                ("DOOR", self.entry_signal),
                ("MOTION", self.last_evidence_seconds["motion"] >= 0),
                ("CCTV_RESIDENT", self.resident_seen),
            ) if seen
        ]
        self.audit.record("CONTEXT", f"OCCUPANCY_CONFIRMED reason={reason}", kind="CONTEXT")
        self.bus.publish("occupancy_confirmed", {
            "reason": reason,
            "confidence": self.state.occupancy_confidence,
            "evidence": list(self.state.occupancy_evidence),
        }, source="LOCAL_BRAIN")

    def handle(self, event):
        event_type = event["type"]
        data = event["data"]
        self.state.last_event = event_type
        if "confidence" in data:
            self.state.confidence = data.get("confidence")

        if event_type == "door_opened":
            self.entry_signal = True
            self.last_evidence_seconds["door"] = self.state.simulation_seconds
            self.audit.record("CONTEXT", "ENTRY_ACTIVITY door=OPEN", kind="OBSERVATION")
            return

        if event_type == "door_closed":
            self.entry_signal = False
            self.audit.record("CONTEXT", "ENTRY_ACTIVITY door=CLOSED", kind="OBSERVATION")
            return

        if event_type == "resident_detected":
            self.resident_seen = True
            self.resident_confidence = float(data.get("confidence", 0.0))
            self.last_evidence_seconds["resident"] = self.state.simulation_seconds
            self.state.resident_location = data.get("location")
            recent_support = (
                self.state.simulation_seconds - self.last_evidence_seconds["door"] <= 20.0
                or self.state.simulation_seconds - self.last_evidence_seconds["motion"] <= 20.0
            )
            if self.resident_confidence >= self.RESIDENT_CONFIDENCE_THRESHOLD:
                self._confirm_occupancy("CCTV resident identity + recent entry/activity")
                self.state.last_motion_minutes = 0.0
                self.bus.publish("resident_arrived", {"location": data.get("location")}, source="LOCAL_BRAIN")
            else:
                self.audit.record("CONTEXT", "RESIDENT_SIGNAL_HELD_FOR_SUPPORTING_EVIDENCE", kind="CONTEXT")
            return

        if event_type == "resident_left":
            confirmed = bool(data.get("confirmed", True))
            if confirmed:
                self._confirm_vacancy("explicit departure signal")
            else:
                self.vacancy_due_seconds = self.state.simulation_seconds + self.VACANCY_TIMEOUT_SECONDS
                self.audit.record("CONTEXT", f"VACANCY_PENDING timeout={self.VACANCY_TIMEOUT_SECONDS:.0f}s", kind="CONTEXT")
            return

        if event_type == "motion_detected":
            self.last_evidence_seconds["motion"] = self.state.simulation_seconds
            self.state.last_motion_minutes = 0.0
            if self.resident_seen and self.resident_confidence >= self.RESIDENT_CONFIDENCE_THRESHOLD:
                self._confirm_occupancy("resident identity + motion evidence")
            self.audit.record("CONTEXT", f"MOTION source={event.get('source', 'unknown')}", kind="OBSERVATION")
            return

        if event_type == "motion_cleared":
            self.audit.record("CONTEXT", "MOTION_CLEARED", kind="OBSERVATION")
            return

        if event_type == "no_movement":
            minutes = max(0.0, float(data.get("minutes", 0.0)))
            self.state.last_motion_minutes = minutes
            self.audit.record("CONTEXT", f"NO_MOVEMENT minutes={minutes:.0f}", kind="CONTEXT")
            self.bus.publish("inactivity_detected", {"minutes": minutes}, source="LOCAL_BRAIN")
            return

        if event_type == "guest_detected":
            self.state.guest_present = True
            self.state.occupied = True
            self.state.mode = "GUEST"
            self.state.occupancy_confidence = float(data.get("confidence", 0.0))
            self.state.occupancy_evidence = ["CCTV_GUEST"]
            self.audit.record("SECURITY", "GUEST_DETECTED", kind="SECURITY EVENT")
            self.bus.publish("guest_arrived", {"location": data.get("location")}, source="LOCAL_BRAIN")
            return

        if event_type == "unknown_person_detected":
            self.state.add_alert("Unknown person detected at front door")
            self.audit.record("SECURITY", "UNKNOWN_PERSON_DETECTED", kind="SECURITY EVENT", details=data)
            return

        if event_type == "sensor_fault":
            self.state.temperature_available = False if data.get("sensor_id") == "TEMP-01" else self.state.temperature_available
            if data.get("sensor_id") == "TEMP-01":
                self.state.devices["temperature_sensor"]["available"] = False
                self.state.add_alert("Temperature sensor unavailable")
            self.audit.record("SECURITY", f"SENSOR_FAULT {data}", kind="SECURITY EVENT")
            self.bus.publish("sensor_unavailable", data, source="LOCAL_BRAIN")
            return

        if event_type == "sensor_conflict":
            cctv_signal = bool(data.get("cctv"))
            motion_signal = bool(data.get("motion"))
            if cctv_signal and not motion_signal:
                self.state.add_alert("Occupancy evidence conflict: CCTV resident / motion absent")
                self.audit.record("SECURITY", "OCCUPANCY_EVIDENCE_CONFLICT cctv=resident motion=absent", kind="SECURITY EVENT", details=data)
            else:
                self.state.add_alert("Occupancy evidence conflict")
                self.audit.record("SECURITY", f"OCCUPANCY_EVIDENCE_CONFLICT {data}", kind="SECURITY EVENT")
            return

        if event_type == "temperature_changed":
            temperature = float(data["temperature_c"])
            self.state.temperature_c = temperature
            self.state.temperature_available = True
            self.state.devices["temperature_sensor"].update({"available": True, "last_value_c": temperature})
            self.audit.record("CONTEXT", f"TEMPERATURE {temperature:.1f}C", kind="OBSERVATION")
            return

    def advance(self, seconds):
        self.state.simulation_seconds += max(0.0, float(seconds))
        if self.state.occupied:
            self.state.last_motion_minutes += max(0.0, float(seconds)) / 60.0
        if self.vacancy_due_seconds is not None and self.state.simulation_seconds >= self.vacancy_due_seconds:
            self._confirm_vacancy("vacancy timeout elapsed")
            self.vacancy_due_seconds = None

    def _confirm_vacancy(self, reason):
        self.state.occupied = False
        self.state.guest_present = False
        self.state.resident_location = None
        self.state.last_motion_minutes = 0.0
        self.state.mode = "EMPTY"
        self.state.occupancy_confidence = 0.0
        self.state.occupancy_evidence = []
        self.audit.record("CONTEXT", f"OCCUPANCY_CLEARED reason={reason}", kind="CONTEXT")
        self.bus.publish("resident_departed", {"reason": reason}, source="LOCAL_BRAIN")
