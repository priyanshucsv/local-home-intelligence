"""Local protocol hardening and failure-injection suite.

All cases are deterministic simulations. No real attack traffic is sent.
"""
from dataclasses import dataclass
from security.local_only import LocalOnlyValidator
from simulation.scenarios import ScenarioRunner


# Scenario names that demonstrate failure handling rather than the happy path.
FAILURE_SCENARIOS = {
    "temperature_sensor_failure",
    "cctv_offline",
    "ac_failure",
    "internet_unavailable",
    "conflicting_sensors",
    "duplicate_event",
    "malformed_event",
    "stale_temperature",
    "unknown_device",
}


@dataclass
class SecurityResult:
    name: str
    passed: bool
    expected: str
    observed: str


class ThreatSuite:
    def __init__(self, runtime):
        self.r = runtime
        self.results = []

    def check(self, name, expected, observed, passed):
        self.results.append(SecurityResult(name, bool(passed), expected, observed))

    def run(self):
        n = self.r.network
        self.results = []
        frame = n.build_frame("CCTV-01", "BRAIN-CORE", {"type": "test", "value": 1})
        ok = n.receive(frame)
        self.check("Protocol: valid authenticated frame", "ACCEPT", "ACCEPT" if ok else "REJECT", ok)

        replay = n.receive(frame)
        self.check("Protocol: replay protection", "REJECT", "REJECT" if not replay else "ACCEPT", not replay)

        tampered = n.build_frame("TEMP-01", "BRAIN-CORE", {"type": "telemetry", "temperature_c": 40})
        tampered["payload"]["temperature_c"] = 999
        ok = n.receive(tampered)
        self.check("Protocol: payload tamper detection", "REJECT", "REJECT" if not ok else "ACCEPT", not ok)

        badsig = n.build_frame("TEMP-01", "BRAIN-CORE", {"type": "telemetry", "temperature_c": 25}, secret_override="WRONG-KEY")
        ok = n.receive(badsig)
        self.check("Protocol: bad signature rejection", "REJECT", "REJECT" if not ok else "ACCEPT", not ok)

        unknown = {"sender": "GHOST", "recipient": "BRAIN-CORE", "seq": 1, "payload": {"type": "test"}, "signature": "x"}
        ok = n.receive(unknown)
        self.check("Protocol: unknown identity rejection", "REJECT", "REJECT" if not ok else "ACCEPT", not ok)

        revoked = n.build_frame("CCTV-01", "BRAIN-CORE", {"type": "test", "value": 2}, seq=n.sequences["CCTV-01"] + 1)
        n.set_trust("CCTV-01", False)
        ok = n.receive(revoked)
        self.check("Protocol: revoked identity rejection", "REJECT", "REJECT" if not ok else "ACCEPT", not ok)
        n.set_trust("CCTV-01", True)

        gap = n.build_frame("CCTV-01", "BRAIN-CORE", {"type": "test"}, seq=n.sequences["CCTV-01"] + 2)
        ok = n.receive(gap)
        self.check("Protocol: sequence-gap rejection", "REJECT", "REJECT" if not ok else "ACCEPT", not ok)

        oversized = {"type": "test", "blob": "x" * 5000}
        ok = n.send("TEMP-01", "BRAIN-CORE", oversized)
        self.check("Protocol: oversized payload rejection", "REJECT", "REJECT" if not ok else "ACCEPT", not ok)

        malformed = n.receive({"sender": "TEMP-01"})
        self.check("Protocol: malformed frame rejection", "REJECT", "REJECT" if not malformed else "ACCEPT", not malformed)

        unknown_type = n.send("TEMP-01", "BRAIN-CORE", {"type": "execute_shell", "cmd": "x"})
        self.check("Protocol: unknown message type rejection", "REJECT", "REJECT" if not unknown_type else "ACCEPT", not unknown_type)

        ext = n.simulate_external_attempt("THREAT-SIM", 4096, api=True)
        self.check("Protocol: external route isolation", "BLOCK", "BLOCK" if ext["blocked"] else "ALLOW", ext["blocked"])
        self.check("Local-only: zero external bytes", "0", str(n.guard.external_bytes), n.guard.external_bytes == 0)

        scenario = ScenarioRunner(self.r)
        for result in scenario.run_all():
            category = "Failure scenario" if result.name in FAILURE_SCENARIOS else "Primary demo"
            self.check(
                f"{category}: {result.name}",
                "PASS",
                result.summary if result.passed else f"FAILED: {result.summary}",
                result.passed,
            )

        self.r = scenario.runtime
        local = LocalOnlyValidator().validate(self.r)
        self.check(
            "Local-only: application validation",
            "PASS",
            "PASS" if local["passed"] else str(local),
            local["passed"],
        )
        return self.results

    @property
    def passed(self):
        return sum(r.passed for r in self.results)

    def report(self):
        return {
            "total": len(self.results),
            "passed": self.passed,
            "failed": len(self.results) - self.passed,
            "results": [r.__dict__ for r in self.results],
        }
