"""What other modules may use from accounts. Nothing else in accounts may be imported.

Planned:
- current_user, require_agent: FastAPI dependencies for routers of other modules
- get_user(user_id) -> UserView (id, email, name, role, locale), e.g. for the quote email
"""
