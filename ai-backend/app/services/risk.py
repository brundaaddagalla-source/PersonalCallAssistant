from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import Caller, Intent, RiskAssessment, RiskLabel


@dataclass(frozen=True)
class Signal:
    key: str
    pattern: re.Pattern
    weight: int
    reason: str


def _s(key: str, pattern: str, weight: int, reason: str) -> Signal:
    return Signal(key, re.compile(pattern, re.I), weight, reason)


FRAUD_SIGNALS = [
    _s("credentials",
       r"\b(?:otp|one[- ]time (?:password|code|pin)|verification code|cvv|password|card number|aadhaar|social security|ssn)\b|\bpin\b(?!\s*code)",
       40, "Asks for a password, OTP, PIN or card/ID number"),
    _s("payment",
       r"\b(?:gift cards?|bitcoin|crypto(?:currency)?|wire transfer|western union|send (?:me )?money|transfer (?:the |some )?(?:money|amount|funds)|pay (?:a |the )?(?:fine|fee|penalty)|processing fee|google pay|phonepe|paytm)\b",
       40, "Asks for money or an unusual payment method"),
    _s("threat",
       r"\b(?:arrest(?:ed)?|warrant|legal action|lawsuit|case (?:has been |is |was )?filed|suspended|blocked|frozen|deactivated|jail|police|penalty)\b",
       30, "Uses threats or warnings about arrest, legal action or account blocking"),
    _s("remote_access",
       r"\b(?:anydesk|teamviewer|quicksupport|remote access|screen shar(?:e|ing)|(?:install|download) (?:an |the )?(?:app|application|software))\b",
       40, "Asks to install software or gain remote access"),
    _s("prize",
       r"\b(?:you(?:'ve| have)? won|lottery|lucky draw|claim your (?:prize|reward|gift)|congratulations)\b",
       30, "Claims a prize or lottery win"),
    _s("secrecy",
       r"\b(?:don'?t tell anyone|do not tell anyone|keep (?:this|it) (?:a secret|confidential|between us)|stay on the line|do not hang up)\b",
       30, "Pressures the user to keep the call secret or stay on the line"),
    _s("urgency",
       r"\b(?:immediately|right now|within (?:the next )?\d+ (?:minutes|hours)|last warning|final notice|act now|urgent(?:ly)?)\b",
       15, "Creates artificial urgency"),
]

_SENSITIVE = {Intent.bank_finance, Intent.government_legal, Intent.tech_support}


def assess_risk(text: str, intent: Intent, caller: Caller) -> RiskAssessment:
    has_speech = bool(text.strip())
    known = caller.is_known_contact

    if not has_speech:
        return RiskAssessment(
            label=RiskLabel.low_risk if known else RiskLabel.unassessed,
            score=0 if known else 10,
            confidence=0.1,
            signals=["No speech to assess yet"],
            uncertain=True,
        )

    signals: list[str] = []
    fraud = 0
    unwanted = 0
    context = 0
    keys: set[str] = set()

    for sig in FRAUD_SIGNALS:
        if sig.pattern.search(text):
            fraud += sig.weight
            keys.add(sig.key)
            signals.append(sig.reason)

    if intent == Intent.emergency and "payment" in keys and not known:
        fraud += 25
        signals.append("Emergency story combined with a money request (common impersonation scam)")
    if intent in _SENSITIVE and not known:
        fraud += 15
        signals.append("Unverified caller claims to be a bank, authority or tech support")
    if intent == Intent.robocall:
        unwanted += 20
        signals.append("Looks like a recorded or automated call")
    if intent == Intent.sales_marketing:
        unwanted += 25
        signals.append("Sales or marketing language")
    if intent == Intent.survey:
        unwanted += 10
        signals.append("Survey request")
    if caller.number_withheld:
        context += 10
        signals.append("Number is withheld")
    if not known:
        context += 5

    total = fraud + unwanted + context
    if known:
        total = max(0, total - 25)
        signals.append("Number matches a saved contact (lowers risk, caller ID can still be spoofed)")
    total = min(100, total)

    if fraud >= 55 or total >= 65:
        label = RiskLabel.fraud
    elif total >= 35 or fraud >= 25:
        label = RiskLabel.suspicious
    elif unwanted >= 20:
        label = RiskLabel.unwanted
    else:
        label = RiskLabel.low_risk

    words = len(text.split())
    n_risk_signals = sum(1 for s in signals if "saved contact" not in s)
    confidence = min(0.95, 0.25 + 0.5 * min(words, 40) / 40 + 0.05 * min(n_risk_signals, 4))
    uncertain = confidence < 0.5 or label == RiskLabel.suspicious

    return RiskAssessment(
        label=label,
        score=total,
        confidence=round(confidence, 2),
        signals=signals,
        uncertain=uncertain,
    )
