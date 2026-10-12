from app.config import settings

class STTNotConfiguredError(RuntimeError):
    pass

class SpeechToTextService:
    def __init__(self):
        self.model = None

    def transcribe(self, audio_path: str, language: str | None = None) -> dict:
        provider = settings.stt_provider.strip().lower()
        if provider == "disabled":
            raise STTNotConfiguredError("STT service is disabled. Set STT_PROVIDER=faster-whisper or STT_PROVIDER=mock in .env.")

        if provider == "mock":
            # Deterministic mock STT for testing and simulation without requiring audio models
            return {
                "text": "Hello, I am calling about your parcel delivery.",
                "language": language or "en",
                "language_probability": 0.99,
                "duration_seconds": 2.5
            }

        if provider == "faster-whisper":
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise STTNotConfiguredError("faster-whisper is not installed. Install with 'pip install faster-whisper'.") from exc

            try:
                if self.model is None:
                    self.model = WhisperModel(
                        settings.whisper_model,
                        device=settings.whisper_device,
                        compute_type=settings.whisper_compute_type
                    )
                segments, info = self.model.transcribe(audio_path, language=language, vad_filter=True)
                text = " ".join(s.text.strip() for s in segments).strip()
                duration = getattr(info, "duration", None)
                return {
                    "text": text,
                    "language": info.language,
                    "language_probability": getattr(info, "language_probability", 1.0),
                    "duration_seconds": duration
                }
            except Exception as exc:
                raise RuntimeError(f"Transcription execution failed: {str(exc)}") from exc

        raise STTNotConfiguredError(f"Unsupported STT provider: '{settings.stt_provider}'. Use 'faster-whisper', 'mock', or 'disabled'.")

stt_service = SpeechToTextService()

