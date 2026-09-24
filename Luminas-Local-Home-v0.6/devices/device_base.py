from typing import Any, Dict, Optional


class LocalDevice:
    """Common implementation used by simulated local devices.

    The class contains identity/lifecycle helpers only. Intelligence code is
    written against the contracts in ``devices.contracts`` rather than this
    concrete class, so a physical adapter can replace the simulator.
    """

    kind = "DIGITAL_TWIN"

    def __init__(self, device_id, device_type, zone, network=None, audit=None, capabilities=()):
        self.device_id = device_id
        self.device_type = device_type
        self.zone = zone
        self.network = network
        self.audit = audit
        self.capabilities = tuple(capabilities)
        self.online = True
        self.last_error: Optional[str] = None

    def send(self, recipient, payload):
        if self.network is None:
            return False
        if not self.online:
            if self.audit:
                self.audit.record("DEVICE", f"SEND_FAILED {self.device_id} OFFLINE")
            return False
        return self.network.send(self.device_id, recipient, payload)

    def identity(self):
        if self.network is not None and self.device_id in self.network.devices:
            d = self.network.devices[self.device_id]
            return {
                "id": d.device_id,
                "type": d.device_type,
                "zone": d.zone,
                "trusted": d.trusted,
                "last_seq": self.network.sequences[self.device_id],
            }
        return {
            "id": self.device_id,
            "type": self.device_type,
            "zone": self.zone,
            "trusted": self.online,
            "last_seq": 0,
        }

    def health(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "zone": self.zone,
            "kind": self.kind,
            "online": self.online,
            "available": self.online,
            "capabilities": list(self.capabilities),
            "last_error": self.last_error,
        }

    def state_snapshot(self) -> Dict[str, Any]:
        return self.health()

    def set_online(self, online: bool):
        self.online = bool(online)
        self.last_error = None if self.online else "DEVICE_OFFLINE"
        if self.audit:
            self.audit.record(
                "DEVICE",
                f"{self.device_id} {'ONLINE' if self.online else 'OFFLINE'}",
            )
        return self.online
