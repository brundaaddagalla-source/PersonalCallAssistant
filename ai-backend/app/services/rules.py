from __future__ import annotations

import re
from datetime import datetime, time

from app.schemas import Caller, ContactGroup, Intent, RuleMatch, UserRule


def _digits(n: str | None) -> str:
    # Last 9 digits: local ("050 123 4567") and international ("+971 50 123 4567")
    # forms of the same number differ only in the prefix.
    d = re.sub(r"\D", "", n or "")
    return d[-9:] if len(d) >= 7 else ""


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_time_window(now: datetime, start: str, end: str) -> bool:
    t, s, e = now.time(), _hhmm(start), _hhmm(end)
    if s <= e:
        return s <= t < e
    return t >= s or t < e  # window wraps past midnight


def rule_matches(
    match: RuleMatch, caller: Caller, intent: Intent, risk_score: int, now: datetime
) -> bool:
    known = caller.is_known_contact
    if match.known_callers_only and not known:
        return False
    if match.unknown_callers_only and known:
        return False
    if match.contact_groups and caller.contact_group not in match.contact_groups:
        return False
    if match.numbers:
        cn = _digits(caller.number)
        if not cn or cn not in {_digits(n) for n in match.numbers}:
            return False
    if match.contact_names:
        names = {n.strip().lower() for n in match.contact_names}
        if (caller.contact_name or "").strip().lower() not in names:
            return False
    if match.intents and intent not in match.intents:
        return False
    if match.min_risk_score is not None and risk_score < match.min_risk_score:
        return False
    if match.days and now.weekday() not in match.days:
        return False
    if match.time_start and match.time_end and not in_time_window(now, match.time_start, match.time_end):
        return False
    return True


def find_matching_rule(
    rules: list[UserRule], caller: Caller, intent: Intent, risk_score: int, now: datetime
) -> UserRule | None:
    for rule in sorted((r for r in rules if r.enabled), key=lambda r: r.priority):
        if rule_matches(rule.match, caller, intent, risk_score, now):
            return rule
    return None
