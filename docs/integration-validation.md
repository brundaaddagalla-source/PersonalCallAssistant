# Integration validation — 11 October 2026

Base: shakeera 9504ab7 (includes brunda backend ce82f31). Main contained only placeholders.

## Checks performed
- Android debug APK: build successful (JDK 17, Gradle 9.3.1, Android Gradle Plugin 9.1.0, SDK 36).
- Android unit tests: 8 passed, including caller mapping to both server contracts.
- Android lint: 0 errors; remaining warnings are diagnostic-text localization and newer dependency versions.
- Decision backend: 34 tests passed, including synthetic Android caller contract validation.
- Voice engine: 50 tests passed, including Android caller context through the voice-to-decision adapter.
- Python suites run in separate processes with Python 3.14. Speech tests use mocks; no speech model download, live AI provider, or external call was tested.

## Not tested / remaining integration work
- Physical phone UI, incoming SIM screening, deadline behavior under device load, and Airtel forwarding.
- Provider caller-ID preservation, target account identification, live media, notifications, contact syncing, and call takeover.
- Authentication and account-scoped authorization before making prototype services public.
- Existing backend number-rule matching uses a nine-digit suffix; it should be reviewed for the India/multi-country use case before production. This change preserves backend behavior.

The Android screen only previews compatible payloads. It does not claim to send a live SIM conversation to the backend. Physical tests are listed in android-app/TEST-PLAN.md.
