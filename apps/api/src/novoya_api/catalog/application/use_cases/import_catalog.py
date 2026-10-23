from collections.abc import AsyncIterable

from novoya_api.catalog.application.dto import ImportCounts
from novoya_api.catalog.application.ports import CatalogImporter


class ImportCatalog:
    """An admin imports a new DÉTOUR export from the back office (#132), with the same code as
    the command line. The file holds partner contacts and reviews: it is read once and never
    kept (ADR 0003, 0014). One import at a time."""

    def __init__(self, importer: CatalogImporter) -> None:
        self._importer = importer

    async def __call__(self, chunks: AsyncIterable[bytes]) -> ImportCounts:
        return await self._importer.import_export(chunks)
