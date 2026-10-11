# AI Decision API: Integration Contract

Base URL (dev): `http://<backend-host>:8000`. Interactive schema at `/docs`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/v1/classify` | Intent + risk + identification only |
| POST | `/v1/decide` | Full decision for the next step of the call |

## Call loop (Member 4, voice engine)

1. A forwarded call arrives at the phone-service provider. The provider identifies the account and call. Member 2 supplies a contact-context mapping when available; permission failures are not unknown-contact matches. See `member2-integration.md`.
2. Call `/v1/decide` with an empty transcript. The first response is a greeting that discloses the AI and asks who is calling.
3. Speak `speak` with TTS. Run STT on the caller's reply and append `{"speaker":"caller","text":...}`. Also append the agent's line as `{"speaker":"agent","text":...}`.
4. Call `/v1/decide` again with the **full transcript so far**.
5. Act on `action`:
   - `ask_clarification`: speak and keep listening.
   - `transfer`: request escalation through Member 4's provider bridge and the Android notification/voice client. `CallScreeningService` cannot transfer the forwarded call or inject audio. Speak `speak` while holding only when the provider supports this flow.
   - `handle` / `take_message`: speak `speak`, then end the call if `end_call` is true. Save `caller_message`.
   - `block`: speak `speak`, then end the call.
6. Show `notification` (title, body, priority) in the app and store the decision in call history.

Send at most one request per finished caller utterance. Typical latency is a few milliseconds for the rule engine; with `USE_LLM=true` allow up to `LLM_TIMEOUT_S`.

## `POST /v1/decide`

Request:

```json
{
  "call_id": "c1",
  "received_at": "2026-10-12T10:00:00+04:00",
  "caller": {
    "number": "+971501111111",
    "is_known_contact": true,
    "contact_name": "Sam",
    "contact_group": "friend",
    "number_withheld": false
  },
  "transcript": [
    {"speaker": "agent",  "text": "Hello, this is the AI assistant for Alex..."},
    {"speaker": "caller", "text": "Can we talk about the project deadline"}
  ],
  "preferences": {
    "user_name": "Alex",
    "do_not_disturb": false,
    "max_clarification_turns": 3,
    "rules": [
      {
        "id": "work-hours",
        "name": "Colleagues during work hours",
        "priority": 10,
        "enabled": true,
        "action": "transfer",
        "instruction": null,
        "match": {
          "contact_groups": ["work"],
          "time_start": "09:00",
          "time_end": "18:00",
          "days": [0, 1, 2, 3, 4]
        }
      }
    ]
  }
}
```

`contact_group`: `none | vip | family | friend | work | other`.

Rule `match` fields (all optional, ANDed): `contact_groups`, `numbers`, `contact_names`, `intents`, `known_callers_only`, `unknown_callers_only`, `min_risk_score`, `time_start`/`time_end` (HH:MM, may wrap past midnight), `days` (0=Mon..6=Sun). Lower `priority` number is evaluated first. Rule `action`: `handle | transfer | take_message | block`. `instruction` is trusted text the agent says to the caller.

Response:

```json
{
  "schema_version": "1.0",
  "call_id": "c1",
  "action": "transfer",
  "speak": "Thanks, Sam. Let me check whether Alex is available. Please hold.",
  "end_call": false,
  "intent": {"intent": "work", "confidence": 0.6, "source": "rules"},
  "risk": {"label": "low_risk", "score": 0, "confidence": 0.5, "signals": ["..."], "uncertain": false},
  "identification": {
    "matched_contact": "Sam", "source": "contacts", "verified": false,
    "statement": "Number matches saved contact 'Sam'. Caller ID can be spoofed, so this is not independently verified."
  },
  "reasons": ["Known contact calling about a work matter."],
  "matched_rule_id": null,
  "caution": false,
  "caller_summary": "Sam: work call, risk low risk (0/100).",
  "caller_message": "Can we talk about the project deadline",
  "notification": {"title": "Sam needs you", "body": "...", "priority": "normal"}
}
```

Enums:

- `action`: `ask_clarification | handle | transfer | take_message | block`
- `risk.label`: `unassessed | low_risk | unwanted | suspicious | fraud`
- `intent.intent`: `emergency | delivery | appointment | bank_finance | sales_marketing | survey | tech_support | government_legal | prize_offer | personal | work | robocall | unknown`
- `notification.priority`: `low | normal | high`

`caution: true` means the app should show a warning (unverified or possibly spoofed caller; do not share personal details).

## For Member 1 (Android UI)

Serialise the user's settings into `preferences` (see above) on every request. Show `reasons` and `risk.signals` in call history so decisions are explainable, and show `notification` as the alert. Invalid rules return HTTP 422.

## For Member 2 (telephony)

Use `CallerContext.decisionCaller()` after a conclusive local lookup. `CallerContext.voiceSession()` maps to Member 4's session API. Inconclusive lookups return no payload; the current boolean-only API cannot express them safely. Contact groups are `none` until explicitly assigned by the user. `transfer` is an escalation request for the provider/voice integration, not an Android screening action. The backend never places calls itself.

## Known limitations

- Intent and risk are keyword/regex-based (English only). Optional LLM refinement helps with paraphrases, but accuracy on accents or noisy STT output depends on Member 4's transcripts.
- Scoring weights are hand-tuned; tune them in `app/services/risk.py` after real call testing.
- Caller identification is self-reported or from contacts; it is never marked verified.
