class PrivacyMonitor:
    """Application-level local-only instrumentation.

    This does not sniff the host network interface. It reports what the
    Luminas process itself attempted through its guarded transport and which
    cloud/API dependencies are present in its runtime configuration.
    """

    def __init__(self):
        self.internet = False
        self.cloud = False
        self.bluetooth = False
        self.external_apis = False
        self.bytes_transmitted = 0
        self.external_attempts = 0
        self.external_api_attempts = 0
        self.measured_scope = "APPLICATION_LEVEL"
        self.validation_notes = "No OS-level packet capture; counters cover Luminas transport boundaries."
        self._guard = None

    def attach_guard(self, guard):
        self._guard = guard

    def snapshot(self):
        guard = self._guard
        return {
            "internet": self.internet,
            "cloud": self.cloud,
            "bluetooth": self.bluetooth,
            "external_apis": self.external_apis,
            "bytes_transmitted": int(guard.external_bytes if guard else self.bytes_transmitted),
            "external_attempts": int(guard.blocked_external_attempts if guard else self.external_attempts),
            "external_api_attempts": self.external_api_attempts,
            "status": "LOCAL ONLY" if not self.internet and not self.cloud and not self.external_apis else "ATTENTION",
            "measured_scope": self.measured_scope,
            "validation_notes": self.validation_notes,
        }
