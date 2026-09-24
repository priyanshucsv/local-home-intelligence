import argparse
import sys

# Windows consoles often default to cp1252; the runtime prints °C and arrows.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from core.runtime import LuminasRuntime
from security.validation import run_full_validation, print_validation_report
from simulation.scenarios import ScenarioRunner, run_v06_demo


def run_validation():
    report = run_full_validation()
    ok = print_validation_report(report)
    return 0 if ok else 1


SCENARIOS = (
    "resident_returns_hot", "resident_returns_comfortable", "resident_leaves",
    "unknown_person", "temperature_sensor_failure", "cctv_offline", "ac_failure",
    "internet_unavailable", "conflicting_sensors", "duplicate_event", "malformed_event",
    "stale_temperature", "unknown_device",
)


def run_scenario(name):
    runtime = LuminasRuntime()
    result = getattr(ScenarioRunner(runtime), name)()
    print(f"[{'PASS' if result.passed else 'FAIL'}] {result.name}: {result.summary}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Luminas Local Home v0.6")
    parser.add_argument("--validate", action="store_true", help="run the full release validation (unit tests, Digital Twin demo, security/protocol, failure scenarios, local-only)")
    parser.add_argument("--scenario", choices=list(SCENARIOS), help="run one deterministic Digital Twin scenario")
    args = parser.parse_args()

    if args.validate:
        raise SystemExit(run_validation())

    if args.scenario:
        raise SystemExit(run_scenario(args.scenario))

    runtime = LuminasRuntime()
    runtime.run()
    run_v06_demo(runtime, delay=0.15)
