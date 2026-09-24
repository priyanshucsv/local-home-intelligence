from datetime import datetime, timezone
from devices.device_base import LocalDevice


class CCTV(LocalDevice):
    """Local CCTV event simulator; no raw video leaves the process."""

    def __init__(self, bus, network, audit, device_id="CCTV-01"):
        super().__init__(
            device_id, "CCTV", "ENTRANCE", network, audit,
            capabilities=("motion", "person_detection", "resident_detection", "unknown_person_detection"),
        )
        self.bus = bus
        self.monitoring = True

    def _publish(self, event, payload, message):
        if not self.online or not self.monitoring:
            self.last_error = "CAMERA_OFFLINE"
            self.audit.record("SECURITY", f"CCTV event withheld: {event}; camera unavailable", kind="SECURITY EVENT")
            return False
        message = dict(message)
        message["camera_id"] = self.device_id
        message["source"] = "local_camera"
        if not self.send("BRAIN-CORE", message):
            self.audit.record("SECURITY", f"CCTV event rejected by local network: {event}", kind="SECURITY EVENT")
            return False
        payload = dict(payload)
        payload.update({
            "camera_id": self.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "source": "local_camera",
        })
        event_result = self.bus.publish(event, payload, source=self.device_id)
        if event_result is False:
            self.audit.record("SECURITY", f"DUPLICATE CCTV EVENT {event}", kind="SECURITY EVENT")
            return False
        self.audit.record("CCTV", f"OBSERVED {event}", kind="OBSERVATION", details=payload)
        return True

    def detect_resident(self, location="front entrance", confidence=0.96):
        return self._publish(
            "resident_detected",
            {"location": location, "confidence": float(confidence)},
            {"type": "presence", "person": "resident", "location": location, "confidence": float(confidence)},
        )

    def detect_unknown(self, location="front entrance", confidence=0.88):
        return self._publish(
            "unknown_person_detected",
            {"location": location, "confidence": float(confidence)},
            {"type": "presence", "person": "unknown", "location": location, "confidence": float(confidence)},
        )

    def detect_resident_leave(self, location="main door", confidence=0.97, confirmed=True):
        return self._publish(
            "resident_left",
            {"location": location, "confidence": float(confidence), "confirmed": bool(confirmed)},
            {"type": "presence", "person": "resident_left", "location": location, "confidence": float(confidence), "confirmed": bool(confirmed)},
        )

    def detect_guest(self, location="front entrance", confidence=0.91):
        return self._publish(
            "guest_detected",
            {"location": location, "confidence": float(confidence)},
            {"type": "presence", "person": "guest", "location": location, "confidence": float(confidence)},
        )

    def detect_motion(self, location="living room"):
        return self._publish(
            "motion_detected", {"location": location},
            {"type": "motion", "location": location},
        )

    def detect_no_movement(self, minutes):
        minutes = float(minutes)
        return self._publish(
            "no_movement", {"minutes": minutes},
            {"type": "inactivity", "minutes": minutes},
        )

    def read(self):
        return {
            "online": self.online,
            "monitoring": self.monitoring,
            "raw_video_export": False,
        }

    def state_snapshot(self):
        data = self.health()
        data.update({"monitoring": self.monitoring, "local_raw_video": False})
        return data
