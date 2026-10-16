"""What other modules may use from planning. Nothing else in planning may be imported.

Planned:
- generate_plan(wish) -> plan id (called by wishes once the panel is answered)
- get_priced_plan(plan_id) -> PricedPlanView (items with negotiated prices, for the quote)
- mark_quoted(plan_id), mark_accepted(plan_id), mark_rejected(plan_id) (called by quoting)
- delete_for_user(user_id)
"""
