# Claude Code — Goal: multi-model testing in test.html

> Small, focused task. Upgrade the EXISTING wxrk_voice/static/test.html so you can
> run the conversation and extraction with different providers/models and compare
> cost. Stays inside wxrk_voice/ only — no wxrk_frontend, no wxrk_backend.

## 1. Branch
```bash
git checkout -b feat/test-page-model-picker
```

## 2. Goal condition (paste into Claude Code)
```
/goal
Upgrade the existing wxrk_voice/static/test.html so it can run with different LLM providers/models per run and show cost, following operation_files/MODELS.md and operation_files/API_CONTRACT.md. Only files under wxrk_voice/ may change. Do not touch wxrk_frontend/, wxrk_backend/, wxrk_landing_v2/, or the root docker-compose.yml. Do not rebuild the page from scratch — extend what is already there.

First, DISCOVER and report (no code changes yet): read wxrk_voice/static/test.html and the service routes it calls, and check whether these already exist — GET /llm/options (key-gated provider+model list), per-run convo/extract provider+model overrides on POST /sessions and POST /simulate, and a cost block in the /simulate and /finalize responses (per operation_files/API_CONTRACT.md). Write a 8-line summary of what exists vs what is missing to wxrk_voice/docs/test_page_gaps.md. Then commit "checkpoint: documented test-page gaps".

Then, only for whatever the discovery found MISSING, add the minimal support inside wxrk_voice so the page can drive models: GET /llm/options returning only providers whose API key env var is present with their allowed models from MODELS.md; accept optional convo {provider,model} and extract {provider,model} on POST /sessions and POST /simulate, validated against MODELS.md and ignored-with-default when omitted; and include the cost block (total_usd plus per-role provider/model/tokens/usd) in the /simulate and /finalize responses, priced from MODELS.md. Add a focused test that an off-catalog model is rejected and that a chosen model is what actually runs. `pytest wxrk_voice/` exits 0. Then commit "checkpoint: service supports per-run model choice + cost (only gaps filled)".

Then update wxrk_voice/static/test.html: add two labelled selectors — Conversation (provider+model) and Extraction (provider+model) — populated from GET /llm/options so only providers with a key present appear; persist the last choice in memory for the session; send the choices with both the mic Start flow (POST /sessions) and the Simulate (no mic) flow (POST /simulate). Show the model that actually ran and a USD cost readout for the run (total plus the per-role breakdown) once results return. For /simulate also expose the difficulty toggle (easy|hard) already supported by the API. Keep the existing two-column chat (agent vs candidate) and live transcript working unchanged. Match the page's current styling; no new framework or build step — plain HTML/JS as it is now. Then commit "checkpoint: test.html model pickers + cost readout".

Final: from a running service (docker compose -f wxrk_voice/docker-compose.yml up), opening /test shows Conversation and Extraction selectors listing only key-present providers (OpenAI and xAI now; Anthropic appears only if ANTHROPIC_API_KEY is set); a Simulate run with a chosen pair returns a transcript, an extraction, and a non-zero USD cost reflecting the chosen models; changing the selectors and re-running uses the new models; the mic Start flow still works; `pytest wxrk_voice/` exits 0; and `git diff --name-only main` shows only files under wxrk_voice/. Or stop after 30 turns.
```

## 3. Why it's shaped this way
- **Extends, not rebuilds:** the page already works; the goal forbids a rewrite and
  forbids new frameworks, so you keep your current chat UI.
- **Discovery-first:** it documents what already exists before adding anything, so
  it won't duplicate endpoints you've already built — it only fills gaps.
- **Key-gated selectors:** only providers with a key show up, so the page reflects
  reality (OpenAI + xAI today; Anthropic when you add its key).
- **Cost is visible per run:** the whole point — compare quality and price side by
  side as you flip models.
- **Scope-locked** to wxrk_voice via the final git diff; frontend/backend untouched.
- **30-turn cap:** this is one feature, not the full build.

## 4. Run it
1. `/model sonnet-4.6`
2. paste the goal
3. `/agent-browser` to click through /test (pick models, Simulate, check cost)
4. `/model opus-4.8` to fix anything the browser surfaced; re-run the last checkpoint

## 5. Tip
Add `CONVO_PROVIDER=xai`, `EXTRACT_PROVIDER=openai` (and optionally
`EXTRACT_MODEL=gpt-5.4-mini`) to wxrk_voice/.env first, so the page has sensible
defaults before you start flipping selectors.
