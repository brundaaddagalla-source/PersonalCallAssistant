import httpx
from app.config import settings
from app.models.schemas import DecisionResponse

class DecisionClientError(Exception):
    """Raised when the Member 3 Decision API call times out, fails, or returns invalid data."""
    pass

class DecisionClient:
    """
    Adapter for Member 3's AI Decision API.
    
    When DECISION_API_URL is configured, sends HTTP POST requests with conversation context.
    When unconfigured (default), uses a deterministic mock decision engine designed for
    local simulation and integration testing.
    
    NOTE: The mock decision engine is purely a demo implementation and rule-based stub.
    It is NOT an AI model or a production spam classifier.
    """
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        configured_url = settings.decision_api_url.strip() if settings.decision_api_url else ""
        self.base_url = (base_url if base_url is not None else configured_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.decision_api_timeout_seconds

    async def decide(self, payload: dict) -> DecisionResponse:
        if not self.base_url:
            return self.mock_decision(payload)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=payload)
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
            return DecisionResponse.model_validate(data)
        except Exception as exc:
            raise DecisionClientError(f"Decision API returned invalid response schema: {str(exc)}") from exc

    @staticmethod
    def mock_decision(payload: dict) -> DecisionResponse:
        """
        Deterministic decision simulation for repeatable testing of demo scenarios:
        - Scenario 1: Delivery
        - Scenario 2: Appointment reschedule
        - Scenario 3: Urgent emergency (triggers escalation)
        - Scenario 4: Unknown purpose / speak with account holder
        - Scenario 5: Possible scam / OTP request (high spam risk, refuses secret sharing)
        """
        text = payload.get("caller_text", "").strip().lower()

        # 1. Urgent / Emergency check (Scenario 3)
        if any(x in text for x in ("urgent", "immediately", "emergency", "accident", "hospital", "call me immediately")):
            return DecisionResponse(
                intent="urgent_request",
                urgency="high",
                spam_risk="low",
                action="escalate",
                response_text="I understand this is urgent. I am escalating this immediately and notifying the account holder to call you back.",
                should_escalate=True,
                should_end_call=False
            )

        # 2. Possible Scam / Sensitive Credential solicitation (Scenario 5)
        if any(x in text for x in ("otp", "password", "prize", "lottery", "pin", "cvv", "won a prize", "bank account")):
            return DecisionResponse(
                intent="possible_scam",
                urgency="normal",
                spam_risk="high",
                action="take_message",
                response_text="For security and privacy reasons, OTPs and sensitive account credentials are never shared. If this is a legitimate call, please state your name and organization.",
                should_escalate=False,
                should_end_call=False
            )

        # 3. Delivery / Courier inquiry (Scenario 1)
        if any(x in text for x in ("delivery", "parcel", "package", "courier")):
            return DecisionResponse(
                intent="delivery",
                urgency="normal",
                spam_risk="low",
                action="ask_followup",
                response_text="I can assist with your delivery. Where should the package be left, or what is the tracking reference?",
                should_escalate=False,
                should_end_call=False
            )

        # 4. Appointment / Rescheduling (Scenario 2)
        if any(x in text for x in ("reschedule", "appointment", "booking", "meeting", "doctor")):
            return DecisionResponse(
                intent="appointment",
                urgency="normal",
                spam_risk="low",
                action="ask_followup",
                response_text="I can take a note about your appointment. What date and preferred time would you like to reschedule for?",
                should_escalate=False,
                should_end_call=False
            )

        # 5. Unknown purpose / Speak with account holder (Scenario 4)
        if any(x in text for x in ("account holder", "speak with", "speak to", "talk to")):
            return DecisionResponse(
                intent="unknown_purpose",
                urgency="normal",
                spam_risk="low",
                action="ask_followup",
                response_text="The account holder is currently unavailable. May I ask who is calling and the reason for your call?",
                should_escalate=False,
                should_end_call=False
            )

        # 6. Default / General inquiry
        return DecisionResponse(
            intent="general",
            urgency="normal",
            spam_risk="unknown",
            action="take_message",
            response_text="Thank you for calling. Could you please share your name and the message you would like to leave?",
            should_escalate=False,
            should_end_call=False
        )

