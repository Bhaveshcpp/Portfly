# Changes in this pass (steps 1–3 of the next-steps plan)

## Bugs fixed
1. User message was sent to the model twice -> history now excludes the current turn.
2. Tool telemetry was placeholder (args `{}`, 0 ms, always ok, tool_ms 0) -> real args, per-call
   duration, blocked/failed outcome, per-model-call timing, llm_calls, token counts.
3. City parsing (`Alibaug, Maharashtra`, city-less `Indiranagar`) -> stored `city` column + resolver.
4. Follow-up context -> recently discussed property ids and the active what-if are injected into the prompt.
5. Attention flags -> sticky error/handoff, auto-clearing clarification, `POST /api/conversations/{id}/resolve`,
   legal/tax/human handoff is now implemented in code, not just described in SOUL.md.
6. Write validation + `parse_inr` + confirm flow (see DECISIONS D-11/D-12).
7. Error path -> run/user message committed before the agent runs, rollback-safe, read-only fallback,
   step-limit detection, tool exceptions contained.
8. What-if -> multiple re-valuations, exclusions by id/location/type, hypothetical additions, exact `delta`,
   unknown ids rejected.

## Also
- Additive DB migration (`ensure_columns`) so an existing `portfly.db` keeps working; delete it if you prefer a clean seed.
- Fallback moved to `agent/fallback.py`; uses the same validated, traced code as the LLM path.
- Desk: p50/p95, model vs tool split, tokens, users table, attention filter, tool arguments, Resolve button.
- Chat: conversation survives refresh; "New chat" button.
- Tests: 7 -> 53 (validation, scripted-LLM runner tests, migration).

## Not done yet (next steps)
Run against the real OpenRouter model (needs a key), measured latency, deployment, README/LATENCY cleanup, desk auth.

---
# Step 4 tooling (real-model testing)

New, in `backend/scripts/` (run from `backend/` with `PYTHONPATH=.`):
- `eval_agent.py`: 17 pass/fail scenarios (totals, exposure, isolation + prompt injection, add / missing info /
  unit slip / negative, update, ambiguous update, what-if with no write, 4-turn conversation chain, honest
  "no appreciation", tax handoff). Asserts on tools used, DB state and numbers, not wording. Resets the DB per case.
  `--model`, `--only`, `-v`, `--base-url/--token`.
- `measure_latency.py`: 8-turn workload x N reps; p50/p95 total, model / tools / other split, model calls,
  tokens, optional cost per turn (`--price-in/--price-out`). Prints a markdown table for docs/LATENCY.md.
- `harness.py`: shared in-process or remote client.

Verified here WITHOUT an API key: 17/17 in fallback mode, 53 unit tests, generated OpenAI tool schemas are valid
and accept money strings ("14 Cr") through the LangChain layer.
NOT verified: any real-model behaviour. Run `eval_agent.py` with OPENROUTER_API_KEY set.

Fixes found while building these: fallback wording on ambiguous updates, negative area parsing in the fallback.
