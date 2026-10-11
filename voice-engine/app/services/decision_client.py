import re
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.models.schemas import DecisionResponse

class DecisionClientError(Exception):
    """Raised when the Member 3 Decision API call times out, fails, or returns invalid data."""
    pass

class DecisionClient:
    """
    Adapter for Member 3's AI Decision API.
    
    When DECISION_API_URL or AI_BACKEND_URL is configured, sends HTTP POST requests with
    full conversational transcript and caller context to POST /v1/decide.
    
    When unconfigured, uses a deterministic mock decision engine designed for
    local simulation and integration testing without external services.
    """
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._custom_base_url = base_url
        self._custom_timeout = timeout

    @property
    def base_url(self) -> str:
        if self._custom_base_url is not None:
            raw = self._custom_base_url.strip()
            if raw and not raw.rstrip("/").endswith("/v1/decide"):
                return f"{raw.rstrip('/')}/v1/decide"
            return raw.rstrip("/")
        return settings.effective_decision_url

    @property
    def timeout(self) -> float:
        if self._custom_timeout is not None:
            return self._custom_timeout
        return settings.decision_api_timeout_seconds

    async def decide(self, payload: dict) -> DecisionResponse:
        if not self.base_url:
            return self.mock_decision(payload)

        # Normalize request body to Member 3 DecideRequest schema
        request_body = self._build_request_body(payload)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=request_body)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise DecisionClientError(f"Decision API timed out after {self.timeout}s.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            snippet = exc.response.text[:200]
            raise DecisionClientError(f"Decision API returned HTTP {status}: {snippet}") from exc
        except httpx.RequestError as exc:
            raise DecisionClientError(f"Decision API network connection failed: {str(exc)}") from exc
        except Exception as exc:
            raise DecisionClientError(f"Decision API request failed: {type(exc).__name__} - {str(exc)}") from exc

        try:
            return self.parse_decision_response(data)
        except Exception as exc:
            raise DecisionClientError(f"Decision API returned invalid response schema: {str(exc)}") from exc

    def _build_request_body(self, payload: dict) -> dict:
        """Translates conversation context into Member 3's DecideRequest JSON contract."""
        call_id = payload.get("call_id") or payload.get("session_id", "sim-session")
        caller = payload.get("caller")
        if not caller:
            caller = {
                "number": payload.get("caller_number"),
                "is_known_contact": payload.get("is_known_contact", False),
                "contact_name": payload.get("caller_name") or payload.get("context", {}).get("caller_name"),
                "contact_group": payload.get("contact_group", "none"),
                "number_withheld": payload.get("number_withheld", False),
            }

        transcript = payload.get("transcript")
        if transcript is None:
            # Build from legacy format if transcript wasn't supplied directly
            transcript = []
            for t in payload.get("context", {}).get("history", []):
                spk = "agent" if t.get("speaker") in ("assistant", "agent") else "caller"
                transcript.append({"speaker": spk, "text": t.get("text", "")})
            if payload.get("caller_text"):
                transcript.append({"speaker": "caller", "text": payload["caller_text"]})

        preferences = payload.get("preferences")
        if not preferences:
            preferences = {
                "user_name": payload.get("user_name") or settings.user_name,
                "rules": payload.get("rules", []),
                "do_not_disturb": payload.get("do_not_disturb", False),
                "max_clarification_turns": payload.get("max_clarification_turns", 3),
            }

        received_at = payload.get("received_at") or datetime.now(timezone.utc).isoformat()

        return {
            "call_id": call_id,
            "caller": caller,
            "transcript": transcript,
            "preferences": preferences,
            "received_at": received_at,
        }

    @staticmethod
    def parse_decision_response(data: dict) -> DecisionResponse:
        """Parses Member 3 Decision JSON into normalized DecisionResponse."""
        action = data.get("action", "handle")
        speak_text = data.get("speak") or data.get("response_text", "")
        end_call = bool(data.get("end_call", False))

        intent_val = data.get("intent")
        confidence = None
        if isinstance(intent_val, dict):
            intent_name = intent_val.get("intent", "general")
            confidence = intent_val.get("confidence")
        elif isinstance(intent_val, str):
            intent_name = intent_val
        else:
            intent_name = "general"

        risk_val = data.get("risk")
        risk_label = risk_val.get("label", "low_risk") if isinstance(risk_val, dict) else "low_risk"

        notification_val = data.get("notification")
        notif_priority = notification_val.get("priority", "normal") if isinstance(notification_val, dict) else "normal"

        should_escalate = (
            action in ("transfer", "escalate")
            or intent_name == "emergency"
            or notif_priority == "high"
            or bool(data.get("should_escalate", False))
        )
        should_end_call = (
            end_call
            or action in ("block", "end_call")
            or bool(data.get("should_end_call", False))
        )

        return DecisionResponse(
            intent=intent_name,
            urgency="high" if should_escalate else "normal",
            spam_risk="high" if risk_label in ("fraud", "suspicious", "unwanted") else "low",
            action=action,
            response_text=speak_text,
            speak=speak_text,
            end_call=end_call,
            should_escalate=should_escalate,
            should_end_call=should_end_call,
            confidence=confidence,
            risk=risk_val if isinstance(risk_val, dict) else None,
            identification=data.get("identification"),
            reasons=data.get("reasons", []),
            matched_rule_id=data.get("matched_rule_id"),
            caution=bool(data.get("caution", False)),
            caller_summary=data.get("caller_summary"),
            caller_message=data.get("caller_message"),
            notification=notification_val,
        )

    @staticmethod
    def mock_decision(payload: dict) -> DecisionResponse:
        """
        Deterministic decision simulation for repeatable testing of demo scenarios.
        Supports multi-turn state awareness (e.g. delivery follow-ups).
        """
        transcript = payload.get("transcript", [])
        if transcript:
            caller_texts = [t.get("text", "") for t in transcript if t.get("speaker") in ("caller", "user")]
            all_caller = " ".join(caller_texts)
            latest_caller = caller_texts[-1] if caller_texts else ""
            agent_texts = [t.get("text", "") for t in transcript if t.get("speaker") in ("agent", "assistant")]
        else:
            all_caller = payload.get("caller_text", "")
            latest_caller = all_caller
            agent_texts = []

        all_text_lower = (all_caller + " " + latest_caller).strip().lower()
        latest_lower = latest_caller.strip().lower()

        # 1. Urgent / Emergency check (Scenario 3)
        if any(x in latest_lower for x in ("urgent", "immediately", "emergency", "accident", "hospital", "call me immediately")):
            resp = "I understand this is urgent. I am escalating this immediately and notifying the account holder to call you back."
            return DecisionResponse(
                intent="urgent_request",
                urgency="high",
                spam_risk="low",
                action="escalate",
                response_text=resp,
                speak=resp,
                should_escalate=True,
                should_end_call=False,
                end_call=False,
            )

        # 2. Possible Scam / Sensitive Credential solicitation (Scenario 5)
        if any(x in latest_lower for x in ("otp", "password", "prize", "lottery", "pin", "cvv", "won a prize", "bank account")):
            resp = "For security and privacy reasons, OTPs and sensitive account credentials are never shared. If this is a legitimate call, please state your name and organization."
            return DecisionResponse(
                intent="possible_scam",
                urgency="normal",
                spam_risk="high",
                action="take_message",
                response_text=resp,
                speak=resp,
                should_escalate=False,
                should_end_call=False,
                end_call=False,
            )

        # 3. Delivery / Courier inquiry (Scenario 1) with multi-turn follow-up awareness
        if any(x in all_text_lower for x in ("delivery", "parcel", "package", "courier")):
            has_tracking = bool(re.search(r"\b(?:trk|tracking|reference|waybill)\b|\b[A-Za-z]{2,}\d+\b|\b\d{5,}\b", latest_lower, re.I))
            already_asked = any("tracking reference" in t.lower() or "where should the package be left" in t.lower() for t in agent_texts)
            has_instruction = any(x in latest_lower for x in ("leave it", "neighbor", "security", "desk", "gate", "front door"))

            if has_tracking or (already_asked and (has_instruction or latest_lower)):
                resp = "Thank you. I have updated the delivery note and informed the recipient. Goodbye."
                return DecisionResponse(
                    intent="delivery",
                    urgency="normal",
                    spam_risk="low",
                    action="handle",
                    response_text=resp,
                    speak=resp,
                    should_escalate=False,
                    should_end_call=True,
                    end_call=True,
                )
            else:
                resp = "I can assist with your delivery. Where should the package be left, or what is the tracking reference?"
                return DecisionResponse(
                    intent="delivery",
                    urgency="normal",
                    spam_risk="low",
                    action="ask_followup",
                    response_text=resp,
                    speak=resp,
                    should_escalate=False,
                    should_end_call=False,
                    end_call=False,
                )

        # 4. Appointment / Rescheduling (Scenario 2)
        if any(x in latest_lower for x in ("reschedule", "appointment", "booking", "meeting", "doctor")):
            resp = "I can take a note about your appointment. What date and preferred time would you like to reschedule for?"
            return DecisionResponse(
                intent="appointment",
                urgency="normal",
                spam_risk="low",
                action="ask_followup",
                response_text=resp,
                speak=resp,
                should_escalate=False,
                should_end_call=False,
                end_call=False,
            )

        # 5. Unknown purpose / Speak with account holder (Scenario 4)
        if any(x in latest_lower for x in ("account holder", "speak with", "speak to", "talk to")):
            resp = "The account holder is currently unavailable. May I ask who is calling and the reason for your call?"
            return DecisionResponse(
                intent="unknown_purpose",
                urgency="normal",
                spam_risk="low",
                action="ask_followup",
                response_text=resp,
                speak=resp,
                should_escalate=False,
                should_end_call=False,
                end_call=False,
            )

        # 6. Default / General inquiry
        resp = "Thank you for calling. Could you please share your name and the message you would like to leave?"
        return DecisionResponse(
            intent="general",
            urgency="normal",
            spam_risk="unknown",
            action="take_message",
            response_text=resp,
            speak=resp,
            should_escalate=False,
            should_end_call=False,
            end_call=False,
        )
