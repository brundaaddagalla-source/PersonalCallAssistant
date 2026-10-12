import io
import os
import struct
import time
import wave
from pathlib import Path

ALLOWED = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}

def validate_audio_file(filename: str | None, size_bytes: int, max_mb: int, content: bytes | None = None) -> None:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED:
        allowed_str = ", ".join(sorted(ALLOWED))
        raise ValueError(f"Unsupported audio extension: '{suffix or '(none)'}'. Allowed formats: {allowed_str}")
    if size_bytes <= 0:
        raise ValueError("Audio file is empty (0 bytes).")
    if size_bytes > max_mb * 1024 * 1024:
        raise ValueError(f"Audio file exceeds the {max_mb} MB limit.")
    if content is not None and len(content) >= 4:
        if suffix == ".wav" and not content.startswith(b"RIFF"):
            raise ValueError("Invalid audio content: corrupted or missing WAV header.")
        if suffix == ".flac" and not content.startswith(b"fLaC"):
            raise ValueError("Invalid audio content: corrupted or missing FLAC header.")
        if suffix == ".ogg" and not content.startswith(b"OggS"):
            raise ValueError("Invalid audio content: corrupted or missing OGG header.")

def generate_mock_wav(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generates valid 16kHz mono PCM WAV audio bytes using standard library."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_frames = int(sample_rate * duration_seconds)
        data = struct.pack(f"<{num_frames}h", *([0] * num_frames))
        wf.writeframes(data)
    return buffer.getvalue()

def cleanup_old_audio_files(directory: str | Path, max_age_seconds: int = 3600) -> int:
    """Removes generated audio files older than max_age_seconds. Returns count of deleted files."""
    path = Path(directory)
    if not path.exists():
        return 0
    now = time.time()
    deleted_count = 0
    for file_path in path.glob("*"):
        if file_path.is_file():
            try:
                if now - file_path.stat().st_mtime > max_age_seconds:
                    file_path.unlink(missing_ok=True)
                    deleted_count += 1
            except OSError:
                pass
    return deleted_count

