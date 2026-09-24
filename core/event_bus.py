"""Small deterministic in-process local event bus with event history/dedup."""
from datetime import datetime, timezone
import uuid


class EventBus:
    def __init__(self, max_history=300):
        self._subscribers = {}
        self.history = []
        self._seen_event_ids = set()
        self.max_history = int(max_history)
        self.duplicates_rejected = 0

    def subscribe(self, event_type, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data=None, source="LOCAL_EVENT_BUS", event_id=None, timestamp=None):
        data = dict(data or {})
        event_id = event_id or f"evt-{uuid.uuid4().hex[:12]}"
        if event_id in self._seen_event_ids:
            self.duplicates_rejected += 1
            return False
        self._seen_event_ids.add(event_id)
        event = {
            "id": event_id,
            "type": event_type,
            "data": data,
            "source": source,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }
        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]
        for handler in self._subscribers.get(event_type, []):
            handler(event)
        return event

    def inject_duplicate(self, event):
        """Replay an already-published event id; the bus must refuse it."""
        if not isinstance(event, dict):
            return False
        return self.publish(
            event.get("type", "unknown"),
            event.get("data", {}),
            source=event.get("source", "INJECTED_DUPLICATE"),
            event_id=event.get("id"),
            timestamp=event.get("timestamp"),
        )

    def snapshot(self, limit=50):
        return {
            "recent_events": self.history[-int(limit) :],
            "duplicates_rejected": self.duplicates_rejected,
        }
