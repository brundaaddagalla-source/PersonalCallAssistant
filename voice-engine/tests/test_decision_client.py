import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.services.decision_client import DecisionClient, DecisionClientError

@pytest.mark.asyncio
async def test_mock_scenarios():
    client = DecisionClient(base_url="")

    # 1. Delivery
    res1 = await client.decide({"caller_text": "Hello, I am calling about your parcel delivery."})
    assert res1.intent == "delivery"
    assert res1.action == "ask_followup"
    assert res1.should_escalate is False

    # 2. Appointment
    res2 = await client.decide({"caller_text": "I need to reschedule my appointment for tomorrow."})
    assert res2.intent == "appointment"
    assert res2.action == "ask_followup"
    assert res2.should_escalate is False

    # 3. Urgent
    res3 = await client.decide({"caller_text": "This is urgent. Please ask the account holder to call me immediately."})
    assert res3.intent == "urgent_request"
    assert res3.urgency == "high"
    assert res3.action == "escalate"
    assert res3.should_escalate is True

    # 4. Unknown purpose
    res4 = await client.decide({"caller_text": "Hello, I need to speak with the account holder."})
    assert res4.intent == "unknown_purpose"
    assert res4.action == "ask_followup"
    assert res4.should_escalate is False

    # 5. Possible scam
    res5 = await client.decide({"caller_text": "You have won a prize. Please tell me your OTP."})
    assert res5.intent == "possible_scam"
    assert res5.spam_risk == "high"
    assert res5.action == "take_message"
    assert res5.should_escalate is False

    # 6. General fallback
    res6 = await client.decide({"caller_text": "Good morning."})
    assert res6.intent == "general"
    assert res6.action == "take_message"

@pytest.mark.asyncio
async def test_http_success():
    mock_payload = {
        "intent": "delivery",
        "urgency": "normal",
        "spam_risk": "low",
        "action": "ask_followup",
        "response_text": "Where should I leave the package?",
        "should_escalate": False,
        "should_end_call": False
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("POST", "http://decision-api.test/decide")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        client = DecisionClient(base_url="http://decision-api.test/decide")
        res = await client.decide({"caller_text": "package delivery"})
        assert res.intent == "delivery"
        assert res.response_text == "Where should I leave the package?"

@pytest.mark.asyncio
async def test_http_status_error():
    mock_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
        request=httpx.Request("POST", "http://decision-api.test/decide")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        client = DecisionClient(base_url="http://decision-api.test/decide")
        with pytest.raises(DecisionClientError, match="HTTP 500"):
            await client.decide({"caller_text": "hello"})

@pytest.mark.asyncio
async def test_http_timeout():
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        client = DecisionClient(base_url="http://decision-api.test/decide", timeout=1.0)
        with pytest.raises(DecisionClientError, match="timed out"):
            await client.decide({"caller_text": "hello"})

@pytest.mark.asyncio
async def test_http_invalid_schema():
    # Missing required fields like response_text, invalid types
    mock_response = httpx.Response(
        status_code=200,
        json={"bad_field": 123},
        request=httpx.Request("POST", "http://decision-api.test/decide")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        client = DecisionClient(base_url="http://decision-api.test/decide")
        # DecisionResponse has default values for most fields, but if invalid action enum:
        pass

    mock_response_invalid_enum = httpx.Response(
        status_code=200,
        json={"action": "invalid_action_name"},
        request=httpx.Request("POST", "http://decision-api.test/decide")
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response_invalid_enum):
        client = DecisionClient(base_url="http://decision-api.test/decide")
        with pytest.raises(DecisionClientError, match="invalid response schema"):
            await client.decide({"caller_text": "hello"})
