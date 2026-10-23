from dataclasses import dataclass
from uuid import uuid4

from novoya_api.catalog.application.ports import PartnerRepository
from novoya_api.catalog.domain import Partner, PartnerKind, normalize_place
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreatePartnerCommand:
    name: str
    kind: PartnerKind
    country: str
    city: str
    contact_email: str
    contact_phone: str | None
    active: bool = True


class CreatePartner:
    def __init__(self, partners: PartnerRepository, uow: UnitOfWork) -> None:
        self._partners = partners
        self._uow = uow

    async def __call__(self, cmd: CreatePartnerCommand) -> Partner:
        partner = Partner(
            id=uuid4(),
            name=cmd.name.strip(),
            kind=cmd.kind,
            country=normalize_place(cmd.country),
            city=normalize_place(cmd.city),
            contact_email=cmd.contact_email.strip(),
            contact_phone=cmd.contact_phone.strip() if cmd.contact_phone else None,
            active=cmd.active,
        )
        await self._partners.add(partner)
        await self._uow.commit()
        return partner
