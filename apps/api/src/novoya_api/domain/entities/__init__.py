"""Entities: objects with an identity that lives over time. Plain dataclasses.

Planned:
- user.py: User, Role (client, agent), Locale (en, fr) (#15, #49)
- partner.py: Partner (#17)
- offer.py: Offer, with tags, person limits, availability, no price (#17)
- wish.py: Wish and WishStatus (draft, not_covered, panel_shown, answered, planned) (#23)
- plan.py: Plan, PlanItem and PlanStatus (proposed, requested, negotiating, quoted,
  accepted, rejected), with the allowed status changes (#29, #50, #51)
- quote.py: Quote, with total and validity of 7 days (#52)
"""
