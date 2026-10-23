from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from novoya_api.shared.domain.errors import InvalidInput


class InvalidExtra(InvalidInput):
    """The label is empty, or the supplement does not match the pricing."""

    code = "invalid_extra"


class ExtraPricing(StrEnum):
    INCLUDED = "included"  # free with the trip
    SUPPLEMENT = "supplement"  # a fixed amount, known in advance
    ON_QUOTE = "on_quote"  # the agent asks the partner and prices it on the quote


@dataclass(frozen=True)
class Extra:
    """An option a client can add to a plan (a quiet room, an extra bag, a private guide).

    Every extra comes from DÉTOUR, which owns it; hidden is the agent's switch in Novoya,
    which the import never changes. A hidden extra is not offered, like an inactive one."""

    id: UUID
    category: str
    label: str
    description: str
    pricing: ExtraPricing
    supplement_eur: int | None  # only for a supplement, and then more than 0
    unit: str
    constraints: tuple[str, ...]
    active: bool
    hidden: bool = False

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise InvalidExtra("the label is empty")
        if self.pricing is ExtraPricing.SUPPLEMENT:
            if self.supplement_eur is None or self.supplement_eur <= 0:
                raise InvalidExtra("a supplement needs an amount more than 0")
        elif self.supplement_eur is not None:
            raise InvalidExtra("only a supplement has an amount")
