"""LLM adapters, with OpenRouter through the OpenAI SDK (#22).

Planned:
- client.py: AsyncOpenAI pointed at https://openrouter.ai/api/v1, model from NOVOYA_LLM_MODEL
- orchestrator.py: the tool-calling loop
- panel_builder.py, plan_generator.py: implement the PanelBuilder and PlanGenerator ports
- tools/: travel tools the model can call, backed by OfferRepository (#20)
- prompts/: system prompts, one text file per task
"""
