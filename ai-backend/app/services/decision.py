from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime

from app.schemas import (
    Action,
    Caller,
    ClassifyResponse,
    ContactGroup,
    Decision,
    DecideRequest,
    Identification,
    Intent,
    IntentInfo,
    Notification,
    RiskAssessment,
    RiskLabel,
    Turn,
    UserPreferences,
    UserRule,
)
from app.services.intent import IntentResult, classify_intent
from app.services.llm_classifier import llm_classify
from app.services.responses import render_speech
from app.services.risk import assess_risk
from app.services.rules import find_matching_rule
from app.services.transcript import agent_turn_count, caller_text

_UNWANTED_INTENTS = {Intent.sales_marketing, Intent.robocall, Intent.survey, Intent.prize_offer}
_SENSITIVE_INTENTS = {Intent.bank_finance, Intent.government_legal, Intent.tech_support}
_DELIVERY_DETAILS_RX = re.compile(
    r"\b(?:trk|tracking|tracking reference|reference number|waybill|order number|flat|gate|door|outside|leave it|drop off|security desk|reception|address|leave at|left at)\b|\b[A-Z]{2,}\d+\b|\b\d{5,}\b",
    re.I,
)


def _has_delivery_details(text: str) -> bool:
    return bool(_DELIVERY_DETAILS_RX.search(text))



@dataclass
class Analysis:
    text: str
    intent: IntentResult
    risk: RiskAssessment
    identification: Identification


@dataclass
class Outcome:
    action: Action
    reasons: list[str]
    caution: bool = False
    rule: UserRule | None = None
    by_rule_block: bool = False


# ---------------------------------------------------------------- analysis


def build_identification(caller: Caller, ir: IntentResult) -> Identification:
    if caller.is_known_contact and caller.contact_name:
        return Identification(
            claimed_name=ir.claimed_name,
            claimed_org=ir.claimed_org,
            matched_contact=caller.contact_name,
            source="contacts",
            verified=False,
            statement=(
                f"Number matches saved contact '{caller.contact_name}'. "
                "Caller ID can be spoofed, so this is not independently verified."
            ),
        )
    if ir.claimed_name or ir.claimed_org:
        who = ir.claimed_name or "someone"
        org = f" from {ir.claimed_org}" if ir.claimed_org else ""
        return Identification(
            claimed_name=ir.claimed_name,
            claimed_org=ir.claimed_org,
            source="self_reported",
            statement=f"Caller says they are {who}{org}. This is self-reported and unverified.",
        )
    return Identification(source="none", statement="Caller has not identified themselves and could not be identified.")


def _merge_llm(ir: IntentResult, risk: RiskAssessment, text: str) -> tuple[IntentResult, RiskAssessment]:
    """The LLM may refine intent and may only RAISE risk. It never picks the action."""
    llm = llm_classify(text)
    if not llm:
        return ir, risk
    if ir.intent == Intent.unknown or llm.confidence > ir.confidence + 0.15:
        ir = replace(ir, intent=llm.intent, confidence=round(llm.confidence, 2), source="llm")
    if llm.suspicious and risk.label in (RiskLabel.low_risk, RiskLabel.unassessed):
        risk = risk.model_copy(
            update={
                "label": RiskLabel.suspicious,
                "score": max(risk.score, 40),
                "signals": [*risk.signals, "Language model flagged the call as suspicious"],
                "uncertain": True,
            }
        )
    return ir, risk


def analyze(caller: Caller, transcript: list[Turn]) -> Analysis:
    text = caller_text(transcript)
    ir = classify_intent(text)
    risk = assess_risk(text, ir.intent, caller)
    ir, risk = _merge_llm(ir, risk, text)
    return Analysis(text, ir, risk, build_identification(caller, ir))


def classify(caller: Caller, transcript: list[Turn]) -> ClassifyResponse:
    a = analyze(caller, transcript)
    return ClassifyResponse(intent=_intent_info(a.intent), risk=a.risk, identification=a.identification)


def _intent_info(ir: IntentResult) -> IntentInfo:
    return IntentInfo(intent=ir.intent, confidence=ir.confidence, source=ir.source)  # type: ignore[arg-type]


# ---------------------------------------------------------------- policy


