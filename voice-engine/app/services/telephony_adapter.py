"""
Telephony Integration Boundary for Voice AI Engine (Member 4).

Architecture Overview:
----------------------
In the production architecture:
1. Caller dials the user's personal mobile phone (e.g., Airtel subscriber).
2. Carrier Conditional Call Forwarding (*67* / *61* / *62*) forwards unanswered,
   busy, or declined calls to a dedicated virtual DID (hosted by a CPaaS or SIP trunk).
3. The Telephony Provider (e.g., Exotel, Twilio, Airtel IQ, or FreeSWITCH/Asterisk gateway)
   initiates an inbound webhook and opens a bidirectional live media stream (e.g. WebSocket PCM 8kHz/16kHz).
4. This Telephony Adapter boundary translates raw carrier media streams and call events into
   high-level voice-engine events (STT transcription, conversational decision turns, and TTS audio synthesis).
5. When an escalation is requested (urgency=high / action='escalate'), this adapter issues
   a carrier-level transfer command or push notification to the user's Android app.

NOTE: Real-time cellular audio streaming requires a finalized CPaaS/telephony partner.
The SimulatedTelephonyAdapter below provides a mock provider boundary for integration testing.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from app.state.session_store import store, SessionNotFound
from app.services.conversation_manager import manager
from app.models.schemas import TurnResponse

class TelephonyEventType(str, Enum):
    CALL_INITIATED = "call_initiated"
    CALL_ANSWERED = "call_answered"
    AUDIO_CHUNK = "audio_chunk"
    SPEECH_COMPLETED = "speech_completed"
    PLAY_AUDIO = "play_audio"
    ESCALATE_CALL = "escalate_call"
    CALL_HANGUP = "call_hangup"

class TelephonyEvent(BaseModel):
    call_id: str
    event_type: TelephonyEventType
    caller_number: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None

class BaseTelephonyAdapter(ABC):
    """
    Abstract interface for telephony provider bridges (Airtel IQ, Twilio, Exotel, etc.).
    """

    @abstractmethod
    async def on_call_start(self, call_id: str, caller_number: str | None, caller_name: str | None = None) -> str:
        """
        Invoked when an inbound phone call reaches the telephony trunk.
        Returns the associated voice-engine session_id.
        """
        pass

    @abstractmethod
    async def on_audio_chunk(self, call_id: str, chunk_bytes: bytes) -> None:
        """
        Receives an inbound raw audio frame (e.g. 20ms of PCM 8kHz/16kHz) from the telephony media stream.
        Buffers audio chunks until Voice Activity Detection (VAD) detects end of speech.
        """
        pass

    @abstractmethod
    async def on_speech_completed(self, call_id: str, transcript: str, language: str | None = None) -> TurnResponse:
        """
        Invoked when the caller finishes speaking a turn.
        Executes the turn through ConversationManager and returns the AI response.
        """
        pass

    @abstractmethod
    async def dispatch_audio_playback(self, call_id: str, audio_bytes: bytes) -> None:
        """
        Dispatches synthesized assistant audio back through the provider's media stream to the caller.
        """
        pass

    @abstractmethod
    async def on_escalate(self, call_id: str, reason: str) -> None:
        """
        Executes an escalation protocol (e.g., initiating carrier bridge or alerting Android app).
        """
        pass

    @abstractmethod
    async def on_call_end(self, call_id: str) -> None:
        """
        Terminates the voice-engine session and tears down provider call resources.
        """
        pass


class SimulatedTelephonyAdapter(BaseTelephonyAdapter):
    """
    Simulation adapter implementing the telephony boundary for local and CI testing.
    Maintains a mapping between external call_id and internal session_id.
    """
    def __init__(self):
        self._call_session_map: dict[str, str] = {}

    def get_session_id(self, call_id: str) -> str:
        session_id = self._call_session_map.get(call_id)
        if not session_id:
            raise SessionNotFound(f"No active session for call_id: {call_id}")
        return session_id

    async def on_call_start(self, call_id: str, caller_number: str | None, caller_name: str | None = None) -> str:
        session = store.create(caller_number=caller_number, caller_name=caller_name or "Telephony Caller")
        self._call_session_map[call_id] = session["session_id"]
        return session["session_id"]

    async def on_audio_chunk(self, call_id: str, chunk_bytes: bytes) -> None:
        # In live telephony, accumulates PCM frames and monitors VAD silence flags.
        # In simulation, audio chunk receiving is a no-op buffer stub.
        pass

    async def on_speech_completed(self, call_id: str, transcript: str, language: str | None = None) -> TurnResponse:
        session_id = self.get_session_id(call_id)
        turn_response = await manager.process_turn(session_id, transcript, language=language)
        if turn_response.decision.should_escalate:
            await self.on_escalate(call_id, reason=turn_response.decision.intent)
        return turn_response

    async def dispatch_audio_playback(self, call_id: str, audio_bytes: bytes) -> None:
        # In live telephony, converts MP3/WAV to μ-law 8kHz and writes to provider WebSocket.
        pass

    async def on_escalate(self, call_id: str, reason: str) -> None:
        session_id = self.get_session_id(call_id)
        store.set_status(session_id, "escalation_requested")

    async def on_call_end(self, call_id: str) -> None:
        session_id = self._call_session_map.pop(call_id, None)
        if session_id:
            try:
                store.set_status(session_id, "ended")
            except SessionNotFound:
                pass

telephony_adapter = SimulatedTelephonyAdapter()

