from datetime import datetime, timezone
import uuid


class AuditLog:
    def __init__(self):
        self.entries = []

    def record(self, source, action, kind=None, details=None):
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        entry = {
            "id": f"audit-{uuid.uuid4().hex[:10]}",
            "time": datetime.now().strftime("%H:%M:%S"),
            "timestamp": timestamp,
            "kind": kind or self._infer_kind(source),
            "source": source,
            "action": action,
            "details": dict(details or {}),
        }
        self.entries.append(entry)
        return entry

    @staticmethod
    def _infer_kind(source):
        mapping = {
            "REASONING": "DECISION",
            "DECISION": "DECISION",
            "SECURITY": "SECURITY EVENT",
            "NETWORK": "ACTION",
            "AC": "RESULT",
            "LIGHTS": "RESULT",
            "CONTEXT": "CONTEXT",
            "IDENTITY": "SECURITY EVENT",
        }
        return mapping.get(source, "OBSERVATION")

    def snapshot(self, limit=40):
        return self.entries[-int(limit):]

    def print_report(self):
        print("\n========== LOCAL AUDIT ==========")
        for entry in self.entries:
            print(
                f'{entry["time"]} | {entry["kind"]:<15} | '
                f'{entry["source"]:<10} | {entry["action"]}'
            )
        print("=================================\n")
