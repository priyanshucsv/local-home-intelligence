"""Deterministic v0.6 digital-twin scenarios and failure injections."""
import time
from dataclasses import dataclass
from simulation.house import VirtualHouse

HOT_TEMPERATURE_C = 31.4
COMFORT_TEMPERATURE_C = 23.0


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    summary: str


class ScenarioRunner:
    def __init__(self, runtime):
        self.runtime = runtime

    def reset(self):
        self.runtime = self.runtime.reset()
        return self.runtime

    def _resident_returns(self, temperature_c, cooling_steps=26, real_delay=0.0, step_seconds=2.0):
        r = self.runtime
        r.set_temperature(temperature_c)
        r.door.open()
        r.cctv.detect_resident("front_door", 0.97)
        r.motion.detect("living_room")
        start = r.state.temperature_c
        for _ in range(int(cooling_steps)):
            r.advance(step_seconds)
            if real_delay:
                time.sleep(real_delay)
        end = r.state.temperature_c
        return start, end

    def resident_returns_hot(self, cooling_steps=27, real_delay=0.0, step_seconds=2.0):
        start, end = self._resident_returns(HOT_TEMPERATURE_C, cooling_steps, real_delay, step_seconds)
        r = self.runtime
        passed = (
            r.state.occupied
            and r.state.devices["lights"]["power"]
            and r.state.devices["ac"]["power"]
            and r.state.devices["ac"]["temperature_c"] == 24.0
            and end < start
        )
        return ScenarioResult(
            "resident_returns_hot",
            passed,
            f"{start:.1f}°C → {end:.2f}°C with AC={'ON' if r.state.devices['ac']['power'] else 'OFF'}",
        )

    def resident_returns_comfortable(self):
        r = self.runtime
        r.set_temperature(COMFORT_TEMPERATURE_C)
        r.door.open()
        r.cctv.detect_resident("front_door", 0.96)
        r.motion.detect("living_room")
        passed = r.state.occupied and r.state.devices["lights"]["power"] and not r.state.devices["ac"]["power"]
        return ScenarioResult("resident_returns_comfortable", passed, "Resident present; lights on; AC remains OFF")

    def resident_leaves(self):
        r = self.runtime
        if not r.state.occupied:
            self.resident_returns_comfortable()
        r.cctv.detect_resident_leave("front_door", .97, confirmed=False)
        r.door.close()
        r.motion.clear()
        r.advance(31.0, report_temperature=False)
        r.validate_temperature_freshness()
        passed = not r.state.occupied and not r.state.devices["ac"]["power"] and not r.state.devices["lights"]["power"]
        return ScenarioResult("resident_leaves", passed, "Vacancy confirmed after configured 30-second timeout")

    def unknown_person(self):
        r = self.runtime
        r.set_temperature(HOT_TEMPERATURE_C)
        r.door.open()
        r.cctv.detect_unknown("front_door", .93)
        passed = (not r.state.occupied) and bool(r.state.alerts) and not r.state.devices["ac"]["power"]
        return ScenarioResult(
            "unknown_person", passed,
            "Unknown-person event creates a security alert without resident comfort automation",
        )

    def temperature_sensor_failure(self):
        r = self.runtime
        self.resident_returns_hot(cooling_steps=1)
        r.inject_sensor_failure()
        passed = (not r.state.temperature_available) and r.state.mode in {"SAFE_HOLD", "COMFORT", "COMFORT_DEGRADED"}
        return ScenarioResult(
            "temperature_sensor_failure", passed,
            "Temperature automation is withheld when the reading becomes invalid",
        )

    def cctv_offline(self):
        r = self.runtime
        r.cctv.set_online(False)
        r.door.open()
        r.motion.detect("living_room")
        r.cctv.detect_resident("front_door", .99)
        passed = not r.state.occupied and not r.state.devices["lights"]["power"]
        return ScenarioResult("cctv_offline", passed, "CCTV does not fabricate a detection while offline")

    def ac_failure(self):
        r = self.runtime
        r.ac.set_online(False)
        r.set_temperature(HOT_TEMPERATURE_C)
        r.door.open()
        r.cctv.detect_resident("front_door", .97)
        r.motion.detect("living_room")
        passed = (
            r.state.occupied
            and r.state.devices["lights"]["power"]
            and not r.state.devices["ac"]["power"]
            and "Living room AC unavailable" in r.state.alerts
        )
        return ScenarioResult(
            "ac_failure", passed,
            "Comfort decision is generated but the failed AC action is surfaced and audited",
        )

    def internet_unavailable(self):
        r = self.runtime
        r.set_temperature(HOT_TEMPERATURE_C)
        blocked = r.network.simulate_external_attempt("SIMULATED-INTERNET", 1024)
        r.door.open()
        r.cctv.detect_resident("front_door", .97)
        passed = blocked["blocked"] and r.network.guard.external_bytes == 0 and r.state.occupied
        return ScenarioResult(
            "internet_unavailable", passed,
            "Core automation continues locally while the external route remains blocked",
        )

    def conflicting_sensors(self):
        r = self.runtime
        r.set_temperature(30.0)
        r.door.open()
        r.cctv.detect_resident("front_door", .96)
        r.motion.clear()
        r.bus.publish("sensor_conflict", {
            "cctv": "resident_detected",
            "motion": "no_motion",
            "interpretation": "occupancy_uncertain",
        }, source="SCENARIO")
        passed = r.state.occupied and any(
            "Occupancy evidence conflict" in alert for alert in r.state.alerts
        )
        return ScenarioResult(
            "conflicting_sensors", passed,
            "Conflicting evidence is surfaced as attention/uncertainty instead of being silently ignored",
        )

    def duplicate_event(self):
        r = self.runtime
        r.cctv.detect_resident("front_door", .96)
        evt = r.bus.history[-1]
        duplicate = r.bus.inject_duplicate(evt)
        passed = duplicate is False and r.bus.duplicates_rejected >= 1
        return ScenarioResult("duplicate_event", passed, "Event-bus deduplication rejected the repeated event id")

    def malformed_event(self):
        r = self.runtime
        malformed = r.network.receive({"sender": "TEMP-01"})
        passed = malformed is False and r.network.rejected_messages >= 1
        return ScenarioResult("malformed_event", passed, "Malformed authenticated frame rejected and audited")

    def stale_temperature(self):
        r = self.runtime
        r.set_temperature(HOT_TEMPERATURE_C)
        r.advance(31.0, report_temperature=False)
        r.validate_temperature_freshness()
        passed = not r.state.temperature_available
        return ScenarioResult(
            "stale_temperature", passed,
            "Stale temperature data is invalidated after the configured freshness window",
        )

    def unknown_device(self):
        r = self.runtime
        ok = r.network.receive({"sender": "GHOST", "recipient": "BRAIN-CORE", "seq": 1, "payload": {"type": "test"}, "signature": "x"})
        passed = ok is False and r.network.rejection_reasons.get("UNKNOWN_DEVICE", 0) >= 1
        return ScenarioResult("unknown_device", passed, "Unknown device identity rejected")

    def run_all(self):
        """Each scenario gets its own fresh runtime so outcomes are independent."""
        methods = [
            self.resident_returns_hot,
            self.resident_returns_comfortable,
            self.resident_leaves,
            self.unknown_person,
            self.temperature_sensor_failure,
            self.cctv_offline,
            self.ac_failure,
            self.internet_unavailable,
            self.conflicting_sensors,
            self.duplicate_event,
            self.malformed_event,
            self.stale_temperature,
            self.unknown_device,
        ]
        results = []
        for method in methods:
            self.runtime = self.runtime.reset()
            results.append(method())
        return results


def run_v06_demo(runtime, delay=0.0):
    """Camera-ready primary resident-return demo (CLI form)."""
    house = VirtualHouse(runtime)
    steps = [
        ("RESET — EMPTY DIGITAL TWIN", lambda: None),
        ("1. HOT EMPTY HOME", lambda: runtime.set_temperature(31.4)),
        ("2. FRONT DOOR OPENS", lambda: runtime.door.open()),
        ("3. LOCAL CCTV — RESIDENT DETECTED", lambda: runtime.cctv.detect_resident("front_door", .97)),
        ("4. MOTION CONFIRMS LOCAL ACTIVITY", lambda: runtime.motion.detect("living_room")),
        ("5. LOCAL BRAIN ACTIVATES COMFORT", lambda: None),
    ]
    for title, action in steps:
        print("\n" + "=" * 76)
        print(title)
        print("=" * 76)
        action()
        house.show_state()
        if delay:
            time.sleep(delay)

    print("\nCOOLING SIMULATION")
    for _ in range(26):
        runtime.advance(2.0)
        house.show_state()
        if delay:
            time.sleep(delay)
    return runtime
