from pathlib import Path
from uuid import uuid4
from app.config import settings
from app.services.audio_utils import generate_mock_wav, cleanup_old_audio_files

class TTSNotConfiguredError(RuntimeError):
    pass

class TTSGenerationError(RuntimeError):
    pass

async def synthesize(text: str) -> Path:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Text cannot be empty for speech synthesis.")
    if len(clean_text) > 4000:
        raise ValueError("Text exceeds maximum limit of 4000 characters for speech synthesis.")

    provider = settings.tts_provider.strip().lower()
    if provider == "disabled":
        raise TTSNotConfiguredError("TTS service is disabled. Set TTS_PROVIDER=edge-tts or TTS_PROVIDER=mock in .env.")


    folder = Path(settings.audio_storage_dir)
    folder.mkdir(parents=True, exist_ok=True)

    # Periodic cleanup of old cached audio files
    cleanup_old_audio_files(folder, max_age_seconds=settings.max_audio_retention_seconds)

    if provider == "mock":
        # Deterministic offline mock TTS for tests and zero-network simulations
        path = folder / f"{uuid4()}.wav"
        wav_bytes = generate_mock_wav(duration_seconds=1.5)
        path.write_bytes(wav_bytes)
        return path

    if provider == "edge-tts":
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSNotConfiguredError("edge-tts is not installed. Install with 'pip install edge-tts'.") from exc

        path = folder / f"{uuid4()}.mp3"
        try:
            communicate = edge_tts.Communicate(clean_text, settings.tts_voice)
            await communicate.save(str(path))
            return path
        except Exception as exc:
            raise TTSGenerationError(f"TTS synthesis provider error: {str(exc)}") from exc

    raise TTSNotConfiguredError(f"Unsupported TTS provider: '{settings.tts_provider}'. Use 'edge-tts', 'mock', or 'disabled'.")

