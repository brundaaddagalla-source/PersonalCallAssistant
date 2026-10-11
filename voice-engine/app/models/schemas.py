from typing import Literal
from pydantic import BaseModel, Field

Action = Literal["ask_followup", "take_message", "escalate", "end_call", "continue"]
Action = Literal["ask_clarification", "handle", "transfer", "take_message", "block", "ask_followup", "escalate", "end_call", "continue"]
SessionStatus = Literal["active", "escalation_requested", "ended"]

class SessionCreate(BaseModel):
    caller_number: str | None = None
    caller_name: str | None = None
    language: str = "English"
    is_known_contact: bool = False
    contact_group: str = "none"
    number_withheld: bool = False
    user_name: str | None = None
    do_not_disturb: bool = False
    max_clarification_turns: int = 3
    rules: list[dict] = Field(default_factory=list)

class TurnRequest(BaseModel):
    caller_text: str = Field(min_length=1, max_length=12000)
    language: str | None = None
    generate_audio: bool = False

class DecisionResponse(BaseModel):
    intent: str = "general"
    urgency: str = "normal"
    spam_risk: str = "low"
    action: Action = "continue"
    response_text: str = "Thank you. Could you tell me a little more?"
    speak: str | None = None
    end_call: bool = False
    should_escalate: bool = False
    should_end_call: bool = False
    confidence: float | None = None
    risk: dict | None = None
    identification: dict | None = None
    reasons: list[str] = Field(default_factory=list)
    matched_rule_id: str | None = None
    caution: bool = False
    caller_summary: str | None = None
    caller_message: str | None = None
    notification: dict | None = None


class TurnResponse(BaseModel):
    session_id: str
    turn_number: int
    caller_text: str
    assistant_text: str
    decision: DecisionResponse
    session_status: SessionStatus
    audio_generated: bool = False
    audio_url: str | None = None

class DemoConversationRequest(BaseModel):
    session_id: str | None = None
    caller_text: str = Field(min_length=1, max_length=12000)
    language: str = "English"
    generate_audio: bool = False

class DemoConversationResponse(BaseModel):
    session_id: str
    turn_number: int
    language: str
    caller_text: str
    assistant_text: str
    intent: str
    urgency: str
    spam_risk: str
    action: Action
    should_escalate: bool
    should_end_call: bool
    session_status: SessionStatus
    audio_generated: bool = False
    audio_url: str | None = None

class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    language_probability: float | None = None
    duration_seconds: float | None = None

