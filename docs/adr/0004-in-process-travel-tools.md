# 0004. Travel tools as in-process functions, not an MCP server

- **Status:** Accepted
- **Date:** 2026-10-16
- **Issue / PR:** #55 (Architecture 0.3), built in #20 (#68)

## Context

The LLM needs to read the partner catalog to know where Novoya can plan a trip and which
offers exist. An MCP server is one way to expose such tools to a model, but the project does
not require MCP, and it would be one more service to run, secure and deploy.

## Decision

The travel tools are plain Python functions in the `planning` module
(`infrastructure/llm/tools.py`), passed to the model with tool calling:

- `covered_destinations()`
- `search_offers(country, city, tags, persons, start_date, end_date)`

The orchestrator (`shared/infrastructure/llm/orchestrator.py`) runs the function the model
asks for and sends the result back. The tools read the catalog only through
`catalog.public`; the model never touches the database.

## Options considered

- **An MCP server:** standard and reusable by other clients, but a separate process with its
  own deployment and authentication, for two read-only functions used by one backend.

## Consequences

- No extra service: the tools run in the API process, inside the request.
- The model chooses the arguments, so each tool checks them and answers a bad call with an
  error the model can act on. Results never carry the partner's name or contact.
- The orchestrator caps the steps, the tool calls (5 per answer, 15 per run) and the time.
- If another client ever needs these tools, wrapping them in an MCP server stays possible:
  they are already plain functions.
