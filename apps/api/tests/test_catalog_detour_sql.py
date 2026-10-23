"""DÉTOUR import into a real PostgreSQL, from a made-up sqlite file.

Needs docker compose db (or the CI service); skipped when Postgres does not answer.
Uses novoya_test, like test_catalog_sql.py, so the development database is never emptied.
"""

import asyncio
import tempfile
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from novoya_api.catalog.application.dto import ImportCounts
from novoya_api.catalog.application.use_cases.get_offer_detail import GetOfferDetail
from novoya_api.catalog.application.use_cases.update_extra import UpdateExtra, UpdateExtraCommand
from novoya_api.catalog.application.use_cases.update_offer import UpdateOffer, UpdateOfferCommand
from novoya_api.catalog.application.use_cases.update_partner import (
    UpdatePartner,
    UpdatePartnerCommand,
)
from novoya_api.catalog.application.use_cases.update_review import (
    UpdateReview,
    UpdateReviewCommand,
)
from novoya_api.catalog.domain import ImportedRow, OfferNotFound
from novoya_api.catalog.infrastructure.db.models import ExtraRow, OfferRow, PartnerRow, ReviewRow
from novoya_api.catalog.infrastructure.db.repositories import (
    SqlExtraRepository,
    SqlOfferRepository,
    SqlPartnerRepository,
    SqlReviewRepository,
)
from novoya_api.catalog.infrastructure.detour.mapping import DetourImportError, detour_id
from novoya_api.catalog.infrastructure.detour.run import LOCK_KEY, DetourImportBusy, import_detour
from novoya_api.catalog.infrastructure.detour.upload import DetourUploadImporter
from novoya_api.catalog.infrastructure.seed.run import seed_catalog
from novoya_api.catalog.public import covered_destinations, get_extras, search_offers, tags_at
from novoya_api.shared.infrastructure.db.session import close_db
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.detour_fixture import (
    CHANIA,
    CHANIA_STAY,
    CHANIA_TRANSFER,
    DetourFile,
    leftover_folders,
    sample_detour,
)
from tests.test_catalog_sql import (
    API_DIR,
    database_url,  # noqa: F401  (fixture)
)

TABLES = "reviews, extras, offers, partners"


@pytest.fixture
async def session(database_url) -> AsyncIterator[AsyncSession]:  # noqa: F811
    # import_detour / public.py use a process-wide engine; pytest-asyncio uses one loop per test.
    await close_db()
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()
    await close_db()


@pytest.fixture
def source(tmp_path) -> Path:
    return sample_detour(tmp_path / "detour.sqlite")


async def counts(session: AsyncSession) -> dict[str, int]:
    return {
        row.__tablename__: await session.scalar(select(func.count()).select_from(row))
        for row in (PartnerRow, OfferRow, ReviewRow, ExtraRow)
    }


async def test_import_reports_and_stores_the_counts(session, source):
    reported = await import_detour(source)

    assert (reported.partners, reported.offers, reported.reviews, reported.extras) == (3, 3, 3, 3)
    assert await counts(session) == {"partners": 3, "offers": 3, "reviews": 3, "extras": 3}


async def test_importing_twice_keeps_the_counts(session, source):
    await import_detour(source)
    first = await counts(session)

    await import_detour(source)

    assert await counts(session) == first


async def test_imported_partners_are_marked_detour_and_have_no_phone(session, source):
    await import_detour(source)

    partner = await session.get(PartnerRow, detour_id("partenaires", "P001"))

    assert partner.source == "detour"
    assert partner.contact_phone is None


async def test_a_changed_row_is_updated(session, source):
    await import_detour(source)
    with DetourFile(source) as detour:
        detour.execute("UPDATE offres SET prix_unitaire_eur = 90 WHERE id = ?", (CHANIA_STAY,))

    await import_detour(source)

    offer = await session.get(OfferRow, detour_id("offres", CHANIA_STAY))
    await session.refresh(offer)
    assert offer.price_eur == 90


