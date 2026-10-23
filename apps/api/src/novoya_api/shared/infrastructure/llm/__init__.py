"""The LLM client, shared by the modules that need one (wishes, planning) (#22).

- client.py: AsyncOpenAI pointed at OpenRouter; get_orchestrator() uses NOVOYA_LLM_MODEL,
  then NOVOYA_LLM_FALLBACK_MODELS in order
- orchestrator.py: Tool, and Orchestrator.run(), the tool-calling loop with a maximum
  number of steps
- structured.py: run_structured() validates the model's JSON with Pydantic, retries once,
  then raises LLMError
- errors.py: LLMError, which every adapter catches so its use case can fall back

Each module writes its own prompts and tools in its infrastructure/llm/.
"""
