# Physical-phone acceptance checklist

All cases below remain NOT RUN until a tester records device model, Android version, SIM/carrier, date, actual result, and pass/fail. Emulator or JVM tests cannot validate Airtel forwarding.

| Case | Expected |
|---|---|
| Screening role declined | App stays usable; indicates role not enabled |
| Contacts permission denied/revoked | Unable to check; never labels permission failure as unsaved |
| Saved caller with permission | SAVED with name; rings |
| Unsaved caller; default settings | NOT_SAVED; rings |
| Unsaved caller; both switches enabled | SILENCE response; no programmatic rejection |
| Rules off; silence switch still on | ALLOW response |
| Same Indian mobile as 10 digits / +91 / 0091 / leading 0 | Same saved-contact result |
| International number | Country code preserved; no last-ten-digit comparison |
| Withheld caller ID | May not be delivered by Android; must not crash or invent a number |
| Slow/failing contact provider | Allow fallback; no remote API dependency |
| Locked screen/app not foreground | Role service receives eligible calls and records events |
| Airplane mode / no data | Local lookup works; no claim that incoming SIM calls arrive without service |
| Contacts edited/deleted | Next lookup queries current provider data |
| Repeated calls / rotation | No crashes or duplicate responses |
| Delete history | No local events shown after relaunch |
| Unanswered Airtel call with forwarding configured separately | Provider receives it; verify original caller and target account |
| Declined/busy call | Record actual carrier behavior; do not assume rejection forwards |
| App rules disabled or app uninstalled | Verify forwarding separately; app cannot certify forwarding is off |

Use consenting testers and ordinary test calls. The app does not place calls or alter forwarding settings. No real contact data should be included in shared bug reports.
