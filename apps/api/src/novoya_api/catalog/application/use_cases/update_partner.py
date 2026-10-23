from dataclasses import dataclass, replace
from uuid import UUID

from novoya_api.catalog.application.ports import PartnerRepository
from novoya_api.catalog.domain import (
    ImportedRow,
    Partner,
    PartnerKind,
    PartnerNotFound,
    normalize_place,
)
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class UpdatePartnerCommand:
    partner_id: UUID
    name: str | None = None
    kind: PartnerKind | None = None
    country: str | None = None
    city: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    active: bool | None = None
    hidden: bool | None = None


class UpdatePartner:
    """Patch a partner. Deactivating or hiding it hides its offers from search without
    touching them. An imported partner only changes hidden: DÉTOUR owns the rest (ADR 0014)."""

    def __init__(self, partners: PartnerRepository, uow: UnitOfWork) -> None:
        self._partners = partners
        self._uow = uow

    async def __call__(self, cmd: UpdatePartnerCommand) -> Partner:
        partner = await self._partners.get(cmd.partner_id)
        if partner is None:
            raise PartnerNotFound("no such partner")
        updated = replace(
            partner,
            name=cmd.name.strip() if cmd.name is not None else partner.name,
            kind=cmd.kind if cmd.kind is not None else partner.kind,
            country=normalize_place(cmd.country) if cmd.country is not None else partner.country,
            city=normalize_place(cmd.city) if cmd.city is not None else partner.city,
            contact_email=(
                cmd.contact_email.strip()
                if cmd.contact_email is not None
                else partner.contact_email
            ),
            contact_phone=(
                cmd.contact_phone.strip()
                if cmd.contact_phone is not None
                else partner.contact_phone
            ),
            active=cmd.active if cmd.active is not None else partner.active,
            hidden=cmd.hidden if cmd.hidden is not None else partner.hidden,
        )
        if partner.imported and replace(updated, hidden=partner.hidden) != partner:
            raise ImportedRow(
                "this partner comes from DÉTOUR: change it in DÉTOUR and it arrives with the "
                "next import. Here you can only hide it."
            )
        await self._partners.save(updated)
        await self._uow.commit()
        return updated
