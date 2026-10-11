import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.models.schemas import SessionCreate
from app.services.decision_client import DecisionClient
from app.state.session_store import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store_and_env(monkeypatch):
    store.clear()
    monkeypatch.setattr(settings, "ai_backend_url", "http://127.0.0.1:8000")
    monkeypatch.setattr(settings, "decision_api_url", None)
    yield
    store.clear()


def test_android_examples_survive_voice_to_decision_mapping():
    """Verify that Android Member 2 caller examples deserialize and map accurately to Member 3 schema."""
    examples_path = Path(__file__).resolve().parents[2] / "docs/member2-caller-examples.json"
    examples = json.loads(examples_path.read_text())
    for example in examples:
        session = SessionCreate.model_validate(example["voice_session"])
        body = DecisionClient()._build_request_body({**session.model_dump(), "session_id": "provider-test-call"})
        assert body["caller"] == example["caller"]


def test_saved_caller_work_flow():
    """Flow: Saved caller (work/personal) makes a call handled by Member 4 and Member 3."""
    saved_caller_session = {
        "caller_number": "+919876543210",
        "is_known_contact": True,
        "caller_name": "Priya Sharma",
        "contact_group": "work",
        "number_withheld": False,
        "language": "English",
        "user_name": "Alex",
    }

    turn_backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-work",
        "action": "take_message",
        "speak": "Hi Priya, Alex is in a meeting. Would you like to leave a message regarding the quarterly budget?",
        "end_call": False,
        "intent": {"intent": "work", "confidence": 0.95, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": "Priya Sharma", "source": "contacts", "verified": False, "statement": "Matches saved contact Priya Sharma."},
        "reasons": ["Known contact during workday."],
        "caller_summary": "Priya Sharma calling about quarterly sales budget",
        "notification": {"title": "Call from Priya Sharma", "body": "Quarterly budget review", "priority": "normal"}
    }

    captured_requests = []

    async def fake_post(url, json=None, **kwargs):
        captured_requests.append({"url": str(url), "json": json})
        return httpx.Response(200, json=turn_backend_response, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        s_res = client.post("/api/sessions", json=saved_caller_session)
        assert s_res.status_code == 200
        session_id = s_res.json()["session_id"]

        turn_res = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "Hi Alex, let's review the quarterly sales budget tomorrow morning.",
            "generate_audio": False
        })
        assert turn_res.status_code == 200
        t_data = turn_res.json()
        assert t_data["decision"]["action"] == "take_message"
        assert "Priya" in t_data["assistant_text"]

        assert len(captured_requests) == 1
        req = captured_requests[0]["json"]
        assert req["caller"]["number"] == "+919876543210"
        assert req["caller"]["is_known_contact"] is True
        assert req["caller"]["contact_name"] == "Priya Sharma"
        assert req["caller"]["contact_group"] == "work"


def test_unsaved_caller_delivery_two_turn_flow():
    """Flow: Unsaved caller (delivery) provides tracking reference across two turns."""
    unsaved_caller_session = {
        "caller_number": "+919123456789",
        "is_known_contact": False,
        "caller_name": None,
        "contact_group": "none",
        "number_withheld": False,
        "language": "English",
        "user_name": "Alex",
    }

    turn1_backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-deliv",
        "action": "ask_clarification",
        "speak": "I can help with your delivery. Where should it be left, or what is the tracking reference?",
        "end_call": False,
        "intent": {"intent": "delivery", "confidence": 0.95, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": None, "source": "unknown", "verified": False, "statement": "Unknown caller"},
        "reasons": ["Delivery inquiry requires tracking reference."],
    }

    turn2_backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-deliv",
        "action": "handle",
        "speak": "Thanks for the delivery details. I have logged reference BLU998877 for Alex.",
        "end_call": True,
        "intent": {"intent": "delivery", "confidence": 0.98, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": None, "source": "unknown", "verified": False, "statement": "Unknown caller"},
        "reasons": ["Tracking reference provided."],
    }

    captured_requests = []

    async def fake_post(url, json=None, **kwargs):
        captured_requests.append({"url": str(url), "json": json})
        if len(captured_requests) == 1:
            return httpx.Response(200, json=turn1_backend_response, request=httpx.Request("POST", str(url)))
        return httpx.Response(200, json=turn2_backend_response, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        s_res = client.post("/api/sessions", json=unsaved_caller_session)
        assert s_res.status_code == 200
        session_id = s_res.json()["session_id"]

        # Turn 1
        t1 = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "Hello, I am calling with a package delivery from BlueDart.",
            "generate_audio": False
        }).json()
        assert t1["decision"]["action"] == "ask_clarification"
        assert t1["session_status"] == "active"

        # Turn 2
        t2 = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "The tracking reference is BLU998877. Can I leave it at the gate?",
            "generate_audio": False
        }).json()
        assert t2["decision"]["action"] == "handle"
        assert t2["session_status"] == "ended"

        # Verify second turn contained cumulative transcript
        req2 = captured_requests[1]["json"]
        assert len(req2["transcript"]) == 3  # Turn 1 caller + agent + Turn 2 caller


