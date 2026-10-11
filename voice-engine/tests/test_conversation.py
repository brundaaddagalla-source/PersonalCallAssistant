import pytest
from app.services.conversation_manager import ConversationManager
from app.services.decision_client import DecisionClient, DecisionClientError
from app.state.session_store import store
from app.config import settings

@pytest.fixture(autouse=True)
def clean_store():
    store.clear()
    yield
    store.clear()

@pytest.mark.asyncio
async def test_turn_adds_caller_and_assistant():
    s = store.create(caller_number="+919876543210", caller_name="Amit")
    manager = ConversationManager(DecisionClient(base_url=""))
    result = await manager.process_turn(s["session_id"], "parcel delivery")

    assert result.turn_number == 1
    assert result.caller_text == "parcel delivery"
    assert "assist with your delivery" in result.assistant_text.lower() or "delivery" in result.assistant_text.lower()
    
    turns = store.get(s["session_id"])["turns"]
    assert len(turns) == 2
    assert turns[0]["speaker"] == "caller"
    assert turns[0]["turn_number"] == 1
    assert turns[0]["text"] == "parcel delivery"
    assert "timestamp" in turns[0]

    assert turns[1]["speaker"] == "assistant"
    assert turns[1]["turn_number"] == 1
    assert turns[1]["action"] == "ask_followup"
    assert "timestamp" in turns[1]

@pytest.mark.asyncio
async def test_multiple_turns_sequence():
    s = store.create()
    manager = ConversationManager(DecisionClient(base_url=""))
    
    t1 = await manager.process_turn(s["session_id"], "I have a package delivery")
    assert t1.turn_number == 1

    t2 = await manager.process_turn(s["session_id"], "Please leave it at door 4B")
    assert t2.turn_number == 2

    session = store.get(s["session_id"])
    assert len(session["turns"]) == 4
    assert [t["turn_number"] for t in session["turns"]] == [1, 1, 2, 2]
    assert [t["speaker"] for t in session["turns"]] == ["caller", "assistant", "caller", "assistant"]

@pytest.mark.asyncio
async def test_urgent_escalates():
    s = store.create()
    manager = ConversationManager(DecisionClient(base_url=""))
    result = await manager.process_turn(s["session_id"], "emergency, call immediately")
    
    assert result.session_status == "escalation_requested"
    assert result.decision.should_escalate is True
    assert result.decision.urgency == "high"
    assert store.get(s["session_id"])["status"] == "escalation_requested"

@pytest.mark.asyncio
async def test_ended_session_rejects_turn():
    s = store.create()
    store.set_status(s["session_id"], "ended")
    manager = ConversationManager(DecisionClient(base_url=""))
    
    with pytest.raises(ValueError, match="Session has ended"):
        await manager.process_turn(s["session_id"], "Hello?")

    # Verify no turns added
    assert len(store.get(s["session_id"])["turns"]) == 0

@pytest.mark.asyncio
async def test_empty_caller_text_rejected():
    s = store.create()
    manager = ConversationManager(DecisionClient(base_url=""))
    
    with pytest.raises(ValueError, match="Caller text cannot be empty"):
        await manager.process_turn(s["session_id"], "   ")

    assert len(store.get(s["session_id"])["turns"]) == 0

@pytest.mark.asyncio
async def test_decision_client_failure_does_not_corrupt_history():
    class FailingDecisionClient:
        async def decide(self, payload):
            raise DecisionClientError("Simulated external backend timeout")

    s = store.create()
    manager = ConversationManager(FailingDecisionClient())

    with pytest.raises(DecisionClientError):
        await manager.process_turn(s["session_id"], "Important message")

    # Critical check: No partial turns in history
    assert len(store.get(s["session_id"])["turns"]) == 0

@pytest.mark.asyncio
async def test_audio_generation_with_tts_mock(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "mock")
    s = store.create()
    manager = ConversationManager(DecisionClient(base_url=""))
    
    result = await manager.process_turn(s["session_id"], "parcel delivery", generate_audio=True)
    assert result.audio_generated is True
    assert result.audio_url is not None
    assert result.audio_url.startswith("/api/voice/audio/")

@pytest.mark.asyncio
async def test_audio_generation_with_tts_disabled(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "disabled")
    s = store.create()
    manager = ConversationManager(DecisionClient(base_url=""))
    
    result = await manager.process_turn(s["session_id"], "parcel delivery", generate_audio=True)
    assert result.audio_generated is False
    assert result.audio_url is None
