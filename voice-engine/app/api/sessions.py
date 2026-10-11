from fastapi import APIRouter, HTTPException
from app.models.schemas import SessionCreate, TurnRequest
from app.state.session_store import store, SessionNotFound
from app.services.conversation_manager import manager
from app.services.decision_client import DecisionClientError

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("")
def create_session(payload: SessionCreate):
    s = store.create(payload.caller_number, payload.caller_name, payload.language)
    return {
        "session_id": s["session_id"],
        "status": s["status"],
        "caller_number": s["caller_number"],
        "caller_name": s["caller_name"],
        "language": s["language"],
        "created_at": s["created_at"].isoformat() if hasattr(s["created_at"], "isoformat") else str(s["created_at"])
    }

@router.get("/{session_id}")
def get_session(session_id: str):
    try:
        return store.get(session_id)
    except SessionNotFound:
        raise HTTPException(404, "Session not found")

@router.post("/{session_id}/turn")
async def process_turn(session_id: str, payload: TurnRequest):
    try:
        return await manager.process_turn(
            session_id=session_id,
            caller_text=payload.caller_text,
            language=payload.language,
            generate_audio=payload.generate_audio
        )
    except SessionNotFound:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        msg = str(exc)
        if "ended" in msg.lower():
            raise HTTPException(409, msg)
        raise HTTPException(400, msg)
    except DecisionClientError as exc:
        raise HTTPException(502, f"Decision engine unavailable: {str(exc)}")

@router.post("/{session_id}/end")
def end_session(session_id: str):
    try:
        s = store.set_status(session_id, "ended")
        return {"session_id": session_id, "status": s["status"], "turns": len(s["turns"])}
    except SessionNotFound:
        raise HTTPException(404, "Session not found")

