from novoya_api.shared.domain.errors import Conflict, InvalidInput, NotFound, TooLarge


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


class NotADetourExport(InvalidInput):
    """The uploaded file is not a sqlite database, whatever its name says."""

    code = "not_a_detour_export"


class DetourExportTooLarge(TooLarge):
    code = "detour_export_too_large"


class CatalogImportFailed(InvalidInput):
    """The export has a row Novoya cannot take; nothing was written. The message names the
    DÉTOUR table and id only, never a name, an email or a review text."""

    code = "detour_import_failed"


class CatalogImportRunning(Conflict):
    """Another DÉTOUR import, from the back office or the command line, is still running."""

    code = "import_running"