async def test_a_review_no_longer_publishable_is_deleted(session, source):
    await import_detour(source)
    with DetourFile(source) as detour:
        detour.execute("UPDATE consentements SET statut = 'retire' WHERE avis_id = 'A001'")

    await import_detour(source)

    assert await session.get(ReviewRow, detour_id("avis", "A001")) is None
    assert await session.get(ReviewRow, detour_id("avis", "A002")) is not None


async def test_an_invalid_row_rolls_back_the_whole_import(session, source):
    await import_detour(source)
    with DetourFile(source) as detour:
        detour.execute("UPDATE offres SET prix_unitaire_eur = 90 WHERE id = ?", (CHANIA_STAY,))
        detour.offer("F099", "P001", CHANIA, capacite=0)

    with pytest.raises(DetourImportError):
        await import_detour(source)

    offer = await session.get(OfferRow, detour_id("offres", CHANIA_STAY))
    await session.refresh(offer)
    assert offer.price_eur == 85
    assert await counts(session) == {"partners": 3, "offers": 3, "reviews": 3, "extras": 3}


async def test_an_invalid_file_writes_nothing(session, source):
    with DetourFile(source) as detour:
        detour.offer("F099", "P001", CHANIA, capacite=0)

    with pytest.raises(DetourImportError):
        await import_detour(source)

    assert await counts(session) == {"partners": 0, "offers": 0, "reviews": 0, "extras": 0}


async def test_a_second_import_stops_while_one_is_running(session, source):
    # The test's session holds the lock, as a running import's transaction would.
    await session.execute(select(func.pg_advisory_lock(LOCK_KEY)))
    try:
        with pytest.raises(DetourImportBusy):
            await import_detour(source)
    finally:
        await session.execute(select(func.pg_advisory_unlock(LOCK_KEY)))

    assert await counts(session) == {"partners": 0, "offers": 0, "reviews": 0, "extras": 0}
    assert (await import_detour(source)).partners == 3  # the lock went with the transaction


async def test_an_uploaded_export_is_imported_and_not_kept(session, source):
    async def chunks():
        data = source.read_bytes()
        for start in range(0, len(data), 4096):
            yield data[start : start + 4096]

    reported = await DetourUploadImporter(max_bytes=10_000_000).import_export(chunks())

    assert reported == ImportCounts(partners=3, offers=3, reviews=3, extras=3)
    assert await counts(session) == {"partners": 3, "offers": 3, "reviews": 3, "extras": 3}
    assert not leftover_folders()


async def test_imported_destinations_with_an_active_partner_are_covered(session, source):
    await import_detour(source)

    covered = await covered_destinations()

    assert ("Greece", "Chania") in covered
    assert ("France", "Saint-Jean de Luz") not in covered  # its only partner is inactive


async def test_seed_refuses_once_detour_data_is_imported(session, source):
    await import_detour(source)

    with pytest.raises(RuntimeError, match="detour"):
        await seed_catalog()


async def test_reviews_at_a_destination_are_newest_first(session, source):
    await import_detour(source)

    reviews = await SqlReviewRepository(session).list_at("Greece", "Chania", 100)

    assert [review.id for review in reviews] == [
        detour_id("avis", "A004"),
        detour_id("avis", "A001"),
    ]
    assert reviews[1].author == "Zélie Q."


async def test_reviews_are_limited(session, source):
    await import_detour(source)

    reviews = await SqlReviewRepository(session).list_at(None, None, 2)

    assert len(reviews) == 2


async def test_only_active_extras_are_listed(session, source):
    await import_detour(source)
    retired = await session.get(ExtraRow, detour_id("preferences", "O002"))
    retired.active = False
    await session.commit()

    extras = await SqlExtraRepository(session).list_active()

    assert {extra.id for extra in extras} == {
        detour_id("preferences", "O001"),
        detour_id("preferences", "O003"),
    }
    assert [
        extra.constraints for extra in extras if extra.id == detour_id("preferences", "O001")
    ] == [("Selon disponibilité", "Demande à l'avance")]


async def test_database_accepts_a_partner_without_a_phone(session):
    session.add(
        PartnerRow(
            id=uuid4(),
            name="No phone",
            kind="hotel",
            country="Greece",
            city="Chania",
            contact_email="nophone@example.com",
            contact_phone=None,
            active=True,
        )
    )
    await session.commit()


