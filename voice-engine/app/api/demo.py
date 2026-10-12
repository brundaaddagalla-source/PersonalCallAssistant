from fastapi import APIRouter, HTTPException
from app.models.schemas import DemoConversationRequest, DemoConversationResponse
from app.state.session_store import store, SessionNotFound
from app.services.conversation_manager import manager
from app.services.decision_client import DecisionClientError

router = APIRouter(prefix="/api/demo", tags=["demo"])

@router.post("/conversation", response_model=DemoConversationResponse)
async def demo_conversation(payload: DemoConversationRequest):
    """
    Demonstrates a complete conversational turn end-to-end without requiring live telephony.
    
    - If `session_id` is supplied, continues that existing session.
    - If `session_id` is omitted, automatically creates a new demo session.
    - Runs text through Conversation Manager and Member 3 Decision Engine (mock or HTTP).
    - Optionally synthesizes speech if `generate_audio` is True and TTS is enabled.
    """
    clean_text = payload.caller_text.strip()
    if not clean_text:
        raise HTTPException(400, "Caller text cannot be empty.")

    # 1. Resolve or create session
    session_id = payload.session_id
    if session_id:
        try:
            session = store.get(session_id)
            if session.get("status") == "ended":
                raise HTTPException(409, "Session has ended. No further turns are accepted.")
        except SessionNotFound:
            raise HTTPException(404, f"Session '{session_id}' not found.")
    else:
        new_session = store.create(
            caller_number="demo-simulated",
            caller_name="Demo Caller",
            language=payload.language or "English"
        )
        session_id = new_session["session_id"]

    # 2. Process conversational turn
    try:
        turn_result = await manager.process_turn(
            session_id=session_id,
            caller_text=clean_text,
            language=payload.language,
            generate_audio=payload.generate_audio
        )
    except ValueError as exc:
        msg = str(exc)
        if "ended" in msg.lower():
            raise HTTPException(409, msg)
        raise HTTPException(400, msg)
    except DecisionClientError as exc:
        raise HTTPException(502, f"Decision engine unavailable: {str(exc)}")

    # 3. Build response
    decision = turn_result.decision
    return DemoConversationResponse(
        session_id=session_id,
        turn_number=turn_result.turn_number,
        language=payload.language,
        caller_text=turn_result.caller_text,
        assistant_text=turn_result.assistant_text,
        intent=decision.intent,
        urgency=decision.urgency,
        spam_risk=decision.spam_risk,
        action=decision.action,
        should_escalate=decision.should_escalate,
        should_end_call=decision.should_end_call,
        session_status=turn_result.session_status,
        audio_generated=turn_result.audio_generated,
        audio_url=turn_result.audio_url
    )

