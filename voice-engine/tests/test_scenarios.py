import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.state.session_store import store
from app.services.audio_utils import generate_mock_wav
from app.services.telephony_adapter import telephony_adapter

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_store():
    store.clear()
    yield
    store.clear()

def test_scenario_1_delivery():
    """Scenario 1 — Delivery: Caller calling about parcel delivery."""
    res = client.post("/api/demo/conversation", json={
        "language": "English",
        "caller_text": "Hello, I am calling about your parcel delivery."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "delivery"
    assert data["action"] == "ask_followup"
    assert data["should_escalate"] is False
    assert "delivery" in data["assistant_text"].lower() or "package" in data["assistant_text"].lower()

def test_scenario_2_appointment():
    """Scenario 2 — Appointment: Rescheduling appointment."""
    res = client.post("/api/demo/conversation", json={
        "language": "English",
        "caller_text": "I need to reschedule my appointment for tomorrow."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "appointment"
    assert data["action"] == "ask_followup"
    assert data["should_escalate"] is False
    assert "appointment" in data["assistant_text"].lower() or "date" in data["assistant_text"].lower()

def test_scenario_3_urgent():
    """Scenario 3 — Urgent: Urgent call requiring account holder immediate callback."""
    res = client.post("/api/demo/conversation", json={
        "language": "English",
        "caller_text": "This is urgent. Please ask the account holder to call me immediately."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "urgent_request"
    assert data["urgency"] == "high"
    assert data["action"] == "escalate"
    assert data["should_escalate"] is True
    assert data["session_status"] == "escalation_requested"

def test_scenario_4_unknown_purpose():
    """Scenario 4 — Unknown purpose: Caller wants to speak with account holder without stated reason."""
    res = client.post("/api/demo/conversation", json={
        "language": "English",
        "caller_text": "Hello, I need to speak with the account holder."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "unknown_purpose"
    assert data["action"] == "ask_followup"
    assert data["should_escalate"] is False
    assert "who is calling" in data["assistant_text"].lower() or "reason" in data["assistant_text"].lower()

def test_scenario_5_possible_scam():
    """Scenario 5 — Possible scam: Caller claims prize and solicits OTP."""
    res = client.post("/api/demo/conversation", json={
        "language": "English",
        "caller_text": "You have won a prize. Please tell me your OTP."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "possible_scam"
    assert data["spam_risk"] == "high"
    assert data["should_escalate"] is False
    # Crucial security assertion: Never disclose or request OTPs
    lower_resp = data["assistant_text"].lower()
    assert "never shared" in lower_resp or "cannot share" in lower_resp or "privacy" in lower_resp
    assert "here is your otp" not in lower_resp

def test_scenario_6_session_ended():
    """Scenario 6 — Session ended: End session, then submit another turn."""
    # Create session
    s_res = client.post("/api/sessions", json={"language": "English"}).json()
    session_id = s_res["session_id"]

    # End session
    end_res = client.post(f"/api/sessions/{session_id}/end")
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "ended"

    # Submit turn to ended session
    turn_res = client.post(f"/api/sessions/{session_id}/turn", json={
        "caller_text": "Are you still there?"
    })
    assert turn_res.status_code == 409
    assert "ended" in turn_res.json()["detail"].lower()

    # Verify no new turn was appended to history
    session = client.get(f"/api/sessions/{session_id}").json()
    assert len(session["turns"]) == 0

def test_scenario_7_invalid_audio():
    """Scenario 7 — Invalid audio: Unsupported format or empty file."""
    # 1. Empty audio file
    empty_res = client.post("/api/voice/transcribe", files={
        "file": ("empty.wav", io.BytesIO(b""), "audio/wav")
    })
    assert empty_res.status_code == 400
    assert "empty" in empty_res.json()["detail"].lower()

    # 2. Unsupported extension
    invalid_ext_res = client.post("/api/voice/transcribe", files={
        "file": ("malicious.exe", io.BytesIO(b"MZ12345"), "application/octet-stream")
    })
    assert invalid_ext_res.status_code == 400
    assert "unsupported" in invalid_ext_res.json()["detail"].lower()

def test_scenario_8_stt_tts_unavailable(monkeypatch):
    """Scenario 8 — STT or TTS unavailable: Disable provider and call endpoint."""
    monkeypatch.setattr(settings, "stt_provider", "disabled")
    monkeypatch.setattr(settings, "tts_provider", "disabled")

    # STT disabled
    wav_bytes = generate_mock_wav()
    stt_res = client.post("/api/voice/transcribe", files={
        "file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")
    })
    assert stt_res.status_code == 503
    assert "disabled" in stt_res.json()["detail"].lower()

    # TTS disabled
    tts_res = client.post("/api/voice/speak", data={"text": "Hello"})
    assert tts_res.status_code == 503
    assert "disabled" in tts_res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_telephony_adapter_simulation():
    """Verifies that the telephony integration boundary adapter operates correctly."""
    call_id = "airtel-call-001"
    session_id = await telephony_adapter.on_call_start(call_id, caller_number="+919876543210")
    assert session_id is not None

    # Simulate caller speaking
    turn_response = await telephony_adapter.on_speech_completed(call_id, "Hello, parcel delivery")
    assert turn_response.turn_number == 1
    assert turn_response.decision.intent == "delivery"

    # Simulate call hangup
    await telephony_adapter.on_call_end(call_id)
    session = store.get(session_id)
    assert session["status"] == "ended"

