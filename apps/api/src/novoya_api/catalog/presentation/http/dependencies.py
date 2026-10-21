"""Composition root of the catalog module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.application.use_cases.create_offer import CreateOffer
from novoya_api.catalog.application.use_cases.create_partner import CreatePartner
from novoya_api.catalog.application.use_cases.get_offer_detail import GetOfferDetail
from novoya_api.catalog.application.use_cases.list_all_extras import ListAllExtras
from novoya_api.catalog.application.use_cases.list_destinations import ListDestinations
from novoya_api.catalog.application.use_cases.list_extras import ListExtras
from novoya_api.catalog.application.use_cases.list_offers import ListOffers
from novoya_api.catalog.application.use_cases.list_partners import ListPartners
from novoya_api.catalog.application.use_cases.list_reviews import ListReviews
from novoya_api.catalog.application.use_cases.update_extra import UpdateExtra
from novoya_api.catalog.application.use_cases.update_offer import UpdateOffer
from novoya_api.catalog.application.use_cases.update_partner import UpdatePartner
from novoya_api.catalog.infrastructure.db.repositories import (
    SqlExtraRepository,
    SqlOfferRepository,
    SqlPartnerRepository,
    SqlReviewRepository,
)
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def get_list_destinations(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListDestinations:
    return ListDestinations(SqlOfferRepository(session))


def get_list_partners(session: Annotated[AsyncSession, Depends(get_session)]) -> ListPartners:
    return ListPartners(SqlPartnerRepository(session))


def get_create_partner(session: Annotated[AsyncSession, Depends(get_session)]) -> CreatePartner:
    return CreatePartner(SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session))


def get_update_partner(session: Annotated[AsyncSession, Depends(get_session)]) -> UpdatePartner:
    return UpdatePartner(SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session))


def get_list_offers(session: Annotated[AsyncSession, Depends(get_session)]) -> ListOffers:
    return ListOffers(SqlOfferRepository(session))


def get_create_offer(session: Annotated[AsyncSession, Depends(get_session)]) -> CreateOffer:
    return CreateOffer(
        SqlOfferRepository(session),
        SqlPartnerRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_update_offer(session: Annotated[AsyncSession, Depends(get_session)]) -> UpdateOffer:
    return UpdateOffer(
        SqlOfferRepository(session), SqlPartnerRepository(session), SqlAlchemyUnitOfWork(session)
    )


def get_get_offer_detail(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetOfferDetail:
    return GetOfferDetail(SqlOfferRepository(session))


def get_list_reviews(session: Annotated[AsyncSession, Depends(get_session)]) -> ListReviews:
    return ListReviews(SqlReviewRepository(session))


def get_list_extras(session: Annotated[AsyncSession, Depends(get_session)]) -> ListExtras:
    return ListExtras(SqlExtraRepository(session))


def get_list_all_extras(session: Annotated[AsyncSession, Depends(get_session)]) -> ListAllExtras:
    return ListAllExtras(SqlExtraRepository(session))


def get_update_extra(session: Annotated[AsyncSession, Depends(get_session)]) -> UpdateExtra:
    return UpdateExtra(SqlExtraRepository(session), SqlAlchemyUnitOfWork(session))
