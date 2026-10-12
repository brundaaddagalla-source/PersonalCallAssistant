# Member 2 integration

## What was combined
The integration branch starts at `shakeera` commit `9504ab7`, which already includes `brunda`'s decision backend. The previously empty `android-app` folder now contains an Android application and reusable `telephony` library. Existing backend and voice-engine implementations are preserved.

## Local API
- `ContactLookup.lookup(number, cancellation)`: run off the UI thread; returns a `ContactMatch` with a distinct status.
- `ScreeningPolicy.decide(...)`: allow by default. Silence only a confirmed NOT_SAVED result when both explicit switches are enabled.
- `TelephonyStore`: local settings and a bounded event history; does not read the system call log.
- `CallerContext.from(number, match)`: conclusive matches only. Returns null for permission denial, timeouts, errors, and missing numbers.
- `CallerContext.decisionCaller()`: maps into Member 3's `Caller` request object.
- `CallerContext.voiceSession()`: maps into Member 4's `SessionCreate` request object.

The diagnostic screen previews both JSON payloads after a lookup. This is a local, reviewable handoff: no contacts leave the device. Future transport must require consent, authenticate the account, and use HTTPS. No HTTP call belongs in the Android screening callback's five-second deadline.

## Current server contract limitation
The server APIs model `is_known_contact` as a boolean. They cannot distinguish an unknown number from “not checked.” Do not send false for PERMISSION_DENIED, NUMBER_UNAVAILABLE, LOOKUP_FAILED, or TIMED_OUT. Keep the local call allowed; the adapter returns null. For production, Members 3 and 4 must add an explicit contact-match status and define safe rules for indeterminate callers, or resolve contacts server-side from separately consented, account-scoped data.

Contact groups remain `none`: the Android address book does not establish VIP/family/work trust categories. `number_withheld` remains false for concrete numbers; missing numbers are not automatically proof of intentional withholding.

## Carrier/provider flow
1. Airtel rings the phone and forwards under separately configured conditions.
2. The provider supplies an inbound call ID, original caller number when available, and target account.
3. Contact context is resolved independently of a live Android callback. The phone may be offline.
4. Member 4 starts a voice session and calls Member 3 for conversational decisions.
5. A `transfer` decision requests provider bridging / notification / an in-app voice client. It is not an operation implemented by this screening library.

The simulated voice telephony adapter does not implement this production flow. Never use an Android random event UUID as the provider's call identity, or match concurrent calls using timestamps alone.

## Connected integration implementation
- `AssistantApiClient`: Pure-Kotlin HTTP client using standard `HttpURLConnection` to query backend services without external library bloat.
  - Health checks: `checkHealth(baseUrl, path)` for Member 3 (`/health`) and Member 4 (`/health`).
  - AI Decision API: `decide(aiBackendUrl, callerContext, transcript, userName)` calling Member 3's `POST /v1/decide`.
  - Voice Engine API: `createVoiceSession(voiceEngineUrl, callerContext)` calling Member 4's `POST /api/sessions` and `sendVoiceTurn(voiceEngineUrl, sessionId, callerText)` calling `POST /api/sessions/{sessionId}/turn`.
- Asynchronous screening event enrichment:
  - Local `respondToCall(...)` executes immediately well within Android's 5-second deadline (1.2s timeout).
  - Telephony store records the screening event immediately.
  - If enabled and caller context is conclusive, background worker asynchronously queries Member 3's AI backend, updating the event with `decisionAction`, `intent`, `assistantResponse`, `escalationRequested`, and `backendStatus = "synced"` (or `"offline_fallback"` if unreachable).
  - Inconclusive callers (permission denied, lookup failure, timeout) are recorded with `backendStatus = "inconclusive_skipped"` and allowed to ring normally without false-positive silencing.
- Diagnostic harness (`MainActivity.kt`):
  - Displays configurable backend URLs (`store.aiBackendUrl` default `http://10.0.2.2:8000`, `store.voiceEngineUrl` default `http://10.0.2.2:8100`).
  - "Test server connections": checks health of both backends in background worker.
  - "Query AI Decision (Member 3)": sends test caller context to Member 3 and displays intent, action, spoken text, and risk assessment.
  - "Test Voice Turn (Member 4)": creates session and executes a multi-turn conversational interaction with Member 4's voice engine.
  - Unified event history: displays caller details, local screening action, AI decision, intent, spoken response, escalation badges, and session references.

## Validation
- Kotlin tests:
  - `PolicyTest`: validates contact-normalization rules, silence conditions, and phone number formatting.
  - `CallerContextTest`: validates schema mappings to both Member 3 and Member 4 contracts.
  - `IntegrationModelTest`: validates backward-compatible `ScreeningEvent` defaults and data classes.
  - Gradle test suite: `./gradlew :telephony:testDebugUnitTest` (all passing).
  - Gradle build: `./gradlew :app:assembleDebug` (build successful).
- Python integration tests:
  - `voice-engine/tests/test_member2_contract.py`: validates Member 2 payloads across 6 comprehensive flows:
    1. Saved caller (work/personal)
    2. Unsaved caller (delivery 2-turn flow)
    3. Unknown caller (callback request)
    4. Urgent matter escalation (emergency transfer)
    5. Suspicious caller (OTP fraud defense / block)
    6. Contract serialization fidelity
  - Full test suites: `ai-backend` (34 passed), `voice-engine` (55 passed).

## Default dialer
Not requested. InCallService would require a proper dialer/in-call UI and still would not grant arbitrary SIM audio access. Supported local actions are allow and silence. Reject, hangup, AI answering, and carrier forwarding are not claimed by this module.
