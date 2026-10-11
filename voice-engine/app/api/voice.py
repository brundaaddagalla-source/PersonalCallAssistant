import tempfile
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.config import settings
from app.services.audio_utils import validate_audio_file
from app.services.stt_service import stt_service, STTNotConfiguredError
from app.services.tts_service import synthesize, TTSNotConfiguredError, TTSGenerationError
from app.state.session_store import store, SessionNotFound
from app.services.conversation_manager import manager
from app.services.decision_client import DecisionClientError

router = APIRouter(prefix="/api/voice", tags=["voice"])

@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str | None = Form(default=None)):
    """Transcribes an uploaded audio file using the configured STT provider."""
    data = await file.read()
    try:
        validate_audio_file(file.filename, len(data), settings.max_audio_mb, content=data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    path = None
    try:
        suffix = Path(file.filename or "audio.wav").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            path = tmp.name

        result = stt_service.transcribe(path, language)
        if not result.get("text"):
            raise HTTPException(422, "No speech detected in audio file.")
        return result
    except STTNotConfiguredError as exc:
        raise HTTPException(503, str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Transcription processing failed: {str(exc)}")
    finally:
        if path and Path(path).exists():
            Path(path).unlink(missing_ok=True)

@router.post("/speak")
async def speak(text: str = Form(...)):
    """Synthesizes text into speech audio using the configured TTS provider."""
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(400, "Text cannot be empty.")
    if len(clean_text) > 4000:
        raise HTTPException(413, "Text exceeds 4000 characters limit.")

    try:
        path = await synthesize(clean_text)
    except TTSNotConfiguredError as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except TTSGenerationError as exc:
        raise HTTPException(502, str(exc))

    media_type = "audio/wav" if path.suffix == ".wav" else "audio/mpeg"
    return FileResponse(str(path), media_type=media_type, filename=path.name)

@router.post("/process-audio")
async def process_audio_turn(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    generate_audio: bool = Form(default=False)
):
    """
    End-to-end voice turn pipeline:
    1. Transcribes incoming audio upload.
    2. Runs transcript through Conversation Manager & Decision API.
    3. Optionally synthesizes response speech.
    """
    # 1. Transcribe audio
    data = await file.read()
    try:
        validate_audio_file(file.filename, len(data), settings.max_audio_mb, content=data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    temp_path = None
    try:
        suffix = Path(file.filename or "audio.wav").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            temp_path = tmp.name

        transcription = stt_service.transcribe(temp_path, language)
        caller_text = transcription.get("text", "").strip()
        if not caller_text:
            raise HTTPException(422, "No speech detected in audio upload.")
    except STTNotConfiguredError as exc:
        raise HTTPException(503, str(exc))
    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink(missing_ok=True)

    # 2. Resolve or create session
    active_session_id = session_id
    if not active_session_id:
        new_session = store.create(
            caller_number="audio-upload",
            caller_name="Audio Caller",
            language=language or transcription.get("language") or "English"
        )
        active_session_id = new_session["session_id"]

    # 3. Process conversation turn
    try:
        turn_result = await manager.process_turn(
            session_id=active_session_id,
            caller_text=caller_text,
            language=language or transcription.get("language"),
            generate_audio=generate_audio
        )
        result_dict = turn_result.model_dump()
        result_dict["transcription"] = transcription
        return result_dict
    except SessionNotFound:
        raise HTTPException(404, f"Session '{active_session_id}' not found.")
    except ValueError as exc:
        msg = str(exc)
        if "ended" in msg.lower():
            raise HTTPException(409, msg)
        raise HTTPException(400, msg)
    except DecisionClientError as exc:
        raise HTTPException(502, f"Decision engine unavailable: {str(exc)}")

@router.get("/audio/{filename}")
def get_audio_file(filename: str):
    """Retrieves a generated audio file by filename with path traversal protection."""
    safe_name = Path(filename).name
    folder = Path(settings.audio_storage_dir)
    target = folder / safe_name
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Audio file '{safe_name}' not found.")

    media_type = "audio/wav" if target.suffix == ".wav" else "audio/mpeg"
    return FileResponse(str(target), media_type=media_type, filename=safe_name)

