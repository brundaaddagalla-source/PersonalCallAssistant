from datetime import datetime, timedelta, timezone

from app.schemas import Action, Caller, ContactGroup, Intent, RuleMatch, UserRule
from app.services.rules import find_matching_rule, in_time_window

TZ = timezone(timedelta(hours=4))


def _dt(h, m=0, day=12):  # 2026-10-12 is a Monday
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


def test_overnight_window():
    assert in_time_window(_dt(23, 30), "22:00", "07:00")
    assert in_time_window(_dt(3), "22:00", "07:00")
    assert not in_time_window(_dt(12), "22:00", "07:00")


def test_number_match_ignores_formatting():
    rule = UserRule(id="r1", name="Mom", action=Action.transfer, match=RuleMatch(numbers=["+971 50 123 4567"]))
    c = Caller(number="0501234567")
    assert find_matching_rule([rule], c, Intent.unknown, 0, _dt(10)) is not None


def test_priority_order_and_disabled():
    a = UserRule(id="a", name="A", priority=50, action=Action.block)
    b = UserRule(id="b", name="B", priority=10, action=Action.transfer)
    off = UserRule(id="c", name="C", priority=1, action=Action.handle, enabled=False)
    got = find_matching_rule([a, b, off], Caller(), Intent.unknown, 0, _dt(10))
    assert got.id == "b"


def test_group_and_days():
    rule = UserRule(
        id="w", name="Work hours", action=Action.transfer,
        match=RuleMatch(contact_groups=[ContactGroup.work], time_start="09:00", time_end="18:00", days=[0, 1, 2, 3, 4]),
    )
    c = Caller(is_known_contact=True, contact_group=ContactGroup.work)
    assert find_matching_rule([rule], c, Intent.work, 0, _dt(10)) is not None
    assert find_matching_rule([rule], c, Intent.work, 0, _dt(20)) is None
    assert find_matching_rule([rule], c, Intent.work, 0, _dt(10, day=18)) is None  # Sunday
