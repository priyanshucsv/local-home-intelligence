"""v0.6 release-candidate tests: demo state machine, scenario isolation,
shared validation aggregation, Digital Twin labeling and demo-only credentials."""
import unittest

from core.runtime import LuminasRuntime
from security import validation
from simulation.scenarios import ScenarioRunner


class DemoControllerTests(unittest.TestCase):
    def setUp(self):
        self.r = LuminasRuntime()

    def test_demo_transitions_and_completes(self):
        states = []
        original = self.r.demo._set_state

        def spy(state, stage=None):
            states.append(state)
            original(state, stage)

        self.r.demo._set_state = spy
        self.assertTrue(self.r.demo.run_sync())
        self.assertEqual(self.r.demo.state, "COMPLETE")
        for expected in ("RESETTING", "DOOR_OPEN", "DETECTING_RESIDENT", "CONFIRMING_OCCUPANCY",
                         "EVALUATING_COMFORT", "ACTIVATING_COMFORT", "AC_COOLING"):
            self.assertIn(expected, states)
        snap = self.r.demo.snapshot()
        self.assertEqual(snap["demo_state"], "COMPLETE")
        self.assertFalse(snap["running"])
        self.assertTrue(self.r.state.occupied)
        self.assertTrue(self.r.state.devices["ac"]["power"])
        self.assertLessEqual(self.r.state.temperature_c, 24.0 + 0.05)

    def test_demo_reset_gives_deterministic_start(self):
        result = ScenarioRunner(self.r).resident_returns_hot(cooling_steps=2)
        self.assertTrue(result.passed)
        self.r.demo.run_sync()
        self.r.demo.reset_demo_state()
        self.assertEqual(self.r.demo.snapshot()["demo_state"], "IDLE")
        r2 = ScenarioRunner(self.r)
        result2 = r2.resident_returns_hot(cooling_steps=2)
        self.assertTrue(result2.passed, result2.summary)
        self.assertLess(self.r.state.temperature_c, 31.4)
        self.assertEqual(self.r.state.devices["ac"]["temperature_c"], 24.0)

    def test_demo_running_blocks_second_start(self):
        self.r.demo._set_state("AC_COOLING", "COOLING")
        self.assertTrue(self.r.demo.running())
        self.assertFalse(self.r.demo.run_in_background())

    def test_demo_snapshot_reports_running_state(self):
        snap = self.r.demo.snapshot()
        self.assertEqual(snap["demo_state"], "IDLE")
        self.assertFalse(snap["running"])
        self.r.demo._set_state("DOOR_OPEN", "DOOR")
        snap = self.r.demo.snapshot()
        self.assertTrue(snap["running"])
        self.assertEqual(snap["stages"][0]["label"], "DOOR")
        self.assertTrue(snap["stages"][0]["active"])


class ScenarioIsolationTests(unittest.TestCase):
    def test_each_scenario_starts_from_clean_runtime(self):
        runtime = LuminasRuntime()
        runtime.set_temperature(29.0)
        runtime.door.open()
        runtime.cctv.detect_resident("front_door", 0.97)
        runner = ScenarioRunner(runtime)
        results = runner.run_all()
        self.assertTrue(all(r.passed for r in results), [r.summary for r in results if not r.passed])

    def test_hot_scenario_reaches_target_temperature(self):
        runtime = LuminasRuntime()
        result = ScenarioRunner(runtime).resident_returns_hot()
        self.assertTrue(result.passed)
        self.assertAlmostEqual(runtime.state.temperature_c, 24.0, delta=0.06)
        self.assertFalse(runtime.state.devices["ac"]["cooling"])


class ValidationServiceTests(unittest.TestCase):
    def test_validation_guard_prevents_nested_discovery(self):
        from security import validation
        validation._UNIT_TEST_GUARD.active = True
        try:
            nested = validation.run_unit_tests()
            self.assertTrue(nested["passed"])
            self.assertTrue(nested.get("nested"))
        finally:
            validation._UNIT_TEST_GUARD.active = False

    def test_validation_partitions_categories_without_duplicate_logic(self):
        from security.threats import ThreatSuite
        suite = ThreatSuite(LuminasRuntime())
        suite.run()
        security, failure, local_only, other = validation._partition(suite.results)
        self.assertGreaterEqual(len(security), 11)
        self.assertGreaterEqual(len(failure), 9)
        self.assertEqual(len(other), 4)
        self.assertTrue(all(r.name.startswith("Primary demo:") for r in other))
        for name in ("Protocol: replay protection", "Failure scenario: ac_failure"):
            self.assertTrue(any(r.name == name for r in security + failure), name)
        local_group = validation._group("LOCAL-ONLY VALIDATION", local_only)
        self.assertGreaterEqual(local_group["checks_total"], 1)


class LabelingAndCredentialTests(unittest.TestCase):
    def test_every_device_reports_digital_twin_kind(self):
        runtime = LuminasRuntime()
        for name, device in {
            "cctv": runtime.cctv, "ac": runtime.ac, "lights": runtime.lights,
            "temperature": runtime.temperature, "motion": runtime.motion, "door": runtime.door,
        }.items():
            self.assertEqual(device.kind, "DIGITAL_TWIN", name)
            snap = device.state_snapshot()
            self.assertEqual(snap.get("kind"), "DIGITAL_TWIN", name)

    def test_runtime_snapshot_preserves_digital_twin_kind(self):
        snap = LuminasRuntime().state_snapshot()
        for name, device in snap["devices"].items():
            self.assertEqual(device.get("kind"), "DIGITAL_TWIN", name)

    def test_credentials_are_ephemeral_per_runtime(self):
        a = LuminasRuntime()
        b = LuminasRuntime()
        secrets_a = {d.secret for d in a.network.devices.values()}
        secrets_b = {d.secret for d in b.network.devices.values()}
        self.assertTrue(secrets_a)
        self.assertEqual(len(secrets_a), len(a.network.devices))
        self.assertFalse(secrets_a & secrets_b)
        for secret in secrets_a:
            self.assertGreaterEqual(len(secret), 32)

    def test_hardware_adapters_refuse_to_silently_simulate(self):
        from hardware.adapters import ClimateControllerAdapter, CameraAdapter
        with self.assertRaises(NotImplementedError):
            ClimateControllerAdapter("AC-01").set_temperature(24.0)
        with self.assertRaises(NotImplementedError):
            CameraAdapter("CCTV-01").emit_local_event("resident_detected", {})


if __name__ == "__main__":
    unittest.main()
