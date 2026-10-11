# Member 1 validation — 11 October 2026

## Implemented
- Replaced the diagnostic launcher with five Jetpack Compose screens: Recents, Contacts, Keypad, Assistant, Settings.
- Added iPhone-inspired translucent surfaces, capsule navigation, circular keypad, and System/Light/Dark themes.
- Persisted preferences, quiet hours, weekday selection, favorites, and per-number rules locally.
- Connected local rules to the existing screening service, including always-ring overrides and fail-open behavior.
- Added optional screening notifications and an in-app activity inbox.
- Retained Member 2 tools in Settings → Developer diagnostics.

## Automated validation
Command from `android-app` with JDK 17 and an Android SDK:

```sh
./gradlew :app:testDebugUnitTest :telephony:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

- Debug APK assembled successfully.
- 12 telephony unit tests passed: number/policy behavior, caller-context mapping, quiet hours and contact rules.
- 1 Robolectric Compose interaction test passed: tab navigation, keypad entry/deletion/clear, assistant toggle, appearance and assistant persistence across recreation, and contacts-permission UI.
- Android lint: no errors. Remaining warnings include dependency updates, backup configuration guidance, and legacy diagnostic-screen localization/style suggestions.
- Rendered app previews reviewed for light and dark appearance; corrected dark text contrast during review.
- The previous integration's 34 backend and 50 voice-engine tests passed before this UI change; those modules were not changed or retested for Member 1.

Robolectric uses an API 35 instrumented Android runtime downloaded through Gradle; screenshots are host-rendered previews, not physical-device captures. Output: `app/build/ui-previews/`.

## Still requires a phone
Physical Android/Airtel testing was not performed. Verify contact permission and call-screening-role prompts, actual incoming calls, notifications, dialer handoff, smaller displays/large text, and manufacturer battery restrictions with the checklist in `android-app/TEST-PLAN.md`. The native emulator could not run on this host; Robolectric does not substitute for carrier testing.

This version does not activate carrier forwarding, connect the backend/voice service to live calls, provide remote AI summaries, or transfer a caller to the user. The UI makes those connection states explicit.
