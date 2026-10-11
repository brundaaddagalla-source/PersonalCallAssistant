from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Speaker(str, Enum):
    caller = "caller"
    agent = "agent"


class Turn(BaseModel):
    speaker: Speaker
    text: str = Field(default="", max_length=2000)


class ContactGroup(str, Enum):
    none = "none"
    vip = "vip"
    family = "family"
    friend = "friend"
    work = "work"
    other = "other"


class Action(str, Enum):
    ask_clarification = "ask_clarification"
    handle = "handle"
    transfer = "transfer"
    take_message = "take_message"
    block = "block"


class Intent(str, Enum):
    emergency = "emergency"
    delivery = "delivery"
    appointment = "appointment"
    bank_finance = "bank_finance"
    sales_marketing = "sales_marketing"
    survey = "survey"
    tech_support = "tech_support"
    government_legal = "government_legal"
    prize_offer = "prize_offer"
    personal = "personal"
    work = "work"
    robocall = "robocall"
    unknown = "unknown"


class RiskLabel(str, Enum):
    unassessed = "unassessed"
    low_risk = "low_risk"
    unwanted = "unwanted"
    suspicious = "suspicious"
    fraud = "fraud"


# ---------- Request models ----------


class Caller(BaseModel):
    number: str | None = None
    is_known_contact: bool = False
    contact_name: str | None = None
    contact_group: ContactGroup = ContactGroup.none
    number_withheld: bool = False


_HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


class RuleMatch(BaseModel):
    """All specified criteria must match (AND). Empty fields are ignored."""

    contact_groups: list[ContactGroup] = []
    numbers: list[str] = []
    contact_names: list[str] = []
    intents: list[Intent] = []
    known_callers_only: bool = False
    unknown_callers_only: bool = False
    min_risk_score: int | None = Field(default=None, ge=0, le=100)
    time_start: str | None = None  # "HH:MM" 24h; may wrap past midnight
    time_end: str | None = None
    days: list[int] = []  # 0=Mon .. 6=Sun; empty = every day

    @model_validator(mode="after")
    def _validate(self):
        if (self.time_start is None) != (self.time_end is None):
            raise ValueError("time_start and time_end must be set together")
        for v in (self.time_start, self.time_end):
            if v is not None and not _HHMM.fullmatch(v):
                raise ValueError("time must look like HH:MM")
        if self.known_callers_only and self.unknown_callers_only:
            raise ValueError("known_callers_only and unknown_callers_only conflict")
        if any(d < 0 or d > 6 for d in self.days):
            raise ValueError("days must be 0 (Mon) .. 6 (Sun)")
        return self


class UserRule(BaseModel):
    id: str
    name: str
    priority: int = 100  # lower number = evaluated first
    enabled: bool = True
    match: RuleMatch = RuleMatch()
    action: Action
    instruction: str | None = Field(default=None, max_length=300)  # trusted text spoken to caller

    @model_validator(mode="after")
    def _no_clarify(self):
        if self.action == Action.ask_clarification:
            raise ValueError("a rule cannot use ask_clarification")
        return self


class UserPreferences(BaseModel):
    user_name: str | None = None
    rules: list[UserRule] = []
    do_not_disturb: bool = False
    max_clarification_turns: int = Field(default=3, ge=0, le=6)


class ClassifyRequest(BaseModel):
    caller: Caller
    transcript: list[Turn] = []


class DecideRequest(BaseModel):
    call_id: str
    caller: Caller
    transcript: list[Turn] = []
    preferences: UserPreferences = UserPreferences()
    received_at: datetime | None = None


# ---------- Response models ----------


class IntentInfo(BaseModel):
    intent: Intent
    confidence: float
    source: Literal["rules", "llm"] = "rules"


class RiskAssessment(BaseModel):
    label: RiskLabel
    score: int = Field(ge=0, le=100)
    confidence: float
    signals: list[str] = []
    uncertain: bool = True


class Identification(BaseModel):
    claimed_name: str | None = None
    claimed_org: str | None = None
    matched_contact: str | None = None
    source: Literal["contacts", "self_reported", "none"] = "none"
    verified: bool = False
    statement: str


class Notification(BaseModel):
    title: str
    body: str
    priority: Literal["low", "normal", "high"] = "normal"


class ClassifyResponse(BaseModel):
    intent: IntentInfo
    risk: RiskAssessment
    identification: Identification


class Decision(BaseModel):
    schema_version: str = "1.0"
    call_id: str
    action: Action
    speak: str
    end_call: bool
    intent: IntentInfo
    risk: RiskAssessment
    identification: Identification
    reasons: list[str]
    matched_rule_id: str | None = None
    caution: bool = False
    caller_summary: str
    caller_message: str = ""
    notification: Notification | None = None
