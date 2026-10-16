"""The LLM side: OpenRouter client and the tool-calling orchestrator (#22).

Planned:
- client.py: AsyncOpenAI pointed at https://openrouter.ai/api/v1, model from NOVOYA_LLM_MODEL
- orchestrator.py: send messages and tool definitions, run the tool the model asks for,
  loop until done
- structured.py: validate the model's JSON with Pydantic, retry once, then raise
- tools/: the travel tools the model can call
- prompts/: system prompts, one text file per task
"""
