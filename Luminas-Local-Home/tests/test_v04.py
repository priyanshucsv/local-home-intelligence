
import unittest
from core.runtime import LuminasRuntime


class LuminasV04Tests(unittest.TestCase):
    def setUp(self):
        self.r = LuminasRuntime()

    def test_arrival_and_local_control(self):
        self.r.set_temperature(31)
        self.r.cctv.detect_resident()
        self.assertTrue(self.r.state.devices["ac"]["power"])
        self.assertTrue(self.r.state.devices["lights"]["power"])
        self.assertTrue(self.r.network.messages)
        self.assertTrue(all(m["authenticated"] for m in self.r.network.messages))

    def test_guest_profile(self):
        self.r.set_temperature(31)
        self.r.cctv.detect_guest()
        self.assertEqual(self.r.state.mode, "GUEST")
        self.assertEqual(self.r.state.devices["ac"]["temperature_c"], 25.0)

    def test_empty_home_priority(self):
        self.r.set_temperature(32)
        self.r.cctv.detect_resident()
        self.r.cctv.detect_resident_leave()
        self.assertEqual(self.r.state.mode, "EMPTY")
        self.assertFalse(self.r.state.devices["ac"]["power"])
        self.assertFalse(self.r.state.devices["lights"]["power"])

    def test_identity_registry(self):
        ids = set(self.r.network.devices)
        self.assertEqual(
            ids, {"BRAIN-CORE", "CCTV-01", "TEMP-01", "AC-01", "LIGHT-01"}
        )
        self.assertTrue(all(d.trusted for d in self.r.network.devices.values()))

    def test_revoked_device_is_rejected(self):
        self.r.network.set_trust("CCTV-01", False)
        ok = self.r.network.send("CCTV-01", "BRAIN-CORE", {"type": "test"})
        self.assertFalse(ok)
        self.assertEqual(self.r.network.rejected_messages, 1)

    def test_external_route_is_blocked(self):
        result = self.r.network.simulate_external_attempt("TEST-HOST")
        self.assertTrue(result["blocked"])
        self.assertEqual(self.r.network.guard.external_bytes, 0)
        self.assertEqual(self.r.network.guard.blocked_external_attempts, 1)

    def test_privacy_target(self):
        p = self.r.privacy.snapshot()
        self.assertFalse(p["internet"])
        self.assertFalse(p["cloud"])
        self.assertFalse(p["bluetooth"])
        self.assertFalse(p["external_apis"])
        self.assertEqual(p["bytes_transmitted"], 0)

    def test_reasoning_logged(self):
        self.r.set_temperature(31)
        self.r.cctv.detect_resident()
        self.assertTrue(any(e["source"] == "REASONING" for e in self.r.audit.entries))


if __name__ == "__main__":
    unittest.main()
