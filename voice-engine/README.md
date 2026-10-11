# Member 4 — Voice AI & Integration Testing

Independent voice conversation service and integration test module for the **PersonalCallAssistant** project.

This service implements the complete Member 4 Voice AI pipeline:
```
Caller Audio or Demo Text
       │
       ▼
Speech-to-Text (STT) ── (faster-whisper, mock, or typed simulation)
       │
       ▼
Conversation Manager ── (session state, turn order, timestamps)
       │
       ▼
Member 3 Decision API ── (HTTP endpoint or deterministic mock simulation)
       │
       ▼
Text-to-Speech (TTS) ── (edge-tts, mock, or disabled text-only)
       │
       ▼
Audio Response + Escalation Status
```

---

## 1. Directory Structure

```
voice-engine/
├── .env.example                     # Sample environment configuration template
├── README.md                        # Module documentation and integration manual
├── requirements.txt                 # Python dependencies
├── app/
│   ├── __init__.py
│   ├── config.py                    # Pydantic environment settings
│   ├── main.py                      # FastAPI application and route registration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── demo.py                  # Demo conversation endpoint (turn simulation)
│   │   ├── health.py                # Health check and provider status
│   │   ├── sessions.py              # Session lifecycle (create, get, turn, end)
│   │   └── voice.py                 # Audio endpoints (transcribe, speak, process-audio, audio serve)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py               # Pydantic request and response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_utils.py           # Audio validation, mock WAV generator, file cleanup
│   │   ├── conversation_manager.py  # Turn pipeline, session history, status management
│   │   ├── decision_client.py       # Member 3 Decision API adapter & deterministic mock
│   │   ├── stt_service.py           # Speech-to-Text service abstraction (faster-whisper / mock)
│   │   ├── telephony_adapter.py     # Telephony provider integration boundary & simulation
│   │   └── tts_service.py           # Text-to-Speech service abstraction (edge-tts / mock)
│   └── state/
│       ├── __init__.py
│       └── session_store.py         # Thread-safe in-memory session store
├── samples/
│   └── README.md                    # Guidance for consented testing audio
└── tests/
    ├── __init__.py
    ├── test_api.py                  # API endpoints, session lifecycle, demo tests
    ├── test_conversation.py         # Multi-turn history, timestamps, resilience tests
    ├── test_decision_client.py      # Decision client mock scenarios and HTTP resilience
    ├── test_scenarios.py            # Complete tests for all 8 required demo scenarios
    └── test_stt_tts.py              # STT/TTS validation, mock audio, and file cleanup
```

---

## 2. Python Environment & Dependency Compatibility

- **Primary Runtime:** Python 3.14.0 (Windows 64-bit AMD64).
- **Compatibility Testing Report:**
  - `fastapi` (0.115+) & `uvicorn` (0.30+): Fully compatible and verified.
  - `pydantic-settings` (2.4+) & `pydantic` (2.10+): Fully compatible and verified.
  - `httpx` (0.27+): Fully compatible and verified.
  - `faster-whisper` (1.2.1) & `ctranslate2` (4.8.2): Verified to import and run on this Python 3.14 environment.
  - `edge-tts` (6.1+): Verified to import and synthesize audio asynchronously on this Python 3.14 environment.
- **Production Recommendation:** For containerized Linux deployments or systems without pre-built CTranslate2 binary wheels, **Python 3.11 or 3.12** remains the recommended standard for enterprise AI audio workloads.

---

## 3. Installation & Setup

### Windows (PowerShell)
```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment
Copy-Item .env.example .env

# 4. Start the server
python -m uvicorn app.main:app --reload --port 8100
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn app.main:app --reload --port 8100
```

### Interactive API Documentation (Swagger UI)
Once started, visit:
**`http://127.0.0.1:8100/docs`**

---

