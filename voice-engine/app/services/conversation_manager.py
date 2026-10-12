from datetime import datetime, timezone
from app.models.schemas import DecisionResponse, TurnResponse
from app.state.session_store import store
from app.services.decision_client import DecisionClient
from app.services.tts_service import synthesize, TTSNotConfiguredError, TTSGenerationError

class ConversationManager:
    def __init__(self, decision_client=None):
        self.decision_client = decision_client or DecisionClient()

    async def process_turn(
        self,
        session_id: str,
        caller_text: str,
        language: str | None = None,
        generate_audio: bool = False
    ) -> TurnResponse:
        session = store.get(session_id)
        if session["status"] == "ended":
            raise ValueError("Session has ended. No further turns are accepted.")
        clean_text = caller_text.strip()
        if not clean_text:
            raise ValueError("Caller text cannot be empty.")

        turn_number = len(session["turns"]) // 2 + 1

        # Construct full transcript in Member 3 format: [{"speaker": "caller"|"agent", "text": "..."}]
        transcript = []
        for t in session.get("turns", []):
            spk = "agent" if t.get("speaker") in ("assistant", "agent") else "caller"
            transcript.append({"speaker": spk, "text": t.get("text", "")})
        transcript.append({"speaker": "caller", "text": clean_text})

        payload = {
            "call_id": session_id,
            "session_id": session_id,
            "caller": {
                "number": session.get("caller_number"),
                "is_known_contact": session.get("is_known_contact", False),
                "contact_name": session.get("caller_name"),
                "contact_group": session.get("contact_group", "none"),
                "number_withheld": session.get("number_withheld", False),
            },
            "transcript": transcript,
            "preferences": {
                "user_name": session.get("user_name") or "Alex",
                "rules": session.get("rules", []),
                "do_not_disturb": session.get("do_not_disturb", False),
                "max_clarification_turns": session.get("max_clarification_turns", 3),
            },
            "received_at": datetime.now(timezone.utc).isoformat(),
            "caller_text": clean_text,
            "caller_number": session.get("caller_number"),
            "caller_name": session.get("caller_name"),
            "turn_number": turn_number,
            "language": language or session.get("language", "English"),
        }

        # Step 1: Decision API call (prior to modifying history to prevent duplicate/corrupted turns on failure)
        decision: DecisionResponse = await self.decision_client.decide(payload)

        # Step 2: Speech synthesis if requested
        audio_url = None
        audio_generated = False
        if generate_audio:
            try:
                audio_path = await synthesize(decision.response_text)
                audio_url = f"/api/voice/audio/{audio_path.name}"
                audio_generated = True
            except (TTSNotConfiguredError, TTSGenerationError, ValueError):
                # TTS disabled or failed gracefully; continue with text-only
                audio_generated = False
                audio_url = None

        # Step 3: Record conversation turns with timestamps
        timestamp = datetime.now(timezone.utc).isoformat()
        store.append_turn(session_id, {
            "turn_number": turn_number,
            "speaker": "caller",
            "text": clean_text,
            "intent": decision.intent,
            "timestamp": timestamp
        })
        store.append_turn(session_id, {
            "turn_number": turn_number,
            "speaker": "assistant",
            "text": decision.response_text,
            "intent": decision.intent,
            "action": decision.action,
            "timestamp": timestamp
        })

        # Step 4: Update session status
        status = "active"
        if decision.should_escalate or decision.action in ("escalate", "transfer"):
            status = "escalation_requested"
        elif decision.should_end_call or decision.action in ("end_call", "block"):
            status = "ended"
        store.set_status(session_id, status)

        return TurnResponse(
            session_id=session_id,
            turn_number=turn_number,
            caller_text=clean_text,
            assistant_text=decision.response_text,
            decision=decision,
            session_status=status,
            audio_generated=audio_generated,
            audio_url=audio_url
        )

manager = ConversationManager()

