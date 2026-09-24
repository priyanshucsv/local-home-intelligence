import unittest
from pathlib import Path

from core.runtime import LuminasRuntime
from devices.contracts import Camera, ClimateController, LightController
from security.local_only import LocalOnlyValidator
from simulation.scenarios import ScenarioRunner


class LuminasV06Tests(unittest.TestCase):
    def setUp(self):
        self.r = LuminasRuntime()

    def test_virtual_devices_match_hardware_independent_contracts(self):
        self.assertIsInstance(self.r.cctv, Camera)
        self.assertIsInstance(self.r.ac, ClimateController)
        self.assertIsInstance(self.r.lights, LightController)

    def test_primary_return_builds_context_and_actions(self):
        result = ScenarioRunner(self.r).resident_returns_hot(cooling_steps=2)
        self.assertTrue(result.passed)
        self.assertTrue(self.r.state.occupied)
        self.assertTrue(self.r.state.devices["lights"]["power"])
        self.assertTrue(self.r.state.devices["ac"]["power"])
        self.assertIn("DOOR", self.r.state.occupancy_evidence)
        self.assertIn("CCTV_RESIDENT", self.r.state.occupancy_evidence)

    def test_ac_temperature_moves_gradually(self):
        r = self.r
        r.set_temperature(31.4)
        r.door.open()
        r.cctv.detect_resident("front_door", .97)
        before = r.state.temperature_c
        r.advance(2)
        mid = r.state.temperature_c
        self.assertLess(mid, before)
        self.assertGreater(mid, 24.0)
        self.assertAlmostEqual(r.state.devices["ac"]["room_temperature_c"], mid, places=2)

    def test_sensor_failure_withholds_temperature_automation(self):
        r = self.r
        ScenarioRunner(r).resident_returns_hot(cooling_steps=1)
        r.inject_sensor_failure()
        self.assertFalse(r.state.temperature_available)
        self.assertIn("Temperature sensor unavailable", r.state.alerts)
        self.assertTrue(any(e["kind"] == "SECURITY EVENT" for e in r.audit.entries))

    def test_ac_failure_surfaces_failed_result(self):
        result = ScenarioRunner(self.r).ac_failure()
        self.assertTrue(result.passed)
        self.assertFalse(self.r.state.devices["ac"]["power"])
        self.assertTrue(any("FAILURE" in e["action"] for e in self.r.audit.entries if e["source"] == "AC"))

    def test_duplicate_event_is_rejected(self):
        result = ScenarioRunner(self.r).duplicate_event()
        self.assertTrue(result.passed)
        self.assertGreaterEqual(self.r.bus.duplicates_rejected, 1)

    def test_stale_sensor_marks_state_unavailable(self):
        result = ScenarioRunner(self.r).stale_temperature()
        self.assertTrue(result.passed)
        self.assertFalse(self.r.state.temperature_available)

    def test_local_only_validation(self):
        validation = LocalOnlyValidator(Path(__file__).resolve().parents[1]).validate(self.r)
        self.assertTrue(validation["passed"], validation)
        self.assertEqual(validation["application_external_transmission_bytes"], 0)
        self.assertEqual(validation["source_import_findings"], [])

    def test_dashboard_state_comes_from_runtime(self):
        self.r.set_temperature(31.4)
        self.r.door.open()
        self.r.cctv.detect_resident("front_door", .97)
        snap = self.r.state_snapshot()
        self.assertEqual(snap["home"]["temperature_c"], self.r.state.temperature_c)
        self.assertEqual(snap["devices"]["ac"]["power"], self.r.state.devices["ac"]["power"])
        self.assertEqual(snap["devices"]["door"]["open"], True)
        self.assertGreater(len(snap["events"]["recent_events"]), 0)


if __name__ == "__main__":
    unittest.main()
