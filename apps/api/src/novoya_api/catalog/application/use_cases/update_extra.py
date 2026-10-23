from dataclasses import dataclass, replace
from uuid import UUID

from novoya_api.catalog.application.ports import ExtraRepository
from novoya_api.catalog.domain import Extra, ExtraNotFound
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class UpdateExtraCommand:
    extra_id: UUID
    hidden: bool


class UpdateExtra:
    """Hide an extra from clients, or show it again. Every extra comes from DÉTOUR, which owns
    the rest of it (ADR 0014); the import never changes hidden."""

    def __init__(self, extras: ExtraRepository, uow: UnitOfWork) -> None:
        self._extras = extras
        self._uow = uow

    async def __call__(self, cmd: UpdateExtraCommand) -> Extra:
        extra = await self._extras.get(cmd.extra_id)
        if extra is None:
            raise ExtraNotFound("no such extra")
        updated = replace(extra, hidden=cmd.hidden)
        await self._extras.save(updated)
        await self._uow.commit()
        return updated