async def test_rows_missing_from_a_later_export_are_deactivated_not_deleted(session, source):
    await import_detour(source)
    with DetourFile(source) as detour:
        detour.execute(
            "DELETE FROM offres_mois_disponibles WHERE parent_id = ?", (CHANIA_TRANSFER,)
        )
        detour.execute("DELETE FROM offres WHERE id = ?", (CHANIA_TRANSFER,))
        detour.execute("DELETE FROM partenaires WHERE id = 'P002'")
        detour.execute("DELETE FROM preferences_contraintes WHERE parent_id = 'O003'")
        detour.execute("DELETE FROM preferences WHERE id = 'O003'")

    reported = await import_detour(source)

    assert (reported.partners, reported.offers, reported.extras) == (2, 2, 2)
    transfer = await session.get(
        OfferRow, detour_id("offres", CHANIA_TRANSFER), populate_existing=True
    )
    shuttle = await session.get(
        PartnerRow, detour_id("partenaires", "P002"), populate_existing=True
    )
    guide = await session.get(ExtraRow, detour_id("preferences", "O003"), populate_existing=True)
    assert (transfer.active, shuttle.active, guide.active) == (False, False, False)
    assert (
        await session.get(OfferRow, detour_id("offres", CHANIA_STAY), populate_existing=True)
    ).active is True
    listed = await search_offers("Greece", "Chania", [], 2, date(2027, 3, 1), date(2027, 3, 5))
    assert detour_id("offres", CHANIA_TRANSFER) not in {offer.id for offer in listed}
    assert detour_id("preferences", "O003") not in {
        extra.id for extra in await SqlExtraRepository(session).list_active()
    }


async def test_a_row_back_in_the_export_is_active_again(session, source):
    await import_detour(source)
    with DetourFile(source) as detour:
        detour.execute("DELETE FROM preferences_contraintes WHERE parent_id = 'O003'")
        detour.execute("DELETE FROM preferences WHERE id = 'O003'")
    await import_detour(source)
    with DetourFile(source) as detour:
        detour.preference("O003", tarification="sur_devis")

    await import_detour(source)

    assert (
        await session.get(ExtraRow, detour_id("preferences", "O003"), populate_existing=True)
    ).active is True


async def test_a_hand_added_partner_is_never_deactivated_by_the_import(session, source):
    hand_added = PartnerRow(
        id=uuid4(),
        name="Hand-added hotel",
        kind="hotel",
        country="Italy",
        city="Rome",
        contact_email="rome@example.com",
        contact_phone="+39 000",
        active=True,
    )
    session.add(hand_added)
    await session.commit()

    await import_detour(source)

    assert (await session.get(PartnerRow, hand_added.id, populate_existing=True)).active is True


MARCH_TRIP = (date(2027, 3, 1), date(2027, 3, 5))


async def _hide_offer(session: AsyncSession, detour_offer: str) -> None:
    await UpdateOffer(
        SqlOfferRepository(session), SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session)
    )(UpdateOfferCommand(offer_id=detour_id("offres", detour_offer), hidden=True))


async def test_a_hidden_offer_is_left_out_of_search_coverage_tags_and_its_page(session, source):
    await import_detour(source)
    transfer = detour_id("offres", CHANIA_TRANSFER)

    await _hide_offer(session, CHANIA_TRANSFER)

    listed = await search_offers("Greece", "Chania", [], 2, *MARCH_TRIP)
    assert transfer not in {offer.id for offer in listed}
    with pytest.raises(OfferNotFound):
        await GetOfferDetail(SqlOfferRepository(session))(transfer)
    await _hide_offer(session, CHANIA_STAY)
    assert ("Greece", "Chania") not in await covered_destinations()
    assert await tags_at("Greece", "Chania") == []


async def test_a_hidden_partner_hides_its_offers(session, source):
    await import_detour(source)

    await UpdatePartner(SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session))(
        UpdatePartnerCommand(partner_id=detour_id("partenaires", "P002"), hidden=True)
    )

    listed = await search_offers("Greece", "Chania", [], 2, *MARCH_TRIP)
    assert detour_id("offres", CHANIA_TRANSFER) not in {offer.id for offer in listed}


