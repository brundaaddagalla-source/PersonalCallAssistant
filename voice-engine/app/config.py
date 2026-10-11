from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Voice Engine"
    app_env: str = "development"
    ai_backend_url: str | None = "http://127.0.0.1:8000"
    decision_api_url: str | None = None
    decision_api_timeout_seconds: float = 8.0
    user_name: str | None = "Alex"
    stt_provider: str = "disabled"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    tts_provider: str = "disabled"
    tts_voice: str = "en-IN-NeerjaNeural"
    max_audio_mb: int = 15
    audio_storage_dir: str = "generated_audio"
    max_audio_retention_seconds: int = 3600
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def effective_decision_url(self) -> str:
        raw = (self.decision_api_url or self.ai_backend_url or "").strip()
        if not raw or raw.lower() in ("disabled", "mock", "none"):
            return ""
        clean = raw.rstrip("/")
        if not clean.endswith("/v1/decide"):
            clean = f"{clean}/v1/decide"
        return clean

settings = Settings()


