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

## Validation
- Kotlin tests cover contact-normalization policy and mapping to both server contracts.
- `docs/member2-caller-examples.json` contains synthetic payloads; tests in each Python service validate these against their existing models.
- See `android-app/TEST-PLAN.md` for pending physical-phone/Airtel checks.
- The diagnostic UI is English-only; language-specific AI behavior is owned by the voice engine.

## Default dialer
Not requested. InCallService would require a proper dialer/in-call UI and still would not grant arbitrary SIM audio access. Supported local actions are allow and silence. Reject, hangup, AI answering, and carrier forwarding are not claimed by this module.
