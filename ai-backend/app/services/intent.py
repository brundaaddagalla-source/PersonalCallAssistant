from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas import Intent

_RAW: dict[Intent, list[tuple[str, float]]] = {
    Intent.emergency: [
        (r"\b(?:emergency|accident|hospital|ambulance|injured|collapsed|heart attack|critical condition|in trouble|urgent|urgently|immediate(?:ly)?|asap|life threatening)\b", 2.0),
    ],
    Intent.delivery: [
        (r"\b(?:delivery|deliver(?:ing)?|courier|driver|drop(?:ping)? off)\b", 1.0),
        (r"\byour (?:order|package|parcel)\b", 1.0),
        (r"\b(?:outside|at the gate|which flat|your address)\b", 1.0),
    ],
    Intent.appointment: [
        (r"\b(?:appointment|reschedul\w*|reservation|booking|clinic|dentist|your slot)\b", 1.5),
    ],
    Intent.bank_finance: [
        (r"\b(?:bank|credit card|debit card|loan|emi|kyc|transaction|your account)\b", 1.0),
    ],
    Intent.sales_marketing: [
        (r"\b(?:offer|discount|promotion|limited time|free trial|special deal|insurance plan|subscription|upgrade|investment|are you interested|interested in)\b", 1.0),
    ],
    Intent.survey: [
        (r"\b(?:survey|feedback|questionnaire|rate your|few questions)\b", 1.5),
    ],
    Intent.tech_support: [
        (r"\b(?:tech(?:nical)? support|virus|your computer|microsoft|windows|remote access|anydesk|teamviewer|hacked)\b", 1.5),
    ],
    Intent.government_legal: [
        (r"\b(?:police|court|arrest|warrant|income tax|customs|immigration|legal action|case (?:has been |is |was )?filed|narcotics)\b", 1.5),
    ],
    Intent.prize_offer: [
        (r"\b(?:you(?:'ve| have)? won|lottery|lucky draw|prize|congratulations|claim your)\b", 1.5),
    ],
    Intent.personal: [
        (r"\b(?:it'?s me|how are you|are you free|where are you|dinner|come home|pick (?:me|you) up|miss you|call me back|call back|callback|leave a message|take a message|can i (?:speak|talk) (?:to|with)|is [a-z]+ available)\b", 1.0),
    ],
    Intent.work: [
        (r"\b(?:meeting|project|deadline|client|office|report|colleague|manager|team|boss)\b", 1.0),
    ],
    Intent.robocall: [
        (r"\b(?:press (?:1|one|9|nine)|this is a recorded|automated (?:message|call)|after the beep)\b", 2.0),
    ],
}

_COMPILED = {i: [(re.compile(p, re.I), w) for p, w in pats] for i, pats in _RAW.items()}

_NAME_RX = re.compile(
    r"\b(?:this is|my name is|i am|i'm|it's|speaking is)\s+([a-z][a-z'\-]+(?:\s+[a-z][a-z'\-]+)?)",
    re.I,
)
_NAME_STOP = {
    "me", "calling", "just", "from", "here", "not", "sorry", "looking", "trying", "a", "an", "the",
    "with", "at", "in", "on", "regarding", "about", "to", "your", "you", "so", "really", "very",
    "glad", "afraid", "what", "who", "speaking", "sure", "ok", "okay", "fine", "good", "well", "now",
    "still", "only", "also", "again", "back", "outside", "the", "calling", "urgent", "important",
    "delivering", "ringing", "following", "going", "coming", "waiting",
}
_ORG_RX = re.compile(
    r"\bfrom\s+(?:the\s+)?([A-Za-z0-9&'.\- ]{2,40}?)"
    r"(?=\s+(?:regarding|about|to|and|for|calling|we|i|your|in|at|with|because|on)\b|[,!?;]|\.\s|\.$|$)",
    re.I,
)


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    matches: list[str] = field(default_factory=list)
    claimed_name: str | None = None
    claimed_org: str | None = None
    source: str = "rules"


def _extract_name(text: str) -> str | None:
    for m in _NAME_RX.finditer(text):
        words: list[str] = []
        for tok in m.group(1).split():
            if tok.lower() in _NAME_STOP:
                break
            words.append(tok)
        if words:
            name = " ".join(words)
            return name.title() if name.islower() else name
    return None


def _extract_org(text: str) -> str | None:
    m = _ORG_RX.search(text)
    if not m:
        return None
    org = m.group(1).strip(" .-")
    return org or None


def classify_intent(text: str) -> IntentResult:
    if not text.strip():
        return IntentResult(Intent.unknown, 0.0)

    scores: dict[Intent, float] = {}
    hits: dict[Intent, list[str]] = {}
    for intent, pats in _COMPILED.items():
        for rx, weight in pats:
            found = [m.group(0) for m in rx.finditer(text)][:2]  # cap repeats
            if found:
                scores[intent] = scores.get(intent, 0.0) + weight * len(found)
                hits.setdefault(intent, []).extend(found)

    name, org = _extract_name(text), _extract_org(text)
    if not scores:
        return IntentResult(Intent.unknown, 0.2, [], name, org)

    best = max(scores, key=lambda i: scores[i])  # ties -> earliest declared (emergency first)
    score = scores[best]
    if score < 1.0:
        return IntentResult(Intent.unknown, 0.2, [], name, org)
    confidence = min(0.95, score / (score + 1.5))
    return IntentResult(best, round(confidence, 2), hits[best], name, org)
