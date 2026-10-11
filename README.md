# Personal Call Assistant

An Android call-assistant prototype for an existing Airtel number. This integration branch combines the backend from `brunda`, voice engine from `shakeera`, and Members 1–2's Android UI and telephony/contact modules. It does not represent a deployed carrier integration.

| Folder | Responsibility | Current state |
|---|---|---|
| android-app | Members 1–2: Compose UI, preferences, contacts, local screening | Glass-inspired phone UI, schedules, rules, notifications, diagnostics, and tests |
| ai-backend | Member 3: intent, risk, and decision API | FastAPI implementation with tests |
| voice-engine | Member 4: voice/session orchestration | FastAPI implementation and simulated telephony adapter |
| docs | Team contracts and acceptance checklist | Includes the Android/backend integration boundary |

## Android
Open `android-app` in Android Studio. Use JDK 17 and Android SDK 36. Run the `app` configuration on an Android 10+ phone, grant the caller-screening role and Contacts permission, then call it from another phone. See [Android instructions](android-app/README.md).

```sh
cd android-app
./gradlew :app:assembleDebug :telephony:testDebugUnitTest :app:lintDebug
```

Member 1’s Jetpack Compose frontend now includes Recents, Contacts, Keypad, Assistant, and Settings. Member 2’s original diagnostic screen remains under Settings. See [Member 1 implementation](docs/member1-ui.md).

## Python services
Use separate environments/processes: both services use the Python package name `app`, so do not run their tests as one combined pytest invocation.

- [Decision backend](ai-backend/README.md)
- [Voice engine](voice-engine/README.md)
- [Member 2 integration contract](docs/member2-integration.md)
- [AI API](docs/ai-backend-api.md)

## Current boundaries
Airtel must forward the call to a selected phone-service provider for the AI to converse. Android CallScreeningService can allow or silence eligible incoming calls; it cannot provide SIM-call audio or transfer a forwarded call. The Android app performs no network requests, uploads no contacts, and does not change carrier forwarding. The voice provider remains simulated. Contact sync, authentication, notifications, live provider media, and in-app takeover are still separate work.

Do not expose the prototype Python services publicly without authentication and account-scoped authorization. Do not infer call identity from Android event timestamps. Use the provider's call ID and verified target-account mapping.
