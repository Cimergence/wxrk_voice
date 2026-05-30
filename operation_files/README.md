# voice-capture-agent (planning folder)

Drop this folder at the **root of your repo**. It is the spec + prompts +
build goal for a standalone, swappable voice interview service. The service it
describes deep-dives ONE work experience by voice and returns structured CV
data for the WXRK builder.

## Files
- `GOAL.md` — branch command + the `/goal` to paste into Claude Code.
- `PRD.md` — what to build and what "done" means.
- `API_CONTRACT.md` — the HTTP/WS surface the backend calls.
- `PROMPT.md` — the live interview prompt + the extraction prompt.

## How to use
1. Commit this folder.
2. Run the branch command from `GOAL.md`.
3. Paste the `/goal` block into Claude Code. It builds the service into this
   same folder, in checkpointed phases.
4. Test instantly at `http://localhost:8080/test` — no backend changes needed.
5. Later, add the frontend `/voice-capture-test` page that embeds the same
   endpoints (separate, small task).

## The principle
The backend never knows which model, STT, or TTS is running. It only knows the
contract in `API_CONTRACT.md`. Swap tech by changing one env var.
