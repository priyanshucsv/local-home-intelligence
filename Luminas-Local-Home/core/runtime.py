from datetime import datetime, timezone
import secrets
import threading
import time

from core.event_bus import EventBus
from core.home_state import HomeState
from core.device_network import LocalDeviceNetwork
from devices.cctv import CCTV
from devices.ac import AirConditioner
from devices.light import Light
from devices.sensors import TemperatureSensor
from devices.motion import MotionSensor
from devices.door import EntryDoor
from intelligence.context import ContextEngine
from intelligence.decision import DecisionEngine
from intelligence.reasoner import LocalReasoner
from security.audit import AuditLog
from security.privacy import PrivacyMonitor


# DEMO-ONLY identities. Secrets are generated fresh for every runtime so no
# reusable production credential ever exists in this repository.
DEMO_DEVICE_ROLES = (
    ("BRAIN-CORE", "INTELLIGENCE", "LOCAL"),
    ("CCTV-01", "CCTV", "ENTRANCE"),
    ("TEMP-01", "TEMP_SENSOR", "LIVING_ROOM"),
    ("AC-01", "AC", "LIVING_ROOM"),
    ("LIGHT-01", "LIGHT", "LIVING_ROOM"),
)


class LuminasRuntime:
    """Single-process local home runtime and digital-twin coordinator."""

    def __init__(self):
        self.bus = EventBus()
        self.state = HomeState(initial_temperature=31.4)
        self.audit = AuditLog()
        self.privacy = PrivacyMonitor()
        self.reasoner = LocalReasoner()
        self.network = LocalDeviceNetwork(self.audit)
        self.privacy.attach_guard(self.network.guard)

        # Register DEMO-ONLY identities with fresh ephemeral secrets.
        for device_id, device_type, zone in DEMO_DEVICE_ROLES:
            self.network.register(device_id, device_type, zone, secrets.token_hex(32))

        self.cctv = CCTV(self.bus, self.network, self.audit)
        self.ac = AirConditioner(self.bus, self.state, self.audit, self.network)
        self.lights = Light(self.bus, self.state, self.audit, self.network)
        self.temperature = TemperatureSensor(self.bus, self.state, self.network, self.audit)
        self.motion = MotionSensor(self.bus, self.audit, self.state)
        self.door = EntryDoor(self.bus, self.audit, self.state)

        self.context = ContextEngine(self.bus, self.state, self.audit)
        self.decision = DecisionEngine(
            self.bus, self.state, self.ac, self.lights, self.audit, self.reasoner
        )

        # The primary public demo runs under an explicit DemoController so the
        # dashboard can observe real runtime demo state instead of guessing.
        self.demo = DemoController(self)

        for event_type in (
            "resident_detected", "resident_left", "guest_detected",
            "unknown_person_detected", "motion_detected", "motion_cleared",
            "no_movement", "temperature_changed", "sensor_fault",
            "door_opened", "door_closed", "sensor_conflict",
        ):
            self.bus.subscribe(event_type, self.context.handle)

        for event_type in (
            "resident_arrived", "resident_departed", "guest_arrived",
            "motion_detected", "inactivity_detected", "temperature_changed",
            "sensor_unavailable",
        ):
            self.bus.subscribe(event_type, self.decision.handle)

        self.audit.record("RUNTIME", "LUMINAS LOCAL HOME v0.6 initialized", kind="OBSERVATION")

    def reset(self):
        return LuminasRuntime()

    def set_temperature(self, temperature_c):
        return self.temperature.set_temperature(temperature_c)

    def advance(self, seconds, report_temperature=True):
        """Advance simulation time without pretending it is wall-clock time."""
        seconds = max(0.0, float(seconds))
        self.context.advance(seconds)
        self.ac.simulate_step(seconds)
        self.state.devices["ac"]["room_temperature_c"] = self.state.temperature_c
        if report_temperature:
            self.temperature.report_current()
        return self.state.temperature_c

    def inject_sensor_failure(self):
        return self.temperature.inject_invalid()

    def validate_temperature_freshness(self):
        age = self.state.simulation_seconds - self.temperature.last_reading_sim_seconds
        if age > self.temperature.STALE_AFTER_SECONDS:
            self.state.temperature_available = False
            self.state.devices["temperature_sensor"]["available"] = False
            self.audit.record("SECURITY", f"TEMPERATURE_STALE age={age:.1f}s", kind="SECURITY EVENT")
            return self.bus.publish(
                "sensor_fault",
                {"sensor_id": "TEMP-01", "fault": "STALE_DATA", "age_seconds": age},
                source="TEMP-01",
            )
        return False

    def state_snapshot(self):
        return {
            "home": self.state.snapshot(),
            "devices": self.device_snapshots(),
            "events": self.bus.snapshot(),
            "network": self.network.snapshot(),
            "privacy": self.privacy.snapshot(),
            "audit": self.audit.snapshot(60),
        }

    def device_snapshots(self):
        return {
            "cctv": self.cctv.state_snapshot(),
            "temperature_sensor": self.temperature.state_snapshot(),
            "motion_sensor": self.motion.state_snapshot(),
            "door": self.door.state_snapshot(),
            "ac": self.ac.state_snapshot(),
            "lights": self.lights.state_snapshot(),
        }

    def run(self):
        print("╔════════════════════════════════════════════════════════════╗")
        print("║           LUMINAS LOCAL HOME — v0.6                      ║")
        print("║        LOCAL HOME DIGITAL TWIN / SOFTWARE                ║")
        print("╠════════════════════════════════════════════════════════════╣")
        print("║ Internet: OFF   Cloud: DISABLED   External APIs: NONE   ║")
        print("║ Device transport: authenticated local-only               ║")
        print("║ Physical hardware: NOT CONNECTED / DIGITAL TWIN         ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("Starting local runtime...\n")


class DemoController:
    """Deterministic primary demo with observable runtime demo state.

    The demo resets the Digital Twin, replays the exact same event sequence
    every run, and exposes ``demo_state`` so the dashboard can show real
    progress instead of guessing with timers.
    """

    # One cooling tick ≈ 10 simulated seconds per real 1.1 s ⇒ ~7 s cooling.
    COOLING_TICK_SECONDS = 10.0
    COOLING_TICK_DELAY = 1.1

    STAGE_ORDER = (
        "DOOR", "DETECTION", "CONTEXT", "DECISION", "ACTION", "COOLING",
    )

    STAGES = {
        "DOOR": {"num": "01", "label": "DOOR", "state": "DOOR_OPEN"},
        "DETECTION": {"num": "02", "label": "DETECTION", "state": "DETECTING_RESIDENT"},
        "CONTEXT": {"num": "03", "label": "CONTEXT", "state": "CONFIRMING_OCCUPANCY"},
        "DECISION": {"num": "04", "label": "DECISION", "state": "EVALUATING_COMFORT"},
        "ACTION": {"num": "05", "label": "ACTION", "state": "ACTIVATING_COMFORT"},
        "COOLING": {"num": "06", "label": "COOLING", "state": "AC_COOLING"},
    }

    def __init__(self, runtime):
        self._runtime = runtime
        self.state = "IDLE"
        self.stage = None
        self.thread = None
        self.last_error = None

    def _set_state(self, state, stage=None):
        self.state = state
        if state in ("IDLE", "RESETTING"):
            self.stage = None
        elif state == "COMPLETE":
            self.stage = "COOLING"
        elif state == "FAILED":
            self.stage = stage if stage is not None else self.stage
        else:
            self.stage = stage

    def snapshot(self):
        """Demo status for the dashboard, sourced entirely from runtime."""
        running = self.state not in ("IDLE", "COMPLETE", "FAILED")
        if self.state == "IDLE":
            stage_label = "—"
        elif self.state == "RESETTING":
            stage_label = "RESETTING"
        elif self.state == "COMPLETE":
            stage_label = "DEMO COMPLETE"
        elif self.state == "FAILED":
            stage_label = "FAILED"
        else:
            stage_label = (self.STAGES.get(self.stage) or {}).get("label", self.stage or "—").replace("_", " ")
        return {
            "demo_state": self.state,
            "stage": self.stage,
            "stage_label": stage_label,
            "running": running,
            "stages": [
                {"num": spec["num"], "label": spec["label"], "active": self.stage == name}
                for name, spec in self.STAGES.items()
            ],
            "last_error": self.last_error,
        }

    def running(self):
        return self.state not in ("IDLE", "COMPLETE", "FAILED")

    def reset_demo_state(self):
        self.state = "IDLE"
        self.stage = None
        self.last_error = None

    def run_in_background(self):
        """Start the demo on a worker thread; returns False if one is running."""
        if self.running():
            return False
        self.thread = threading.Thread(target=self._run, name="luminas-demo", daemon=True)
        self.thread.start()
        return True

    def run_sync(self):
        """Run the demo synchronously (validation / CLI use)."""
        if self.running():
            return False
        self._run()
        return True

    def _run(self):
        try:
            self._execute()
        except Exception as exc:  # keep the demo button usable no matter what
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._set_state("FAILED")

    def _execute(self):
        runtime = self._runtime

        self._set_state("RESETTING")
        fresh = LuminasRuntime()
        runtime.state = fresh.state
        runtime.bus = fresh.bus
        runtime.audit = fresh.audit
        runtime.privacy = fresh.privacy
        runtime.reasoner = fresh.reasoner
        runtime.network = fresh.network
        runtime.privacy.attach_guard(runtime.network.guard)
        runtime.cctv = fresh.cctv
        runtime.ac = fresh.ac
        runtime.lights = fresh.lights
        runtime.temperature = fresh.temperature
        runtime.motion = fresh.motion
        runtime.door = fresh.door
        runtime.context = fresh.context
        runtime.decision = fresh.decision
        self._set_state("IDLE")

        self._set_state("DOOR_OPEN", "DOOR")
        runtime.door.open()
        time.sleep(1.0)

        self._set_state("DETECTING_RESIDENT", "DETECTION")
        runtime.cctv.detect_resident("front_door", 0.97)
        time.sleep(1.0)

        self._set_state("CONFIRMING_OCCUPANCY", "CONTEXT")
        runtime.motion.detect("living_room")
        time.sleep(1.0)

        self._set_state("EVALUATING_COMFORT", "DECISION")
        time.sleep(1.0)
        self._set_state("ACTIVATING_COMFORT", "ACTION")
        runtime.bus.publish("decision_evaluated", {"trigger": "resident_arrived"}, source="LOCAL_BRAIN")
        time.sleep(1.0)
        self._set_state("AC_COOLING", "COOLING")
        runtime.set_temperature(runtime.state.temperature_c)  # refresh availability/freshness
        while runtime.ac.simulate_step(self.COOLING_TICK_SECONDS):
            time.sleep(self.COOLING_TICK_DELAY)
        time.sleep(0.4)

        target = float(runtime.state.devices["ac"]["temperature_c"])
        if runtime.state.occupied and runtime.state.devices["ac"]["power"] and runtime.state.temperature_c <= target + 0.05:
            self._set_state("COMPLETE")
        else:
            self.last_error = "Demo completion conditions were not met"
            self._set_state("FAILED")
