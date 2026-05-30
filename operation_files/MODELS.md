# Model catalog + pricing (single source of truth)

The service reads this to (a) populate the model dropdowns and (b) compute the
USD cost of every call. Prices are **USD per 1M tokens**, verified 30 May 2026
from each provider's official pricing page. Keep this file as the only place
prices live — update here when they change.

Providers: **OpenAI, xAI, Anthropic.** (No Gemini, no Groq.)

## Conversation models (latency matters — pick fast + cheap)

| id | provider | model | input $/M | output $/M | notes |
|---|---|---|---|---|---|
| `xai-grok-4.3` | xai | grok-4.3 | 1.25 | 2.50 | cached input 0.20; 1M ctx; good cheap default |
| `xai-grok-build` | xai | grok-build-0.1 | 1.00 | 2.00 | cheapest xAI, 256k ctx |
| `openai-gpt-5.4-mini` | openai | gpt-5.4-mini | 0.375 | 2.25 | cheap, fast |
| `openai-gpt-5.4-nano` | openai | gpt-5.4-nano | 0.10 | 0.625 | cheapest OpenAI |
| `anthropic-haiku-4.5` | anthropic | claude-haiku-4-5 | 1.00 | 5.00 | strong instruction-following |

## Extraction models (JSON quality matters — accuracy over speed)

| id | provider | model | input $/M | output $/M | notes |
|---|---|---|---|---|---|
| `openai-gpt-5.4-mini` | openai | gpt-5.4-mini | 0.375 | 2.25 | reliable structured JSON, cheap |
| `openai-gpt-5.4` | openai | gpt-5.4 | 1.25 | 7.50 | higher quality if mini misses |
| `anthropic-haiku-4.5` | anthropic | claude-haiku-4-5 | 1.00 | 5.00 | good cheap extractor |
| `anthropic-sonnet-4.6` | anthropic | claude-sonnet-4-6 | 3.00 | 15.00 | best quality, pricier |
| `xai-grok-4.3` | xai | grok-4.3 | 1.25 | 2.50 | has structured outputs |

> Prices above are the *short-context / standard* tiers. OpenAI has a higher
> long-context tier and Anthropic has cache read/write multipliers; the cost
> tracker should store the rate it actually used per call, not assume.

## Machine-readable (the service loads this)
```json
{
  "providers": {
    "openai":    { "key_env": "OPENAI_API_KEY",    "api": "openai-compatible", "base_url": "https://api.openai.com/v1" },
    "xai":       { "key_env": "XAI_API_KEY",        "api": "openai-compatible", "base_url": "https://api.x.ai/v1" },
    "anthropic": { "key_env": "ANTHROPIC_API_KEY",  "api": "anthropic-native" }
  },
  "models": {
    "xai-grok-4.3":          { "provider": "xai",       "model": "grok-4.3",        "in": 1.25, "out": 2.50, "roles": ["convo","extract"] },
    "xai-grok-build":        { "provider": "xai",       "model": "grok-build-0.1",  "in": 1.00, "out": 2.00, "roles": ["convo"] },
    "openai-gpt-5.4-mini":   { "provider": "openai",    "model": "gpt-5.4-mini",    "in": 0.375,"out": 2.25, "roles": ["convo","extract"] },
    "openai-gpt-5.4-nano":   { "provider": "openai",    "model": "gpt-5.4-nano",    "in": 0.10, "out": 0.625,"roles": ["convo"] },
    "openai-gpt-5.4":        { "provider": "openai",    "model": "gpt-5.4",         "in": 1.25, "out": 7.50, "roles": ["extract"] },
    "anthropic-haiku-4.5":   { "provider": "anthropic", "model": "claude-haiku-4-5","in": 1.00, "out": 5.00, "roles": ["convo","extract"] },
    "anthropic-sonnet-4.6":  { "provider": "anthropic", "model": "claude-sonnet-4-6","in": 3.00,"out": 15.00,"roles": ["extract"] }
  },
  "units": "USD per 1M tokens",
  "verified": "2026-05-30"
}
```

## Non-LLM costs to also track (so a session's total is real)
- **Deepgram STT** (Nova-3) and **TTS** (Aura) — per-minute / per-character. Pull
  from your Deepgram dashboard and add to the catalog once the key is set.
- **LiveKit** — free tier covers testing; track minutes if you scale.
- xAI also offers its own STT/TTS/realtime voice if you ever want to drop Deepgram
  (STT $0.10/hr, TTS $15/1M chars, realtime $0.05/min) — worth a later look.

## Env scheme (matches your .env)

Two layers: **role → provider**, then **provider → model**.

```dotenv
# Role → provider  (which provider drives each role)
CONVO_PROVIDER=xai          # openai | xai | anthropic
EXTRACT_PROVIDER=openai     # openai | xai | anthropic

# Provider → model  (DEFAULT is used unless the matching *_MODEL override is set)
XAI_MODEL_DEFAULT=grok-4.3
OPENAI_MODEL_DEFAULT=gpt-5.4-nano
ANTHROPIC_MODEL_DEFAULT=claude-haiku-4-5
# XAI_MODEL=            # optional explicit override
# OPENAI_MODEL=
# ANTHROPIC_MODEL=

# Optional role-specific model override (wins over the provider default)
# CONVO_MODEL=
# EXTRACT_MODEL=

# Keys (a provider is only selectable if its key is present)
OPENAI_API_KEY=sk-proj-...
XAI_API_KEY=xai-...
# ANTHROPIC_API_KEY=    # add to enable Anthropic in the dropdown
```

**Model resolution for a role** (e.g. conversation):
1. `CONVO_MODEL` if set, else
2. `<CONVO_PROVIDER>_MODEL` if set (e.g. `XAI_MODEL`), else
3. `<CONVO_PROVIDER>_MODEL_DEFAULT` (e.g. `XAI_MODEL_DEFAULT`).
Same for extraction with `EXTRACT_*`.

**Cost lookup:** prices are keyed by `(provider, model)` in the table above —
the resolved provider+model for each call indexes its input/output rate.

## Currently active with your keys
- Selectable now: **OpenAI, xAI** (Anthropic needs `ANTHROPIC_API_KEY`).
- With your current values: conversation = xai `grok-4.3`, extraction = openai
  `gpt-5.4-nano` (you'd need to add `CONVO_PROVIDER`/`EXTRACT_PROVIDER`).

## Note on extraction quality
`gpt-5.4-nano` is the cheapest OpenAI model but the weakest at structured JSON.
For the extraction role, `gpt-5.4-mini` ($0.375/$2.25) or `claude-haiku-4-5` is a
safer pick. Set `EXTRACT_MODEL=gpt-5.4-mini` to keep nano elsewhere but use mini
for extraction. A/B both from the test page and let cost+quality decide.
