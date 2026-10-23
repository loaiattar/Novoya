"""A DÉTOUR export uploaded from the back office (#132), imported with import_detour.

The file holds partner contacts and reviews (ADR 0003, 0014), so it is never kept: it goes
to a folder only this process can read, under a name the server picks (the client's file
name is never used), is imported, and the folder is deleted, whatever happened. Render wipes
the disk on each deploy anyway (ADR 0013): nothing depends on the file staying.
"""

import tempfile
from collections.abc import AsyncIterable
from pathlib import Path

from novoya_api.catalog.application.dto import ImportCounts
from novoya_api.catalog.domain import (
    CatalogImportFailed,
    CatalogImportRunning,
    DetourExportTooLarge,
    NotADetourExport,
)
from novoya_api.catalog.infrastructure.detour.mapping import DetourImportError
from novoya_api.catalog.infrastructure.detour.run import DetourImportBusy, import_detour

# The first 16 bytes of every sqlite database file.
SQLITE_HEADER = b"SQLite format 3\x00"


class DetourUploadImporter:
    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def import_export(self, chunks: AsyncIterable[bytes]) -> ImportCounts:
        # TemporaryDirectory is mode 0700 and also takes any file sqlite would add next to it.
        with tempfile.TemporaryDirectory(prefix="novoya-detour-") as folder:
            path = Path(folder) / "detour.sqlite"
            await self._write(chunks, path)
            try:
                return await import_detour(path)
            except DetourImportError as error:  # names the DÉTOUR table and id only
                raise CatalogImportFailed(str(error)) from None
            except DetourImportBusy:
                raise CatalogImportRunning("another DÉTOUR import is running") from None

    async def _write(self, chunks: AsyncIterable[bytes], path: Path) -> None:
        """Writes the upload, stopping as soon as it passes the limit; checks it is sqlite."""
        size = 0
        with path.open("xb") as file:
            async for chunk in chunks:
                size += len(chunk)
                if size > self._max_bytes:
                    raise DetourExportTooLarge(
                        f"the export is larger than {self._max_bytes // 1_000_000} MB"
                    )
                file.write(chunk)
        with path.open("rb") as file:
            if file.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                raise NotADetourExport("the file is not a DÉTOUR sqlite export")
