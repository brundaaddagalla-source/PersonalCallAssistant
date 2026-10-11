import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    use_llm: bool
    llm_model: str
    llm_timeout_s: float
    anthropic_api_key: str | None


def get_settings() -> Settings:
    """Read settings on every call so tests can change env vars."""
    return Settings(
        use_llm=os.getenv("USE_LLM", "false").lower() in ("1", "true", "yes"),
        llm_model=os.getenv("LLM_MODEL", "claude-haiku-5-5"),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "4")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
    )
