import unittest
from core.runtime import LuminasRuntime
from security.threats import ThreatSuite


class LuminasV05Tests(unittest.TestCase):
    def test_security_suite_is_clean(self):
        report = ThreatSuite(LuminasRuntime()).report()  # report before run is empty
        suite = ThreatSuite(LuminasRuntime())
        suite.run()
        self.assertEqual(suite.passed, len(suite.results), suite.report())

    def test_brain_to_device_commands_are_authenticated(self):
        r = LuminasRuntime()
        r.set_temperature(31)
        r.cctv.detect_resident()
        commands = r.network.commands
        self.assertTrue(commands)
        self.assertTrue(all(c["authenticated"] for c in commands))
        self.assertTrue(any(c["target"] == "AC-01" for c in commands))

    def test_revoked_cctv_cannot_trigger_home_event(self):
        r = LuminasRuntime()
        r.network.set_trust("CCTV-01", False)
        self.assertFalse(r.cctv.detect_resident())
        self.assertFalse(r.state.occupied)
        self.assertEqual(r.network.rejected_messages, 1)

    def test_external_bytes_stay_zero(self):
        r = LuminasRuntime()
        r.network.simulate_external_attempt("TEST", 99999)
        self.assertEqual(r.network.guard.external_bytes, 0)


if __name__ == "__main__":
    unittest.main()
