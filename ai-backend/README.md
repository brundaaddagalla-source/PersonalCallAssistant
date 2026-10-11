# AI Decision Engine (Member 3)

Python + FastAPI service that decides what the Personal Call Agent should do with a call.

For each call turn it:
1. **Classifies intent** (delivery, emergency, sales, bank, work, personal, ...)
2. **Scores spam/fraud risk** (0-100, label, confidence, explainable signals)
3. **Identifies the caller** as far as possible and states plainly when it can't verify
4. **Applies the user's rules** (per contact, group, number, intent, time window, risk)
5. **Returns a structured decision**: `ask_clarification`, `handle`, `transfer`, `take_message` or `block`, plus the text for TTS and a notification for the app UI.

## Run

```bash
cd ai-backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # optional
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: http://localhost:8000/docs

## Test

```bash
pytest
```

## Try it

```bash
curl -s localhost:8000/v1/decide -H 'content-type: application/json' -d '{
  "call_id": "c1",
  "caller": {"number": "+971500000000"},
  "transcript": [{"speaker": "caller", "text": "This is SBI bank, share your OTP immediately or your account will be blocked"}]
}' | python -m json.tool
```

## Design decisions

- **Stateless.** The voice engine (Member 4) sends the full transcript every turn; nothing is stored server-side, and transcripts are never logged.
- **Rules first, LLM optional.** The rule-based engine works offline with no keys. With `USE_LLM=true` a model may refine intent and may only *raise* risk. It never chooses the action, and the transcript is treated as untrusted (prompt-injection safe). Any LLM failure falls back to rules.
- **Safety beats preferences.** An explicit user `block` always wins. A `transfer`/`handle` rule can't push a high-confidence scam through (the override is explained in `reasons`).
- **Uncertainty is explicit.** `risk.confidence`, `risk.uncertain` and `identification.verified=false` are always returned; short or ambiguous calls lead to `ask_clarification` or `take_message`, not guesses.
- **Emergencies ring through**, with a caution flag if risk signals are present. Fake-emergency + money requests are blocked.
- **The agent always discloses it's an AI** on its first turn.
- Caller-ID match with a saved contact is **not** treated as verified (numbers can be spoofed).

## Layout

```
app/
  main.py                  FastAPI routes
  schemas.py               Request/response models (the API contract)
  config.py                Env settings
  services/
    intent.py              Intent + name/org extraction
    risk.py                Spam/fraud signals and scoring
    rules.py               User rule matching (time windows, groups, numbers)
    decision.py            Policy engine + response assembly
    responses.py           What the agent says per action
    llm_classifier.py      Optional LLM refinement
tests/                     pytest suite
```

See `../docs/ai-backend-api.md` for the integration contract with Members 1, 2 and 4.