## 4. Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Voice Engine` | Service application name |
| `APP_ENV` | `development` | Deployment environment (`development`, `staging`, `production`) |
| `DECISION_API_URL` | `""` (empty) | URL of Member 3's AI Decision API. When empty, runs in deterministic **mock simulation mode** |
| `DECISION_API_TIMEOUT_SECONDS` | `8.0` | Timeout for external decision API HTTP calls |
| `STT_PROVIDER` | `disabled` | Speech-to-Text provider: `disabled`, `faster-whisper`, or `mock` |
| `WHISPER_MODEL` | `base` | Model size for faster-whisper (`tiny`, `base`, `small`, `medium`) |
| `WHISPER_DEVICE` | `cpu` | Device execution target (`cpu` or `cuda`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Quantization type for CPU execution (`int8`, `float32`) |
| `TTS_PROVIDER` | `disabled` | Text-to-Speech provider: `disabled`, `edge-tts`, or `mock` |
| `TTS_VOICE` | `en-IN-NeerjaNeural` | Voice identifier. Default is Indian English female voice |
| `MAX_AUDIO_MB` | `15` | Maximum permissible audio upload size in megabytes |
| `AUDIO_STORAGE_DIR` | `generated_audio` | Local folder for temporary synthesized audio output |
| `MAX_AUDIO_RETENTION_SECONDS` | `3600` | Retention duration (1 hour) before cached audio cleanup |

---

## 5. API Reference & Endpoints

### Health & Diagnostics
- `GET /health` or `GET /api/health`
  - Returns service status, active session count, Python version, STT/TTS provider state, and decision mode (`mock` or `http`).

### Session Management
- `POST /api/sessions`
  - Creates a conversation session.
  - **Request Body:**
    ```json
    {
      "caller_number": "+919876543210",
      "caller_name": "Ravi Kumar",
      "language": "English"
    }
    ```
  - **Response (200):**
    ```json
    {
      "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "status": "active",
      "caller_number": "+919876543210",
      "caller_name": "Ravi Kumar",
      "language": "English",
      "created_at": "2026-10-11T09:30:00.000000+00:00"
    }
    ```

- `GET /api/sessions/{session_id}`
  - Retrieves full session metadata and complete turn history with timestamps.
  - Returns HTTP 404 if the session ID is unknown.

- `POST /api/sessions/{session_id}/turn`
  - Submits a caller text turn to an active session.
  - **Request Body:**
    ```json
    {
      "caller_text": "I am calling about your parcel delivery.",
      "language": "English",
      "generate_audio": false
    }
    ```
  - **Response (200):**
    ```json
    {
      "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "turn_number": 1,
      "caller_text": "I am calling about your parcel delivery.",
      "assistant_text": "I can assist with your delivery. Where should the package be left, or what is the tracking reference?",
      "decision": {
        "intent": "delivery",
        "urgency": "normal",
        "spam_risk": "low",
        "action": "ask_followup",
        "response_text": "I can assist with your delivery. Where should the package be left, or what is the tracking reference?",
        "should_escalate": false,
        "should_end_call": false
      },
      "session_status": "active",
      "audio_generated": false,
      "audio_url": null
    }
    ```
  - Returns HTTP 409 Conflict if the session is ended.
  - Returns HTTP 400 Bad Request if caller text is empty.

- `POST /api/sessions/{session_id}/end`
  - Explicitly terminates a conversation session. Returns status `"ended"`.

### Complete Demo Conversation Endpoint
- `POST /api/demo/conversation`
  - Executes one full conversational turn in a single request.
  - If `session_id` is provided, continues that existing session.
  - If `session_id` is omitted, automatically creates a new session.
  - **Request Body:**
    ```json
    {
      "language": "English",
      "caller_text": "Hello, I am calling about your parcel delivery.",
      "generate_audio": false
    }
    ```
  - **Response (200):**
    ```json
    {
      "session_id": "c1f7a0b3-9e45-423c-8a12-8e7c1341d210",
      "turn_number": 1,
      "language": "English",
      "caller_text": "Hello, I am calling about your parcel delivery.",
      "assistant_text": "I can assist with your delivery. Where should the package be left, or what is the tracking reference?",
      "intent": "delivery",
      "urgency": "normal",
      "spam_risk": "low",
      "action": "ask_followup",
      "should_escalate": false,
      "should_end_call": false,
      "session_status": "active",
      "audio_generated": false,
      "audio_url": null
    }
    ```

### Audio Endpoints
- `POST /api/voice/transcribe`
  - Accepts `multipart/form-data` with `file: UploadFile` and optional `language`.
  - Validates file size (≤ `MAX_AUDIO_MB`), allowed extensions (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.webm`, `.flac`), and audio headers.
  - Returns transcript, detected language, and confidence.
  - Returns HTTP 503 if STT is disabled.

- `POST /api/voice/speak`
  - Accepts form field `text: str`.
  - Synthesizes speech and returns an audio file stream (`audio/mpeg` or `audio/wav`).
  - Returns HTTP 503 if TTS is disabled.

- `POST /api/voice/process-audio`
  - Dedicated multi-step audio turn endpoint: accepts an audio file upload, transcribes caller speech, executes the conversational turn through the decision engine, and optionally synthesizes the response audio.

- `GET /api/voice/audio/{filename}`
  - Retrieves a synthesized audio file by filename with strict path-traversal prevention.

---

## 6. Repeatable Demo Scenarios

The module includes deterministic mock responses for quick verification without external APIs:

### Scenario 1 — Delivery
- **Input:** `"Hello, I am calling about your parcel delivery."`
- **Output:** `intent="delivery"`, `action="ask_followup"`, asks for delivery drop-off location or tracking number.

### Scenario 2 — Appointment Reschedule
- **Input:** `"I need to reschedule my appointment for tomorrow."`
- **Output:** `intent="appointment"`, `action="ask_followup"`, asks for preferred date and time.

### Scenario 3 — Urgent Emergency
- **Input:** `"This is urgent. Please ask the account holder to call me immediately."`
- **Output:** `intent="urgent_request"`, `urgency="high"`, `action="escalate"`, `should_escalate=true`, `session_status="escalation_requested"`.

### Scenario 4 — Unknown Purpose / Account Holder
- **Input:** `"Hello, I need to speak with the account holder."`
- **Output:** `intent="unknown_purpose"`, `action="ask_followup"`, informs caller account holder is unavailable, asks for caller name and reason.

### Scenario 5 — Possible Scam / OTP Solicitation
- **Input:** `"You have won a prize. Please tell me your OTP."`
- **Output:** `intent="possible_scam"`, `spam_risk="high"`, `action="take_message"`. Cautious response: never reveals or asks for OTPs, passwords, or credentials.

### Scenario 6 — Session Ended
- **Action:** End session via `POST /api/sessions/{session_id}/end`, then submit a turn to `POST /api/sessions/{session_id}/turn`.
- **Output:** HTTP 409 Conflict: `"Session has ended. No further turns are accepted."` History remains uncorrupted.

### Scenario 7 — Invalid Audio Upload
- **Action:** Upload empty file (0 bytes) or unsupported `.exe`/`.txt` file to `/api/voice/transcribe`.
- **Output:** HTTP 400 Bad Request with a clear message without application crash.

### Scenario 8 — STT or TTS Unavailable
- **Action:** Set `STT_PROVIDER=disabled` or `TTS_PROVIDER=disabled` and call respective endpoints.
- **Output:** HTTP 503 Service Unavailable with clear configuration instructions, not a crash.

---

## 7. Member 3 Decision API Contract

When Member 3 exposes their service, configure:
```env
DECISION_API_URL=http://<member-3-host>:<port>/api/decision
```

### Request Sent by Voice Engine
```json
{
  "session_id": "c1f7a0b3-9e45-423c-8a12-8e7c1341d210",
  "caller_text": "I am calling to reschedule tomorrow's appointment",
  "caller_number": "+919876543210",
  "turn_number": 1,
  "language": "English",
  "context": {
    "caller_name": "Ravi Kumar",
    "previous_intent": null,
    "history": [
      {
        "turn_number": 1,
        "speaker": "caller",
        "text": "Hello",
        "intent": "general",
        "timestamp": "2026-10-11T09:30:00+00:00"
      }
    ]
  }
}
```

### Expected Response Schema from Member 3
```json
{
  "intent": "appointment",
  "urgency": "normal",
  "spam_risk": "low",
  "action": "ask_followup",
  "response_text": "I can help note your reschedule request. What time works best?",
  "should_escalate": false,
  "should_end_call": false
}
```
Supported actions: `ask_followup`, `take_message`, `escalate`, `end_call`, `continue`.

---

## 8. Telephony Integration Boundary (Airtel & Live Audio Streaming)

### Conceptual Telephony Architecture
```
[Caller]
   │
   ▼
[Airtel Carrier Network]
   │ Conditional Call Forwarding (*67* / *61* / *62*)
   ▼
[Virtual DID / SIP Trunk] (Exotel / Twilio / Airtel IQ / Asterisk)
   │ Inbound Webhook + WebSocket Audio Stream (PCM 8kHz / 16kHz)
   ▼
[app/services/telephony_adapter.py] (Telephony Integration Boundary)
   │
   ├── Audio chunks buffered & VAD detects end of turn
   ├── Speech converted to text via STT
   ├── ConversationManager processes decision turn
   └── Response synthesized via TTS and streamed back to caller
```

### Important Boundary Principles
1. **Simulation vs Real Telephony:** This voice engine currently operates in **simulation mode**. It does not answer cellular phone calls directly over hardware radio interfaces.
2. **Carrier Forwarding Requirement:** In production, the user configures standard carrier call forwarding on their mobile phone (e.g. `*67*<Virtual_DID>#` on Airtel for call forwarding when busy or declined).
3. **Telephony Adapter Abstraction:** The file `app/services/telephony_adapter.py` provides the `BaseTelephonyAdapter` interface and `SimulatedTelephonyAdapter` implementation. When the team selects a CPaaS provider, the provider-specific WebSocket handler plugs into this adapter without altering the conversation pipeline.

---

## 9. Running Tests

Run the comprehensive pytest suite:
```powershell
python -m pytest -q
```

Expected output:
```
44 passed in 4.86s
```

The test suite covers:
- Service health and diagnostics
- Session creation, turn processing, turn retrieval, and termination
- 404 on unknown session IDs and 409 on ended session turns
- In-order turns and UTC ISO timestamps
- Mock decision engine determinism for all 5 conversational categories
- HTTP decision client timeout, 500 error, and invalid schema handling
- Audio file validation (extension, empty file, file size, header corruption)
- STT disabled and mock modes
- TTS disabled and mock modes
- All 8 repeatable demo scenarios
- Telephony adapter simulation lifecycle
- Temporary audio file cleanup utility

---

## 10. Production Gaps & Deployment Checklist

Before deploying this module to production:
1. **Persistence:** Replace in-memory `SessionStore` with a durable database (e.g., PostgreSQL or Redis) to ensure session history survives service restarts.
2. **Authentication & Authorization:** Secure session and voice endpoints with JWT or API key authentication.
3. **Telephony Webhook Verification:** Implement HMAC signature verification for incoming telephony provider webhooks.
4. **Data Retention & Consent:** Implement automated audio scrubbing and caller consent disclaimers adhering to local telecommunications regulations.
5. **Real-time Media Streaming:** Wire the `TelephonyAdapter` to a production WebSocket media stream gateway when the carrier/CPaaS partner is selected.