async def test_a_hidden_extra_is_not_offered(session, source):
    await import_detour(source)
    bag = detour_id("preferences", "O001")

    await UpdateExtra(SqlExtraRepository(session), SqlAlchemyUnitOfWork(session))(
        UpdateExtraCommand(extra_id=bag, hidden=True)
    )

    assert bag not in {extra.id for extra in await SqlExtraRepository(session).list_active()}
    assert await get_extras([bag]) == []
    assert bag in {extra.id for extra in await SqlExtraRepository(session).list_all()}


async def test_a_hidden_review_is_not_listed(session, source):
    await import_detour(source)
    avis = detour_id("avis", "A001")

    await UpdateReview(SqlReviewRepository(session), SqlAlchemyUnitOfWork(session))(
        UpdateReviewCommand(avis, hidden=True)
    )

    listed = await SqlReviewRepository(session).list_at("Greece", "Chania", 100)
    assert avis not in {review.id for review in listed}
    assert avis in {review.id for review in await SqlReviewRepository(session).list_all()}


async def test_a_new_import_keeps_what_novoya_decided(session, source):
    await import_detour(source)
    stay = detour_id("offres", CHANIA_STAY)
    await UpdateOffer(
        SqlOfferRepository(session), SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session)
    )(UpdateOfferCommand(offer_id=stay, featured=True, hidden=True))
    await UpdatePartner(SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session))(
        UpdatePartnerCommand(partner_id=detour_id("partenaires", "P002"), hidden=True)
    )
    await UpdateExtra(SqlExtraRepository(session), SqlAlchemyUnitOfWork(session))(
        UpdateExtraCommand(extra_id=detour_id("preferences", "O001"), hidden=True)
    )
    avis = detour_id("avis", "A001")
    await UpdateReview(SqlReviewRepository(session), SqlAlchemyUnitOfWork(session))(
        UpdateReviewCommand(avis, hidden=True)
    )

    await import_detour(source)

    offer = await session.get(OfferRow, stay, populate_existing=True)
    partner = await session.get(
        PartnerRow, detour_id("partenaires", "P002"), populate_existing=True
    )
    extra = await session.get(ExtraRow, detour_id("preferences", "O001"), populate_existing=True)
    review = await session.get(ReviewRow, avis, populate_existing=True)
    assert (offer.featured, offer.hidden, offer.active) == (True, True, True)
    assert (partner.hidden, partner.active) == (True, True)
    assert (extra.hidden, extra.active) == (True, True)
    assert review.hidden is True


async def test_editing_an_imported_offer_is_refused_and_writes_nothing(session, source):
    await import_detour(source)
    stay = detour_id("offres", CHANIA_STAY)

    with pytest.raises(ImportedRow):
        await UpdateOffer(
            SqlOfferRepository(session),
            SqlPartnerRepository(session),
            SqlAlchemyUnitOfWork(session),
        )(UpdateOfferCommand(offer_id=stay, title="Renamed"))

    await session.rollback()
    offer = await session.get(OfferRow, stay, populate_existing=True)
    assert offer.title == "Chania - nuit en chambre double"


async def test_imported_partners_are_read_as_imported(session, source):
    await import_detour(source)

    partner = await SqlPartnerRepository(session).get(detour_id("partenaires", "P001"))

    assert partner is not None
    assert (partner.imported, partner.hidden) == (True, False)


def test_downgrade_gives_imported_partners_a_placeholder_phone(database_url):  # noqa: F811
    asyncio.run(_import_then_downgrade(database_url))


async def _import_then_downgrade(url: str) -> None:
    await close_db()
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()
    with tempfile.TemporaryDirectory() as folder:
        await import_detour(sample_detour(Path(folder) / "detour.sqlite"))
    await close_db()

    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    await asyncio.to_thread(command.downgrade, config, "b7e4a91c2d08")
    try:
        engine = create_async_engine(url, poolclass=NullPool)
        async with engine.connect() as connection:
            phones = (await connection.execute(text("SELECT contact_phone FROM partners"))).all()
        await engine.dispose()
        assert {phone for (phone,) in phones} == {"-"}
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
