"""Shared validation service used by ``main.py --validate``, the dashboard and RUN_FULL_VALIDATION.bat.

There is deliberately only ONE validation implementation. It:

1. actually executes the Python unit test suite (stdlib unittest)
2. runs the Digital Twin primary demo scenario
3. runs the security/protocol validation
4. runs the failure-scenario validation
5. runs the application-level local-only validation

and returns structured results with a single overall pass/fail.
"""
from io import StringIO
from pathlib import Path
import threading
import unittest

from core.runtime import LuminasRuntime
from security.local_only import LocalOnlyValidator
from security.threats import ThreatSuite
from simulation.scenarios import ScenarioRunner

CATEGORY_PREFIXES = ("Protocol:", "Failure scenario:", "Local-only:", "Primary demo:")


def _partition(results):
    security, failure, local_only, other = [], [], [], []
    for result in results:
        if result.name.startswith("Protocol:"):
            security.append(result)
        elif result.name.startswith("Failure scenario:"):
            failure.append(result)
        elif result.name.startswith("Local-only:"):
            local_only.append(result)
        else:
            other.append(result)
    return security, failure, local_only, other


def _group(name, results):
    passed = sum(1 for r in results if r.passed)
    return {
        "name": name,
        "passed": passed == len(results) and bool(results),
        "checks_passed": passed,
        "checks_total": len(results),
        "results": [r.__dict__ for r in results],
    }


_UNIT_TEST_GUARD = threading.local()


def run_unit_tests():
    """Actually execute the project's unit test suite via stdlib unittest.

    A re-entrancy guard prevents infinite recursion when the suite itself is
    executed from inside a validation run (the suite contains validation
    aggregation tests).
    """
    if getattr(_UNIT_TEST_GUARD, "active", False):
        return {
            "name": "UNIT TESTS", "passed": True, "run": 0, "errors": 0,
            "failures": 0, "skipped": 0, "output": [], "nested": True,
            "note": "Nested unit-test discovery skipped: validation already running.",
        }
    _UNIT_TEST_GUARD.active = True
    try:
        root = Path(__file__).resolve().parents[1]
        loader = unittest.TestLoader()
        suite = loader.discover(str(root / "tests"), top_level_dir=str(root))
        stream = StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=1)
        result = runner.run(suite)
        return {
            "name": "UNIT TESTS",
            "passed": result.wasSuccessful(),
            "run": result.testsRun,
            "errors": len(result.errors),
            "failures": len(result.failures),
            "skipped": len(result.skipped),
            "output": stream.getvalue().strip().splitlines()[-6:],
        }
    finally:
        _UNIT_TEST_GUARD.active = False


def run_primary_demo():
    runtime = LuminasRuntime()
    result = ScenarioRunner(runtime).resident_returns_hot()
    return {"name": "PRIMARY DIGITAL TWIN DEMO", "passed": result.passed, "detail": result.summary}


def run_security_and_failure():
    """One deterministic ThreatSuite run feeds the protocol, failure and
    local-only categories (no duplicated validation logic)."""
    suite = ThreatSuite(LuminasRuntime())
    suite.run()
    security, failure, local_only, _other = _partition(suite.results)
    local = LocalOnlyValidator().validate(suite.r)
    local_only_group = _group("LOCAL-ONLY VALIDATION", local_only)
    local_only_group["external_transmission_bytes"] = local["application_external_transmission_bytes"]
    local_only_group["source_import_findings"] = local["source_import_findings"]
    local_only_group["passed"] = local_only_group["passed"] and local["passed"]
    return _group("SECURITY / PROTOCOL", security), _group("FAILURE SCENARIOS", failure), local_only_group


def run_full_validation():
    """The single authoritative validation entry point."""
    unit = run_unit_tests()
    demo = run_primary_demo()
    security, failure, local_only = run_security_and_failure()
    groups = [unit, demo, security, failure, local_only]
    passed = sum(1 for g in groups if g["passed"])
    failed = sum(1 for g in groups if not g["passed"])
    return {
        "unit_tests": unit,
        "primary_demo": demo,
        "security": security,
        "failure_scenarios": failure,
        "local_only": local_only,
        "passed": passed,
        "failed": failed,
        "ok": failed == 0,
    }


def print_validation_report(report):
    line = "=" * 56
    print(line)
    print("LUMINAS LOCAL HOME v0.6 VALIDATION")
    print(line)

    def _flag(ok):
        return "PASS" if ok else "FAIL"

    unit = report["unit_tests"]
    print(f"Unit tests:             {_flag(unit['passed'])}  ({unit['run']} tests)")
    print(f"Digital Twin demo:      {_flag(report['primary_demo']['passed'])}  ({report['primary_demo']['detail']})")
    sec = report["security"]
    print(f"Security protocol:      {_flag(sec['passed'])}  ({sec['checks_passed']}/{sec['checks_total']} checks)")
    fail = report["failure_scenarios"]
    print(f"Failure scenarios:      {_flag(fail['passed'])}  ({fail['checks_passed']}/{fail['checks_total']} checks)")
    loc = report["local_only"]
    print(f"Local-only validation:  {_flag(loc['passed'])}  (external bytes {loc['external_transmission_bytes']})")
    print()

    if not report["ok"]:
        print("Failures:")
        for key in ("unit_tests", "primary_demo", "security", "failure_scenarios", "local_only"):
            group = report[key]
            if group["passed"]:
                continue
            if key == "unit_tests":
                print("  UNIT TESTS:")
                for text in unit["output"]:
                    print(f"    {text}")
            else:
                for result in group["results"]:
                    if not result["passed"]:
                        print(f"  {result['name']}: {result.get('observed', result.get('summary', ''))}")
        print()

    print(f"FINAL RESULT: {'PASS' if report['ok'] else 'FAIL'}")
    print(line)
    return report["ok"]
