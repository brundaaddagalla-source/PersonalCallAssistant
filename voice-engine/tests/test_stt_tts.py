import io
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.audio_utils import validate_audio_file, generate_mock_wav, cleanup_old_audio_files
from app.services.stt_service import stt_service, STTNotConfiguredError
from app.services.tts_service import synthesize, TTSNotConfiguredError

client = TestClient(app)

def test_audio_file_validation():
    # 1. Valid WAV bytes
    valid_wav = generate_mock_wav(duration_seconds=0.5)
    validate_audio_file("recording.wav", len(valid_wav), max_mb=15, content=valid_wav)

    # 2. Unsupported extension
    with pytest.raises(ValueError, match="Unsupported audio extension"):
        validate_audio_file("recording.txt", 100, max_mb=15)

    # 3. Empty file
    with pytest.raises(ValueError, match="Audio file is empty"):
        validate_audio_file("recording.wav", 0, max_mb=15)

    # 4. File exceeds limit
    with pytest.raises(ValueError, match="exceeds the 1 MB limit"):
        validate_audio_file("recording.wav", 2 * 1024 * 1024, max_mb=1)

    # 5. Invalid WAV header content
    corrupt_data = b"NOT_A_WAV_HEADER_DATA"
    with pytest.raises(ValueError, match="corrupted or missing WAV header"):
        validate_audio_file("recording.wav", len(corrupt_data), max_mb=15, content=corrupt_data)

def test_stt_service_disabled(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "disabled")
    with pytest.raises(STTNotConfiguredError, match="STT service is disabled"):
        stt_service.transcribe("non_existent.wav")

def test_stt_service_mock(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "mock")
    res = stt_service.transcribe("any_audio.wav", language="en")
    assert "parcel delivery" in res["text"]
    assert res["language"] == "en"

def test_api_transcribe_disabled(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "disabled")
    wav_bytes = generate_mock_wav()
    files = {"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")}
    res = client.post("/api/voice/transcribe", files=files)
    assert res.status_code == 503
    assert "STT service is disabled" in res.json()["detail"]

def test_api_transcribe_empty_file():
    files = {"file": ("empty.wav", io.BytesIO(b""), "audio/wav")}
    res = client.post("/api/voice/transcribe", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()

def test_api_transcribe_invalid_extension():
    files = {"file": ("script.py", io.BytesIO(b"print('hello')"), "text/plain")}
    res = client.post("/api/voice/transcribe", files=files)
    assert res.status_code == 400
    assert "unsupported" in res.json()["detail"].lower()

def test_api_transcribe_mock_success(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "mock")
    wav_bytes = generate_mock_wav()
    files = {"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")}
    res = client.post("/api/voice/transcribe", files=files)
    assert res.status_code == 200
    assert "text" in res.json()
    assert len(res.json()["text"]) > 0

def test_tts_service_disabled(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "disabled")
    with pytest.raises(TTSNotConfiguredError, match="TTS service is disabled"):
        import asyncio
        asyncio.run(synthesize("Hello world"))

def test_tts_service_validation():
    with pytest.raises(ValueError, match="cannot be empty"):
        import asyncio
        asyncio.run(synthesize("   "))

    with pytest.raises(ValueError, match="exceeds maximum limit"):
        import asyncio
        asyncio.run(synthesize("A" * 4001))

def test_api_speak_disabled(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "disabled")
    res = client.post("/api/voice/speak", data={"text": "Hello"})
    assert res.status_code == 503

def test_api_speak_validation():
    res_empty = client.post("/api/voice/speak", data={"text": "   "})
    assert res_empty.status_code == 400

    res_long = client.post("/api/voice/speak", data={"text": "x" * 4001})
    assert res_long.status_code == 413

def test_api_speak_mock(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "tts_provider", "mock")
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    res = client.post("/api/voice/speak", data={"text": "Testing mock audio synthesis"})
    assert res.status_code == 200
    assert res.headers["content-type"] in ("audio/wav", "audio/mpeg")
    assert len(res.content) > 0

def test_audio_cleanup_utility(tmp_path):
    # Create old and new files
    old_file = tmp_path / "old_audio.wav"
    old_file.write_bytes(b"old_audio_data")
    
    new_file = tmp_path / "new_audio.wav"
    new_file.write_bytes(b"new_audio_data")

    # Set old_file timestamp to 2 hours ago
    past_time = time.time() - 7200
    import os
    os.utime(str(old_file), (past_time, past_time))

    deleted = cleanup_old_audio_files(tmp_path, max_age_seconds=3600)
    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()

def test_api_process_audio_pipeline(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "mock")
    wav_bytes = generate_mock_wav(duration_seconds=1.0)
    files = {"file": ("caller_recording.wav", io.BytesIO(wav_bytes), "audio/wav")}
    res = client.post("/api/voice/process-audio", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["turn_number"] == 1
    assert data["decision"]["intent"] == "delivery"
    assert "transcription" in data
    assert "parcel delivery" in data["transcription"]["text"]