def test_unknown_caller_callback_request():
    """Flow: Unknown caller asks for a callback; Member 3 logs message and notifies user."""
    unknown_session = {
        "caller_number": "+919988776655",
        "is_known_contact": False,
        "caller_name": None,
        "language": "English",
    }

    backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-cb",
        "action": "take_message",
        "speak": "I will let Alex know you called and asked for a callback regarding the lease agreement.",
        "end_call": True,
        "intent": {"intent": "personal", "confidence": 0.90, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": None, "source": "unknown", "verified": False, "statement": "Unknown caller"},
        "reasons": ["Callback request noted."],
        "notification": {"title": "Callback Request", "body": "Caller requested callback for lease agreement", "priority": "normal"}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=httpx.Response(200, json=backend_response, request=httpx.Request("POST", "http://fake"))):
        s_res = client.post("/api/sessions", json=unknown_session)
        session_id = s_res.json()["session_id"]

        turn_res = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "Please ask Alex to call me back regarding the lease agreement.",
            "generate_audio": False
        })
        assert turn_res.status_code == 200
        data = turn_res.json()
        assert data["decision"]["action"] == "take_message"
        assert data["session_status"] == "ended"


def test_urgent_matter_escalation_flow():
    """Flow: Urgent or emergency caller triggers escalation and transfer."""
    emergency_session = {
        "caller_number": "+919876543210",
        "is_known_contact": True,
        "caller_name": "Dr. Verma",
        "contact_group": "family",
        "language": "English",
    }

    backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-urgent",
        "action": "transfer",
        "speak": "This sounds urgent. Connecting you to Alex immediately.",
        "end_call": False,
        "intent": {"intent": "emergency", "confidence": 0.99, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": "Dr. Verma", "source": "contacts", "verified": False, "statement": "Dr. Verma"},
        "reasons": ["Emergency situation requires immediate transfer."],
        "notification": {"title": "URGENT CALL", "body": "Dr. Verma reporting emergency", "priority": "high"}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=httpx.Response(200, json=backend_response, request=httpx.Request("POST", "http://fake"))):
        s_res = client.post("/api/sessions", json=emergency_session)
        session_id = s_res.json()["session_id"]

        turn_res = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "This is an emergency medical situation. Connect me to Alex immediately!",
            "generate_audio": False
        })
        assert turn_res.status_code == 200
        data = turn_res.json()
        assert data["decision"]["action"] == "transfer"
        assert data["decision"]["should_escalate"] is True
        assert data["session_status"] == "escalation_requested"


def test_suspicious_caller_security_flow():
    """Flow: Suspicious scam call asking for OTP is blocked and never rewarded."""
    scam_session = {
        "caller_number": "+918888888888",
        "is_known_contact": False,
        "caller_name": None,
        "language": "English",
    }

    backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-scam",
        "action": "block",
        "speak": "We do not share one-time passwords or bank details. This call is being terminated.",
        "end_call": True,
        "intent": {"intent": "prize_offer", "confidence": 0.95, "source": "rules"},
        "risk": {"label": "fraud", "score": 90, "confidence": 0.9, "signals": ["otp_request", "lottery"], "uncertain": False},
        "identification": {"matched_contact": None, "source": "unknown", "verified": False, "statement": "Suspicious caller"},
        "reasons": ["Soliciting OTP is flagged as fraud risk."],
        "notification": {"title": "Scam Call Blocked", "body": "Caller solicited OTP", "priority": "normal"}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=httpx.Response(200, json=backend_response, request=httpx.Request("POST", "http://fake"))):
        s_res = client.post("/api/sessions", json=scam_session)
        session_id = s_res.json()["session_id"]

        turn_res = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "You won 50000 rupees in a lottery! Share your OTP right now to claim it.",
            "generate_audio": False
        })
        assert turn_res.status_code == 200
        data = turn_res.json()
        assert data["decision"]["action"] == "block"
        assert data["session_status"] == "ended"
        assert "otp" not in data["assistant_text"].lower() or "not share" in data["assistant_text"].lower()
