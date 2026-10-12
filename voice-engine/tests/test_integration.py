import io
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.state.session_store import store
from app.services.audio_utils import generate_mock_wav

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_store_and_env(monkeypatch):
    store.clear()
    monkeypatch.setattr(settings, "ai_backend_url", "http://127.0.0.1:8000")
    monkeypatch.setattr(settings, "decision_api_url", None)
    yield
    store.clear()

def test_integration_turn1_turn2_delivery_flow():
    """
    Task D Tests 1 & 2:
    - Turn 1: Voice engine sends turn to AI backend, AI backend asks for clarification.
    - Turn 2: Voice engine sends FULL updated transcript (Turn 1 caller + agent + Turn 2 caller).
      AI backend recognizes the tracking reference ('TRK123456') and returns 'handle'.
      Voice engine uses the new response without repeating the old question.
    """
    turn1_backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-1",
        "action": "ask_clarification",
        "speak": "I can help with a delivery. Where should it be left, or what is the tracking or order reference?",
        "end_call": False,
        "intent": {"intent": "delivery", "confidence": 0.95, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": None, "source": "unknown", "verified": False, "statement": "Unknown caller"},
        "reasons": ["Delivery inquiry requires tracking reference or drop-off location."],
        "matched_rule_id": None,
        "caution": False,
        "caller_summary": "Delivery inquiry",
        "caller_message": "Hello, I need help while checking my delivery status.",
        "notification": {"title": "Delivery inquiry", "body": "Caller asking about delivery status", "priority": "normal"}
    }

    turn2_backend_response = {
        "schema_version": "1.0",
        "call_id": "test-call-1",
        "action": "handle",
        "speak": "Thanks for the delivery details. I have logged that for Alex.",
        "end_call": True,
        "intent": {"intent": "delivery", "confidence": 0.98, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        "identification": {"matched_contact": None, "source": "unknown", "verified": False, "statement": "Unknown caller"},
        "reasons": ["Tracking reference provided; logged for recipient."],
        "matched_rule_id": None,
        "caution": False,
        "caller_summary": "Delivery reference received: TRK123456",
        "caller_message": "My tracking reference is TRK123456. Can you check my delivery status?",
        "notification": {"title": "Delivery update", "body": "TRK123456 noted", "priority": "normal"}
    }

    captured_requests = []

    async def fake_post(url, json=None, **kwargs):
        captured_requests.append({"url": str(url), "json": json})
        if len(captured_requests) == 1:
            return httpx.Response(200, json=turn1_backend_response, request=httpx.Request("POST", str(url)))
        return httpx.Response(200, json=turn2_backend_response, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        # Create session
        s_res = client.post("/api/sessions", json={
            "caller_number": "+919876543210",
            "caller_name": "Delivery Person",
            "language": "English",
            "user_name": "Alex"
        })
        assert s_res.status_code == 200
        session_id = s_res.json()["session_id"]

        # === Turn 1 ===
        turn1_res = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "Hello, I need help while checking my delivery status.",
            "generate_audio": False
        })
        assert turn1_res.status_code == 200
        t1_data = turn1_res.json()
        assert t1_data["turn_number"] == 1
        assert t1_data["assistant_text"] == "I can help with a delivery. Where should it be left, or what is the tracking or order reference?"
        assert t1_data["decision"]["action"] == "ask_clarification"
        assert t1_data["decision"]["end_call"] is False
        assert t1_data["session_status"] == "active"

        # Verify Turn 1 request payload sent to Member 3
        assert len(captured_requests) == 1
        req1 = captured_requests[0]["json"]
        assert req1["call_id"] == session_id
        assert req1["caller"]["number"] == "+919876543210"
        assert req1["preferences"]["user_name"] == "Alex"
        assert len(req1["transcript"]) == 1
        assert req1["transcript"][0]["speaker"] == "caller"
        assert req1["transcript"][0]["text"] == "Hello, I need help while checking my delivery status."

        # === Turn 2 ===
        turn2_res = client.post(f"/api/sessions/{session_id}/turn", json={
            "caller_text": "My tracking reference is TRK123456. Can you check my delivery status?",
            "generate_audio": False
        })
        assert turn2_res.status_code == 200
        t2_data = turn2_res.json()
        assert t2_data["turn_number"] == 2
        # Assistant must use the new response and NOT repeat the old question
        assert t2_data["assistant_text"] == "Thanks for the delivery details. I have logged that for Alex."
        assert "where should it be left" not in t2_data["assistant_text"].lower()
        assert t2_data["decision"]["action"] == "handle"
        assert t2_data["decision"]["end_call"] is True
        assert t2_data["session_status"] == "ended"

        # Verify Turn 2 request payload sent to Member 3 had FULL conversation history
        assert len(captured_requests) == 2
        req2 = captured_requests[1]["json"]
        assert len(req2["transcript"]) == 3
        assert req2["transcript"][0] == {
            "speaker": "caller",
            "text": "Hello, I need help while checking my delivery status."
        }
        assert req2["transcript"][1] == {
            "speaker": "agent",
            "text": "I can help with a delivery. Where should it be left, or what is the tracking or order reference?"
        }
        assert req2["transcript"][2] == {
            "speaker": "caller",
            "text": "My tracking reference is TRK123456. Can you check my delivery status?"
        }


