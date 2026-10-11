from app.schemas import Caller, ContactGroup, Intent, RiskLabel
from app.services.intent import classify_intent
from app.services.risk import assess_risk

UNKNOWN = Caller(number="+971500000000")


def _risk(text, caller=UNKNOWN):
    return assess_risk(text, classify_intent(text).intent, caller)


def test_bank_scam_is_fraud():
    r = _risk("This is SBI bank, your account will be blocked, share your OTP immediately")
    assert r.label == RiskLabel.fraud
    assert r.score >= 65 or r.score >= 55
    assert r.signals


def test_sales_is_unwanted():
    r = _risk("We have a special offer with a discount for a limited time, are you interested in an investment plan?")
    assert r.label == RiskLabel.unwanted


def test_polite_delivery_is_low_risk():
    r = _risk("Hi, I'm the delivery driver with your package, I'm outside, which flat is it?")
    assert r.label == RiskLabel.low_risk


def test_no_speech_unknown_is_unassessed():
    r = assess_risk("", Intent.unknown, UNKNOWN)
    assert r.label == RiskLabel.unassessed
    assert r.uncertain


def test_known_contact_lowers_score():
    text = "Can you send money to my account"
    known = Caller(number="+1", is_known_contact=True, contact_name="Sam", contact_group=ContactGroup.friend)
    assert _risk(text, known).score < _risk(text).score


def test_grandparent_scam_pattern():
    r = _risk("I had an accident and I'm in the hospital, please buy gift cards and don't tell anyone")
    assert r.label == RiskLabel.fraud