def _policy(
    *,
    caller: Caller,
    prefs: UserPreferences,
    intent: Intent,
    risk: RiskAssessment,
    rule: UserRule | None,
    has_speech: bool,
    agent_turns: int,
    raw_text: str = "",
) -> Outcome:
    known = caller.is_known_contact
    vip = known and caller.contact_group in (ContactGroup.vip, ContactGroup.family)
    can_ask = agent_turns < prefs.max_clarification_turns
    dnd = prefs.do_not_disturb
    fraud = risk.label == RiskLabel.fraud
    suspicious = risk.label == RiskLabel.suspicious

    # 1. A user's explicit block always wins.
    if rule and rule.action == Action.block:
        return Outcome(Action.block, [f"Your rule '{rule.name}' says to block this caller."], False, rule, True)

    # 2. Safety gates beat every other rule.
    if fraud and not known:
        reasons = ["Strong scam indicators from an unverified caller: " + "; ".join(risk.signals[:3]) + "."]
        if rule:
            reasons.append(f"Safety check overrode your rule '{rule.name}'.")
        return Outcome(Action.block, reasons)
    if fraud and known:
        action = rule.action if rule else Action.transfer
        return Outcome(
            action,
            [
                f"Caller matches contact '{caller.contact_name}' but used scam-like language "
                "(number may be spoofed or the contact compromised). Verify before acting on any request."
            ],
            True,
            rule,
        )

    # 3. User rules.
    if rule:
        return Outcome(rule.action, [f"Matched your rule '{rule.name}'."], suspicious, rule)

    # 4. Defaults.
    if vip:
        return Outcome(Action.transfer, [f"Saved {caller.contact_group.value} contact: always ring through."])

    if not has_speech:
        if can_ask:
            return Outcome(Action.ask_clarification, ["Caller hasn't said anything yet; asking who they are and why they called."])
        return Outcome(Action.take_message, ["Caller stayed silent or unclear after several prompts."])

    if intent == Intent.emergency:
        reasons = ["Caller describes an emergency; the cost of missing a real one is higher than a false alarm."]
        if suspicious:
            reasons.append("Some risk signals present, so the call is flagged for caution.")
        return Outcome(Action.transfer, reasons, suspicious)

    if known:
        if suspicious:
            return Outcome(Action.take_message, ["Known contact but with suspicious wording; taking a message instead of ringing through."], True)
        if intent in (Intent.personal, Intent.work) and not dnd:
            return Outcome(Action.transfer, [f"Known contact calling about a {intent.value} matter."])
        why = "Do Not Disturb is on." if dnd else "Nothing urgent detected."
        return Outcome(Action.take_message, [f"Known contact. {why} Taking a message."])

    if risk.label == RiskLabel.unwanted or intent in _UNWANTED_INTENTS:
        return Outcome(Action.block, ["Looks like sales, survey or automated calling; politely declined."])

    if suspicious:
        if can_ask and risk.confidence < 0.7:
            return Outcome(Action.ask_clarification, ["Some warning signs but not enough evidence; asking for verification details."], True)
        return Outcome(Action.take_message, ["Suspicious wording from an unverified caller; not ringing through."], True)

    if intent in (Intent.delivery, Intent.appointment):
        if intent == Intent.delivery and can_ask and not _has_delivery_details(raw_text):
            return Outcome(Action.ask_clarification, ["Delivery inquiry without tracking reference or drop-off details; asking for tracking reference."])
        return Outcome(Action.handle, [f"Routine {intent.value} call with no risk signals; agent can handle it."])

    if intent in _SENSITIVE_INTENTS:
        return Outcome(
            Action.take_message,
            ["Unverified caller claims to be a bank, authority or support agent; no information shared, message taken."],
            True,
        )

    if intent == Intent.unknown and can_ask:
        return Outcome(Action.ask_clarification, ["Purpose of the call is still unclear."])

    return Outcome(Action.take_message, ["Unknown caller with no urgent need; taking a message."])


# ---------------------------------------------------------------- output helpers


def _who(caller: Caller, ident: Identification) -> str:
    if ident.matched_contact:
        return ident.matched_contact
    if ident.claimed_name:
        return f"{ident.claimed_name} ({ident.claimed_org})" if ident.claimed_org else ident.claimed_name
    if ident.claimed_org:
        return f"Caller from {ident.claimed_org}"
    if caller.number and not caller.number_withheld:
        return f"Unknown caller {caller.number}"
    return "Unknown caller"


def _notification(action: Action, who: str, summary: str, caution: bool, emergency: bool, risk: RiskAssessment) -> Notification | None:
    extra = " Caution: unverified, do not share personal details." if caution else ""
    if action == Action.transfer:
        return Notification(title=f"{who} needs you", body=summary + extra, priority="high" if emergency else "normal")
    if action == Action.take_message:
        return Notification(title=f"Message from {who}", body=summary + extra, priority="normal")
    if action == Action.handle:
        return Notification(title=f"Handled call from {who}", body=summary, priority="low")
    if action == Action.block:
        return Notification(title=f"Blocked: {risk.label.value.replace('_', ' ')} call", body=f"{who}. {summary}", priority="low")
    return None


# ---------------------------------------------------------------- main entry


def decide(req: DecideRequest) -> Decision:
    caller, prefs = req.caller, req.preferences
    a = analyze(caller, req.transcript)
    has_speech = bool(a.text.strip())
    agent_turns = agent_turn_count(req.transcript)
    now = req.received_at or datetime.now().astimezone()

    rule = find_matching_rule(prefs.rules, caller, a.intent.intent, a.risk.score, now)
    out = _policy(
        caller=caller,
        prefs=prefs,
        intent=a.intent.intent,
        risk=a.risk,
        rule=rule,
        has_speech=has_speech,
        agent_turns=agent_turns,
        raw_text=a.text,
    )

    owner = prefs.user_name or "the person you're calling"
    speak, end_call = render_speech(
        out.action,
        owner=owner,
        agent_turns=agent_turns,
        ident=a.identification,
        risk=a.risk,
        instruction=out.rule.instruction if out.rule else None,
        has_speech=has_speech,
        by_rule_block=out.by_rule_block,
        intent=a.intent.intent,
    )


    who = _who(caller, a.identification)
    topic = a.intent.intent.value.replace("_", " ")
    summary = f"{who}: {topic} call, risk {a.risk.label.value.replace('_', ' ')} ({a.risk.score}/100)."
    message = a.text[:500]
    emergency = a.intent.intent == Intent.emergency

    return Decision(
        call_id=req.call_id,
        action=out.action,
        speak=speak,
        end_call=end_call,
        intent=_intent_info(a.intent),
        risk=a.risk,
        identification=a.identification,
        reasons=out.reasons,
        matched_rule_id=out.rule.id if out.rule and not _overridden(out) else None,
        caution=out.caution,
        caller_summary=summary,
        caller_message=message,
        notification=_notification(out.action, who, summary, out.caution, emergency, a.risk),
    )


def _overridden(out: Outcome) -> bool:
    return any("overrode your rule" in r for r in out.reasons)
