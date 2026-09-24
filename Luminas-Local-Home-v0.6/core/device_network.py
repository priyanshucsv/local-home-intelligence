"""Hardened local device-to-device protocol simulation.

v0.6 preserves the v0.5 authenticated local transport and makes its guard
counters explicit so the dashboard can distinguish application-level local-only
validation from host-level network measurement.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
import time


@dataclass
class DeviceIdentity:
    device_id: str
    device_type: str
    zone: str
    secret: str
    trusted: bool = True


class LocalNetworkGuard:
    def __init__(self):
        self.internet = False
        self.bluetooth = False
        self.wifi_uplink = False
        self.external_routes = False
        self.blocked_external_attempts = 0
        self.external_api_attempts = 0
        self.external_bytes = 0

    def block_external_attempt(self, source="unknown", attempted_bytes=0, api=False):
        self.blocked_external_attempts += 1
        if api:
            self.external_api_attempts += 1
        return {
            "blocked": True,
            "source": source,
            "attempted_bytes": int(attempted_bytes),
            "transmitted_bytes": 0,
        }

    def snapshot(self):
        return {
            "internet": self.internet,
            "bluetooth": self.bluetooth,
            "wifi_uplink": self.wifi_uplink,
            "external_routes": self.external_routes,
            "blocked_external_attempts": self.blocked_external_attempts,
            "external_api_attempts": self.external_api_attempts,
            "external_bytes": self.external_bytes,
            "status": "ISOLATED",
            "measurement_scope": "APPLICATION_LEVEL",
        }


class LocalDeviceNetwork:
    """Authenticated local mesh with explicit protocol-hardening checks."""

    MAX_PAYLOAD_BYTES = 4096
    ALLOWED_TYPES = {
        "presence", "motion", "inactivity", "telemetry", "command",
        "heartbeat", "test", "door", "security", "fault",
    }

    def __init__(self, audit):
        self.audit = audit
        self.guard = LocalNetworkGuard()
        self.devices = {}
        self.sequences = {}
        self.messages = []
        self.rejected_messages = 0
        self.rejection_reasons = {}
        self.commands = []

    def _reject(self, reason, detail):
        self.rejected_messages += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
        self.audit.record("SECURITY", f"REJECT {reason} {detail}", kind="SECURITY EVENT")
        return False

    def register(self, device_id, device_type, zone, secret, trusted=True):
        if not device_id or not secret or device_id in self.devices:
            raise ValueError("Device identity must be unique and have a secret")
        self.devices[device_id] = DeviceIdentity(device_id, device_type, zone, secret, trusted)
        self.sequences[device_id] = 0
        self.audit.record("IDENTITY", f"REGISTER {device_id} type={device_type} zone={zone}")

    def set_trust(self, device_id, trusted):
        if device_id in self.devices:
            self.devices[device_id].trusted = bool(trusted)
            self.audit.record("IDENTITY", f"{'TRUSTED' if trusted else 'REVOKED'} {device_id}")
            return True
        return False

    def _validate_payload(self, payload):
        if not isinstance(payload, dict):
            return False, "MALFORMED_PAYLOAD"
        kind = payload.get("type")
        if kind not in self.ALLOWED_TYPES:
            return False, "UNKNOWN_MESSAGE_TYPE"
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if len(raw) > self.MAX_PAYLOAD_BYTES:
            return False, "PAYLOAD_TOO_LARGE"
        return True, None

    def _canonical(self, sender, recipient, seq, payload):
        return json.dumps(
            {"sender": sender, "recipient": recipient, "seq": seq, "payload": payload},
            sort_keys=True, separators=(",", ":"),
        ).encode()

    def _sign(self, identity, canonical):
        return hmac.new(identity.secret.encode(), canonical, hashlib.sha256).hexdigest()

    def build_frame(self, sender, recipient, payload, seq=None, secret_override=None):
        if sender not in self.devices:
            raise KeyError(sender)
        if seq is None:
            seq = self.sequences[sender] + 1
        canonical = self._canonical(sender, recipient, seq, payload)
        secret = secret_override if secret_override is not None else self.devices[sender].secret
        return {
            "sender": sender, "recipient": recipient, "seq": int(seq),
            "payload": payload, "signature": hmac.new(
                secret.encode(), canonical, hashlib.sha256
            ).hexdigest(),
        }

    def receive(self, frame):
        if not isinstance(frame, dict):
            return self._reject("MALFORMED_FRAME", "not_a_dict")
        required = {"sender", "recipient", "seq", "payload", "signature"}
        if not required.issubset(frame):
            return self._reject("MALFORMED_FRAME", "missing_fields")

        sender, recipient = frame["sender"], frame["recipient"]
        if sender not in self.devices or recipient not in self.devices:
            return self._reject("UNKNOWN_DEVICE", f"{sender}->{recipient}")
        src, dst = self.devices[sender], self.devices[recipient]
        if not src.trusted or not dst.trusted:
            return self._reject("UNTRUSTED_DEVICE", f"{sender}->{recipient}")

        try:
            seq = int(frame["seq"])
        except (TypeError, ValueError):
            return self._reject("BAD_SEQUENCE", sender)
        if seq <= self.sequences[sender]:
            return self._reject("REPLAY_OR_STALE", f"{sender} seq={seq}")
        if seq > self.sequences[sender] + 1:
            return self._reject("SEQUENCE_GAP", f"{sender} seq={seq}")

        valid, reason = self._validate_payload(frame["payload"])
        if not valid:
            return self._reject(reason, sender)

        canonical = self._canonical(sender, recipient, seq, frame["payload"])
        expected = self._sign(src, canonical)
        if not isinstance(frame["signature"], str) or not hmac.compare_digest(
            frame["signature"], expected
        ):
            return self._reject("BAD_SIGNATURE", f"{sender}->{recipient}")

        self.sequences[sender] = seq
        message = {
            "id": f"{sender}:{seq}",
            "timestamp": time.strftime("%H:%M:%S"),
            "sender": sender,
            "recipient": recipient,
            "seq": seq,
            "payload": frame["payload"],
            "authenticated": True,
            "transport": "LOCAL_ONLY",
        }
        self.messages.append(message)
        self.audit.record(
            "NETWORK",
            f"AUTH {sender}->{recipient} seq={seq} payload={frame['payload'].get('type')}",
        )
        return True

    def send(self, sender, recipient, payload):
        if sender not in self.devices or recipient not in self.devices:
            return self._reject("UNKNOWN_DEVICE", f"{sender}->{recipient}")
        frame = self.build_frame(sender, recipient, payload)
        return self.receive(frame)

    def send_command(self, command, target, payload=None):
        payload = dict(payload or {})
        payload["type"] = "command"
        payload["command"] = command
        ok = self.send("BRAIN-CORE", target, payload)
        result = "SUCCESS" if ok else "FAILURE"
        self.audit.record("NETWORK", f"AC/DEVICE COMMAND target={target} command={command} result={result}", kind="ACTION")
        if ok:
            self.commands.append({
                "command": command, "target": target, "payload": payload,
                "authenticated": True,
            })
        return ok

    def simulate_external_attempt(self, source="SIMULATED_THREAT", attempted_bytes=128, api=False):
        result = self.guard.block_external_attempt(source, attempted_bytes, api=api)
        self.audit.record("SECURITY", f"BLOCKED_EXTERNAL_ROUTE source={source}", kind="SECURITY EVENT")
        return result

    def snapshot(self):
        return {
            "guard": self.guard.snapshot(),
            "devices": [
                {
                    "device_id": d.device_id,
                    "type": d.device_type,
                    "zone": d.zone,
                    "trusted": d.trusted,
                    "last_seq": self.sequences.get(d.device_id, 0),
                }
                for d in self.devices.values()
            ],
            "messages": self.messages[-48:],
            "commands": self.commands[-24:],
            "rejected_messages": self.rejected_messages,
            "rejection_reasons": self.rejection_reasons,
        }
