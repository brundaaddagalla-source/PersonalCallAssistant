from __future__ import annotations

from app.schemas import Action, Identification, RiskAssessment, RiskLabel


def render_speech(
    action: Action,
    *,
    owner: str,
    agent_turns: int,
    ident: Identification,
    risk: RiskAssessment,
    instruction: str | None,
    has_speech: bool,
    by_rule_block: bool = False,
) -> tuple[str, bool]:
    """Return (text for TTS, end_call). The agent always discloses it is an AI."""
    name = ident.claimed_name or ident.matched_contact
    thanks = f"Thanks, {name}." if name else "Thank you."

    if action == Action.ask_clarification:
        if agent_turns == 0:
            return (
                f"Hello, this is the AI assistant for {owner}. They can't take your call right now. "
                "May I ask who's calling and what it's regarding?",
                False,
            )
        if risk.label == RiskLabel.suspicious:
            return (
                "I'd like to help, but I couldn't confirm the details. Could you give me your full name, "
                f"your organisation, and a number where {owner} can reach you?",
                False,
            )
        if not has_speech:
            return ("Sorry, I didn't catch that. Could you tell me who is calling and what it's regarding?", False)
        if not ident.claimed_name and not ident.matched_contact:
            return ("Sorry, I didn't get your name. Who am I speaking with, and what is this regarding?", False)
        return (f"{thanks} Could you tell me briefly what this is regarding?", False)

    if action == Action.transfer:
        if not has_speech:
            return ("Hello, one moment while I connect you.", False)
        return (f"{thanks} Let me check whether {owner} is available. Please hold.", False)

    if action == Action.handle:
        text = f"{thanks} I've noted that and will pass it on to {owner}."
        if instruction:
            text += f" {instruction}"
        return (text + " Goodbye.", True)

    if action == Action.take_message:
        if not has_speech:
            return (
                "I wasn't able to understand the purpose of your call. "
                "If it's important, please call back or send a text message. Goodbye.",
                True,
            )
        text = f"{thanks} {owner} can't take the call right now, so I'll pass your message along."
        if instruction:
            text += f" {instruction}"
        return (text + " Goodbye.", True)

    # block
    if by_rule_block:
        return ("I'm sorry, I'm unable to help with this call. Goodbye.", True)
    if risk.label in (RiskLabel.fraud, RiskLabel.suspicious):
        return ("I'm unable to assist with this request. Goodbye.", True)
    return (f"Thanks, but {owner} isn't interested. Please remove this number from your call list. Goodbye.", True)
