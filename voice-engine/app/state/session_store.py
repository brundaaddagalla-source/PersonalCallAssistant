from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

class SessionNotFound(Exception):
    pass

class SessionStore:
    # In-memory development store. Use a shared database for deployment.
    def __init__(self):
        self.items = {}
        self.lock = RLock()

    def create(
        self,
        caller_number=None,
        caller_name=None,
        language="English",
        is_known_contact=False,
        contact_group="none",
        number_withheld=False,
        user_name=None,
        do_not_disturb=False,
        max_clarification_turns=3,
        rules=None
    ):
        item = {
            "session_id": str(uuid4()),
            "caller_number": caller_number,
            "caller_name": caller_name,
            "language": language,
            "is_known_contact": is_known_contact,
            "contact_group": contact_group,
            "number_withheld": number_withheld,
            "user_name": user_name,
            "do_not_disturb": do_not_disturb,
            "max_clarification_turns": max_clarification_turns,
            "rules": rules or [],
            "status": "active",
            "turns": [],
            "created_at": datetime.now(timezone.utc),
            "previous_intent": None
        }
        with self.lock:
            self.items[item["session_id"]] = item
        return item


    def get(self, session_id):
        with self.lock:
            item = self.items.get(session_id)
            if item is None:
                raise SessionNotFound(session_id)
            return item

    def append_turn(self, session_id, turn):
        with self.lock:
            item = self.get(session_id)
            if "timestamp" not in turn:
                turn["timestamp"] = datetime.now(timezone.utc).isoformat()
            item["turns"].append(turn)
            item["previous_intent"] = turn.get("intent", item["previous_intent"])
            return item

    def set_status(self, session_id, status):
        with self.lock:
            item = self.get(session_id)
            item["status"] = status
            return item

    def clear(self):
        """Clears all sessions from the in-memory store. Used primarily in test suites."""
        with self.lock:
            self.items.clear()

store = SessionStore()

