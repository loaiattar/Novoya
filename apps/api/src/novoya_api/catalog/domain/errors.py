from novoya_api.shared.domain.errors import Conflict, InvalidInput, NotFound


class InvalidPartner(InvalidInput):
    """A partner field is empty or not a usable contact email."""

    code = "invalid_partner"


class PartnerNotFound(NotFound):
    code = "partner_not_found"


class OfferNotFound(NotFound):
    code = "offer_not_found"


class ExtraNotFound(NotFound):
    code = "extra_not_found"


class ReviewNotFound(NotFound):
    code = "review_not_found"


class ImportedRow(Conflict):
    """The row comes from the DÉTOUR export, which owns its content: the change is made in
    DÉTOUR and arrives with the next import. Novoya only decides featured and hidden."""

    code = "imported_row"
