import json
from pathlib import Path
from app.models.schemas import SessionCreate
from app.services.decision_client import DecisionClient


def test_android_examples_survive_voice_to_decision_mapping():
    examples = json.loads((Path(__file__).resolve().parents[2] / "docs/member2-caller-examples.json").read_text())
    for example in examples:
        session = SessionCreate.model_validate(example["voice_session"])
        body = DecisionClient()._build_request_body({**session.model_dump(), "session_id": "provider-test-call"})
        assert body["caller"] == example["caller"]
