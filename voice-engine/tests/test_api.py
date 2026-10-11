import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.state.session_store import store

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_store():
    store.clear()
    yield
    store.clear()

def test_health():
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert res1.json()["status"] == "ok"
    assert "service" in res1.json()

    res2 = client.get("/api/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "ok"

def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert "service" in res.json()
    assert "/docs" in res.json()["docs"]

def test_create_and_get_session():
    # Create session
    payload = {
        "caller_number": "+919876543210",
        "caller_name": "Ravi Kumar",
        "language": "English"
    }
    create_res = client.post("/api/sessions", json=payload)
    assert create_res.status_code == 200
    data = create_res.json()
    session_id = data["session_id"]
    assert data["status"] == "active"
    assert data["caller_number"] == "+919876543210"
    assert data["caller_name"] == "Ravi Kumar"
    assert "created_at" in data

    # Retrieve session
    get_res = client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    session_data = get_res.json()
    assert session_data["session_id"] == session_id
    assert session_data["turns"] == []

    # Non-existent session
    unknown_res = client.get("/api/sessions/unknown-id-123")
    assert unknown_res.status_code == 404

def test_session_turn():
    s = client.post("/api/sessions", json={"language": "English"}).json()
    session_id = s["session_id"]

    # Turn 1
    r1 = client.post(f"/api/sessions/{session_id}/turn", json={"caller_text": "I am calling about a parcel delivery"})
    assert r1.status_code == 200
    res1 = r1.json()
    assert res1["turn_number"] == 1
    assert res1["decision"]["intent"] == "delivery"
    assert res1["session_status"] == "active"

    # Turn 2
    r2 = client.post(f"/api/sessions/{session_id}/turn", json={"caller_text": "Please leave it at the security desk"})
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["turn_number"] == 2

    # Verify history
    history = client.get(f"/api/sessions/{session_id}").json()["turns"]
    assert len(history) == 4  # 2 turns * 2 messages (caller + assistant)
    assert history[0]["speaker"] == "caller"
    assert history[1]["speaker"] == "assistant"
    assert "timestamp" in history[0]

def test_session_end_and_rejection():
    s = client.post("/api/sessions", json={"language": "English"}).json()
    session_id = s["session_id"]

    end_res = client.post(f"/api/sessions/{session_id}/end")
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "ended"

    # Post turn on ended session -> must be rejected (409)
    rejected_res = client.post(f"/api/sessions/{session_id}/turn", json={"caller_text": "Hello are you still there?"})
    assert rejected_res.status_code == 409
    assert "ended" in rejected_res.json()["detail"].lower()

    # Verify no new turns were added
    assert len(client.get(f"/api/sessions/{session_id}").json()["turns"]) == 0

def test_empty_caller_text():
    s = client.post("/api/sessions", json={"language": "English"}).json()
    res = client.post(f"/api/sessions/{s['session_id']}/turn", json={"caller_text": "   "})
    assert res.status_code == 400

def test_demo_conversation_endpoint():
    # 1. Without existing session
    demo_res1 = client.post("/api/demo/conversation", json={
        "caller_text": "Hello, I am calling about your parcel delivery."
    })
    assert demo_res1.status_code == 200
    data1 = demo_res1.json()
    assert data1["turn_number"] == 1
    assert data1["intent"] == "delivery"
    session_id = data1["session_id"]

    # 2. Reusing session_id for subsequent turn
    demo_res2 = client.post("/api/demo/conversation", json={
        "session_id": session_id,
        "caller_text": "Can you leave it with the neighbor?"
    })
    assert demo_res2.status_code == 200
    data2 = demo_res2.json()
    assert data2["session_id"] == session_id
    assert data2["turn_number"] == 2

    # 3. Non-existent session
    demo_res3 = client.post("/api/demo/conversation", json={
        "session_id": "non-existent-session-id",
        "caller_text": "Hello?"
    })
    assert demo_res3.status_code == 404

def test_audio_file_not_found():
    res = client.get("/api/voice/audio/missing_recording.wav")
    assert res.status_code == 404
