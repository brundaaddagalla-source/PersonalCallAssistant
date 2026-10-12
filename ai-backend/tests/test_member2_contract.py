import json
from pathlib import Path
from app.schemas import Caller, DecideRequest


def test_android_examples_match_decision_contract():
    examples = json.loads((Path(__file__).resolve().parents[2] / "docs/member2-caller-examples.json").read_text())
    for example in examples:
        caller = Caller.model_validate(example["caller"])
        assert caller.model_dump(mode="json") == example["caller"]
        request = DecideRequest(call_id="provider-test-call", caller=caller)
        assert request.caller.is_known_contact is example["caller"]["is_known_contact"]
