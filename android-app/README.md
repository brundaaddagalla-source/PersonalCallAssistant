# Member 2 — Android Telephony & Contacts

A Kotlin Android project containing a reusable `telephony` library and a small native Android test app. Android 10+ (API 29). This implements Member 2’s prototype, not the whole voice assistant.

## Open and run
1. Open this folder in Android Studio compatible with Android Gradle Plugin 9.1.0.
2. Use JDK 17 and install Android SDK Platform 36 / Build Tools 36.0.0. Allow Gradle sync to download dependencies.
3. Connect your Android phone by USB, enable developer options and USB debugging, then run the `app` configuration.
4. In Call Assistant Lab, enable the caller-screening role and grant Contacts permission.
5. Try a saved number in the local lookup form. Call the phone from another phone, then refresh events.
6. Enable both local rules and silence-unsaved settings only when testing that behavior. Default behavior allows every call to ring.

A debug APK, when supplied alongside this project, is for development/testing, not a Play Store release. It has no INTERNET permission and never uploads contacts.

## What works in the implementation
- Android screening-role setup and runtime contacts-permission request.
- ContactsContract.PhoneLookup matching, with normalization of Indian mobile formats.
- Separate SAVED, NOT_SAVED, PERMISSION_DENIED, NUMBER_UNAVAILABLE, LOOKUP_FAILED and TIMED_OUT results.
- Incoming-call screening: allow by default; optionally silence confirmed unsaved numbers.
- Local contact lookup with a 1.2-second screening fallback, comfortably below Android's 5-second limit.
- Bounded local event history (50 entries), deletion, and a diagnostic screen.
- Phone permissions can be managed from system settings.

## Important boundaries
- This does not answer calls, access SIM-call audio, generate AI speech, activate forwarding, verify forwarding state, identify spam, or provide in-app call takeover.
- Silencing is not forwarding. Do not label it “send to AI.” Busy/reject forwarding behavior must be tested with Airtel and the chosen provider.
- Do not block unknown calls by default: they may be deliveries, appointments, or urgent calls.
- Android may omit calls with restricted/unknown presentation and other unsupported calls from screening. Missing events are not proof of no call.
- Without Contacts permission, Android generally sends only non-contact calls to the screening service. The module still reports PERMISSION_DENIED rather than pretending a lookup succeeded.
- Disabling local rules still allows diagnostic matching and local event logging while the screening role is held. To stop the service being selected, change the system’s default Caller ID & spam app. Neither action cancels Airtel forwarding.
- Records contain sensitive names/numbers in app-private storage; backups are disabled in the demo. No full address-book copy is stored. Clear events to delete history.

## Team integration
Member 1: add `implementation(project(":telephony"))` and include the module in settings. The library manifest merges its service and READ_CONTACTS permission. Replace the native demo UI with your Compose screens. Request the screening role and permission from an Activity; use ContactLookup off the UI thread. TelephonyStore exposes settings and events. This module does not need READ_CALL_LOG, ANSWER_PHONE_CALLS, or default-dialer privileges.

Member 3: ContactMatch is not identity verification. Map statuses as distinct values. Any future contact syncing needs explicit user consent and an authenticated backend; it is deliberately absent here. Server-side contact matching must work independently of whether the phone gets a screening callback or has internet. Do not call your decision API from the screening deadline path.

Member 4: own the telephony-provider inbound webhook/live audio integration in addition to speech services. The provider must identify the assistant account and original caller. Do not correlate calls solely by timestamps. Your provider's call ID and authenticated account mapping should be authoritative. In-app takeover needs the provider’s voice SDK or WebRTC.

## Default dialer investigation
Do not request ROLE_DIALER for this prototype. InCallService is a different role with obligations to provide dial/in-call UI and manage calls; it does not grant arbitrary SIM audio access. Add it only if a later requirement actually needs a replacement phone app. This prototype intentionally supports allow/silence, not answering/hanging up SIM calls or changing carrier forwarding.

## Build and tests
`./gradlew :app:assembleDebug :telephony:testDebugUnitTest :app:lintDebug`

See TEST-PLAN.md for tests that need physical phones and the Airtel provider. See ../docs/integration-validation.md for what was actually run.

## Official references
- https://developer.android.com/reference/android/telecom/CallScreeningService
- https://developer.android.com/reference/android/provider/ContactsContract.PhoneLookup
- https://developer.android.com/reference/android/telecom/InCallService
- https://developer.android.com/media/platform/sharing-audio-input

## Repository-specific mapping
See [Member 2 integration](../docs/member2-integration.md). The test screen previews local payloads for both existing APIs using `CallerContext`. No network client or automatic upload is installed.
