"""Ports: interfaces (typing.Protocol) the use cases need. Infrastructure implements them.

Done: health.py (DatabaseProbe).
Planned:
- repositories.py: UserRepository, PartnerRepository, OfferRepository, WishRepository,
  PlanRepository, QuoteRepository
- unit_of_work.py: UnitOfWork (commit, rollback): one use case is one transaction
- llm.py: PanelBuilder, PlanGenerator (implemented with OpenRouter) (#22, #25, #29)
- documents.py: QuoteRenderer (PDF) (#52)
- notifications.py: QuoteNotifier (email) (#53)
- identity.py: IdentityProvider (Google sign-in) (#15)
"""
