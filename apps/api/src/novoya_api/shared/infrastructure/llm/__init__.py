"""The LLM client, shared by the modules that need one (wishes, planning) (#22).

Planned:
- client.py: AsyncOpenAI pointed at https://openrouter.ai/api/v1, model from NOVOYA_LLM_MODEL
- orchestrator.py: the tool-calling loop, with a maximum number of steps
- structured.py: validate the model's JSON with Pydantic, retry once, then raise
Each module writes its own prompts and tools in its infrastructure/llm/.
"""
