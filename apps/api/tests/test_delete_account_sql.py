"""DELETE /me against PostgreSQL (#46): after a quoted client deletes their account, no row
points to them any more. Another client's data stays.

Uses the fixtures of test_quoting_repository_sql.py: skipped when Postgres does not answer.
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.accounts.infrastructure.db.models import SessionModel, UserModel
from novoya_api.accounts.presentation.http.dependencies import (
    build_store,
    get_delete_account,
    get_user_data_eraser,
)
from novoya_api.planning.infrastructure.db.models import PlanModel
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.quoting.presentation.http.dependencies import get_send_quote
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.models import WishModel
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_quoting_repository_sql import (  # noqa: F401  (fixtures)
    NOW,
    engine,
    new_session,
    stored,
)
from tests.test_quoting_send_quote_sql import negotiate


async def count(db, model, *where) -> int:
    async with new_session(db) as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_nothing_points_to_a_deleted_client(engine, stored):  # noqa: F811
    await negotiate(engine, stored, Decimal("640.00"))
    async with new_session(engine) as session:
        await get_send_quote(session)(stored.plan_id, stored.agent_id)
    other = uuid4()
    async with new_session(engine) as session:
        session.add(
            SessionModel(
                id=uuid4(),
                user_id=stored.client_id,
                token_hash=uuid4().hex,
                created_at=NOW,
                last_seen_at=NOW,
                idle_expires_at=NOW + timedelta(days=7),
                absolute_expires_at=NOW + timedelta(days=30),
            )
        )
        session.add(UserModel(id=other, email=f"{other}@example.com", created_at=NOW))
        await session.flush()
        await SqlWishRepository(session).add(Wish.create(other, "Another trip", NOW))
        await session.commit()

    async with new_session(engine) as session:
        use_case = get_delete_account(build_store(session), get_user_data_eraser(session))
        await use_case(UserId(stored.client_id))

    client = stored.client_id
    assert await count(engine, UserModel, UserModel.id == client) == 0
    assert await count(engine, SessionModel, SessionModel.user_id == client) == 0
    assert await count(engine, QuoteModel, QuoteModel.client_id == client) == 0
    assert await count(engine, WishModel, WishModel.user_id == client) == 0
    assert await count(engine, PlanModel, PlanModel.id == stored.plan_id) == 0
    assert await count(engine, WishModel, WishModel.user_id == other) == 1
    assert await count(engine, UserModel, UserModel.id == stored.agent_id) == 1
