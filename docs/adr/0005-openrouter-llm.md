# 0005. OpenRouter as the LLM provider

- **Status:** Accepted
- **Date:** 2026-10-16
- **Issue / PR:** #55 (Architecture 0.3), built in #22 (#65)

## Context

The school asks for a model served through OpenRouter. The team has no paid model budget,
and free models on OpenRouter come and go, hit rate limits, and do not all follow a JSON
schema or support tool calling equally well.

## Decision

The backend calls OpenRouter with the official `openai` Python SDK, pointed at
`https://openrouter.ai/api/v1`. The model is a setting, not code:

- `NOVOYA_LLM_MODEL`: the main model. It must support tool calling.
- `NOVOYA_LLM_FALLBACK_MODELS`: a JSON list of models tried in order when a model fails or
  answers empty.
- `NOVOYA_OPENROUTER_API_KEY`: stays on the server, in the local `.env`, never in git or
  the browser.

Every structured answer is checked with Pydantic, retried once, then the caller falls back
(for example to matching names instead of reading the wish).

## Consequences

- Switching models is a change of setting. Today the chain is NVIDIA Nemotron 3 Ultra, then
  Nemotron 3 Super, Xing 4.0 and Gemma 4 (free models).
- Free models only work with OpenRouter's privacy setting that allows them, and some
  providers may keep prompts. Wish text goes to them, so the privacy page (#45) must say so.
- Each feature needs a fallback that works without the model, since free models can fail.
- Tests use a fake client; CI never calls OpenRouter.
