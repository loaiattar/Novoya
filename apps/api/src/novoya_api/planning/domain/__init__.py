"""Domain: Plan, PlanItem, PlanStatus and the allowed status changes. Pure Python.

Rules: every item points to a real, active offer; only the plan's client asks for a
quote; only the assigned agent sets prices; a plan is quoted only when every kept
item has a price.
"""
