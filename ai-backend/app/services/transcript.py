from app.schemas import Speaker, Turn


def caller_text(turns: list[Turn]) -> str:
    return " ".join(t.text.strip() for t in turns if t.speaker == Speaker.caller and t.text.strip())


def agent_turn_count(turns: list[Turn]) -> int:
    return sum(1 for t in turns if t.speaker == Speaker.agent)