def test_integration_session_isolation():
    """
    Task D Test 3: Multi-turn session isolation.
    Multiple concurrent sessions do not cross-contaminate transcripts or state.
    """
    captured = []

    async def fake_post(url, json=None, **kwargs):
        captured.append(json)
        return httpx.Response(200, json={
            "schema_version": "1.0",
            "call_id": json["call_id"],
            "action": "ask_clarification",
            "speak": f"Response for {json['call_id']}",
            "end_call": False,
            "intent": {"intent": "general", "confidence": 0.8, "source": "rules"},
            "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
        }, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        # Create Session A
        sA = client.post("/api/sessions", json={"caller_number": "+1111111111", "caller_name": "Alice"}).json()["session_id"]
        # Create Session B
        sB = client.post("/api/sessions", json={"caller_number": "+2222222222", "caller_name": "Bob"}).json()["session_id"]

        # Turn on Session A
        client.post(f"/api/sessions/{sA}/turn", json={"caller_text": "Alice Turn 1"})
        # Turn on Session B
        client.post(f"/api/sessions/{sB}/turn", json={"caller_text": "Bob Turn 1"})
        # Second Turn on Session A
        client.post(f"/api/sessions/{sA}/turn", json={"caller_text": "Alice Turn 2"})

        # Check session histories in store
        histA = client.get(f"/api/sessions/{sA}").json()["turns"]
        histB = client.get(f"/api/sessions/{sB}").json()["turns"]

        # Session A must only contain Alice's turns (2 caller + 2 agent = 4)
        assert len(histA) == 4
        assert [t["text"] for t in histA if t["speaker"] == "caller"] == ["Alice Turn 1", "Alice Turn 2"]

        # Session B must only contain Bob's turns (1 caller + 1 agent = 2)
        assert len(histB) == 2
        assert [t["text"] for t in histB if t["speaker"] == "caller"] == ["Bob Turn 1"]


def test_integration_failure_handling_502():
    """
    Task D Test 4: Failure handling.
    If the AI backend is unreachable or returns an error, the voice engine returns
    HTTP 502 Bad Gateway rather than crashing or storing corrupted state.
    """
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        s_id = client.post("/api/sessions", json={"language": "English"}).json()["session_id"]

        # Calling turn when backend is unreachable
        res = client.post(f"/api/sessions/{s_id}/turn", json={"caller_text": "Can you hear me?"})
        assert res.status_code == 502
        assert "Decision engine unavailable" in res.json()["detail"]

        # Verify session state was NOT corrupted (no half-turns added)
        history = client.get(f"/api/sessions/{s_id}").json()["turns"]
        assert len(history) == 0

    with patch("httpx.AsyncClient.post", return_value=httpx.Response(500, text="Internal Server Error")):
        res2 = client.post(f"/api/sessions/{s_id}/turn", json={"caller_text": "Can you hear me now?"})
        assert res2.status_code == 502
        assert "Decision engine unavailable" in res2.json()["detail"]

        # Still no corrupted history
        history2 = client.get(f"/api/sessions/{s_id}").json()["turns"]
        assert len(history2) == 0


def test_integration_audio_generation_toggle(monkeypatch):
    """
    Task D Test 5: Audio generation toggle.
    - generate_audio=false skips TTS generation.
    - generate_audio=true returns an audio URL when TTS is configured.
    """
    decision_resp = {
        "schema_version": "1.0",
        "call_id": "test-audio",
        "action": "handle",
        "speak": "Your package has arrived at the front door.",
        "end_call": False,
        "intent": {"intent": "delivery", "confidence": 0.9, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
    }

    async def fake_post(*args, **kwargs):
        return httpx.Response(200, json=decision_resp, request=httpx.Request("POST", "http://127.0.0.1:8000/v1/decide"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        s_id = client.post("/api/sessions", json={"language": "English"}).json()["session_id"]

        # Case 1: generate_audio=False
        r1 = client.post(f"/api/sessions/{s_id}/turn", json={
            "caller_text": "Hello delivery",
            "generate_audio": False
        })
        assert r1.status_code == 200
        assert r1.json()["audio_generated"] is False
        assert r1.json()["audio_url"] is None

        # Case 2: generate_audio=True with mock TTS
        monkeypatch.setattr(settings, "tts_provider", "mock")
        r2 = client.post(f"/api/sessions/{s_id}/turn", json={
            "caller_text": "Where is it now?",
            "generate_audio": True
        })
        assert r2.status_code == 200
        assert r2.json()["audio_generated"] is True
        assert r2.json()["audio_url"] is not None
        assert r2.json()["audio_url"].startswith("/api/voice/audio/")


def test_integration_process_audio_with_ai_backend(monkeypatch):
    """
    Task D Test: End-to-end /api/voice/process-audio pipeline with AI Backend.
    """
    decision_resp = {
        "schema_version": "1.0",
        "call_id": "audio-turn",
        "action": "handle",
        "speak": "Thank you for the update. Have a great day.",
        "end_call": True,
        "intent": {"intent": "delivery", "confidence": 0.9, "source": "rules"},
        "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": [], "uncertain": False},
    }

    monkeypatch.setattr(settings, "stt_provider", "mock")
    wav_bytes = generate_mock_wav(duration_seconds=1.0)

    async def fake_post_audio(*args, **kwargs):
        return httpx.Response(200, json=decision_resp, request=httpx.Request("POST", "http://127.0.0.1:8000/v1/decide"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post_audio):
        files = {"file": ("caller_recording.wav", io.BytesIO(wav_bytes), "audio/wav")}
        res = client.post("/api/voice/process-audio", files=files, data={"generate_audio": "false"})
        assert res.status_code == 200
        data = res.json()
        assert data["turn_number"] == 1
        assert data["assistant_text"] == "Thank you for the update. Have a great day."
        assert data["decision"]["action"] == "handle"
        assert data["session_status"] == "ended"
