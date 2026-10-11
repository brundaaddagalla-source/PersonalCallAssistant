from app.schemas import Intent
from app.services.intent import classify_intent


def test_delivery():
    r = classify_intent("Hi, I'm the delivery driver with your package, I'm outside your building")
    assert r.intent == Intent.delivery


def test_emergency():
    r = classify_intent("There's been an accident, your brother is in the hospital")
    assert r.intent == Intent.emergency


def test_sales():
    r = classify_intent("We have a special offer with a big discount for a limited time, are you interested?")
    assert r.intent == Intent.sales_marketing


def test_empty_is_unknown():
    assert classify_intent("   ").intent == Intent.unknown


def test_name_and_org_extraction():
    r = classify_intent("Hi, this is Rahul from SBI bank regarding your account")
    assert r.claimed_name == "Rahul"
    assert r.claimed_org == "SBI bank"


def test_its_me_is_not_a_name():
    assert classify_intent("it's me, are you free for dinner").claimed_name is None
