# Test-page model/cost gaps (discovery)

Checked `static/test.html`, `app/main.py`, `app/models.py`, `providers/` against `operation_files/{MODELS,API_CONTRACT}.md`.

1. **GET /llm/options** — MISSING. No such route; no catalog loader. Models in `MODELS.md` are never read by the service.
2. **Per-run `convo`/`extract` {provider,model} on POST /sessions & /simulate** — MISSING. `CreateSessionRequest`/`SimulateRequest` have no model fields; the seam only knows `LLM_PROVIDER=stub|gemini`.
3. **Cost block (`total_usd` + per-role provider/model/tokens/usd) in /simulate & /finalize** — MISSING. `SimulateResponse`/`FinalizeResponse` carry no cost; no token accounting or pricing exists.
4. **`test.html`** — only has a difficulty toggle; no provider/model selectors and no cost readout. Calls POST /sessions, WS /stream, POST /simulate (difficulty+max_turns only).
5. **Note:** `Settings` doesn't even read `OPENAI_API_KEY`/`XAI_API_KEY`/`ANTHROPIC_API_KEY` (all present in `.env`), so key-gating must be added. Pre-existing breakage: tracked `operation_files/PROMPT.md` was deleted in the working tree (restored — needed for the prompts loader and green tests).

Plan: add a `MODELS.md` catalog loader (availability + pricing + validation), thread an optional per-role model choice through the existing stub/gemini seam (chosen catalog model governs labeling + pricing), and emit the cost block. Everything stays offline-green; real catalog clients are added behind an opt-in `LLM_PROVIDER=catalog` so the chosen model can genuinely run when keys are set.
