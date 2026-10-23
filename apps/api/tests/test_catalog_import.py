"""DÉTOUR import from the back office (#132): the upload adapter without a database, and
POST /admin/catalog/import with a signed-in admin. The real import is in
test_catalog_detour_sql.py."""

import asyncio
import tempfile
from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import current_user
from novoya_api.catalog.application.dto import ImportCounts
from novoya_api.catalog.application.use_cases.import_catalog import ImportCatalog
from novoya_api.catalog.domain import (
    CatalogImportFailed,
    CatalogImportRunning,
    DetourExportTooLarge,
    NotADetourExport,
)
from novoya_api.catalog.infrastructure.detour import upload
from novoya_api.catalog.infrastructure.detour.mapping import DetourImportError
from novoya_api.catalog.infrastructure.detour.run import DetourImportBusy
from novoya_api.catalog.infrastructure.detour.upload import SQLITE_HEADER, DetourUploadImporter
from novoya_api.catalog.presentation.http.dependencies import (
    get_detour_max_bytes,
    get_import_catalog,
)
from novoya_api.main import create_app
from novoya_api.shared.domain.value_objects import Locale
from tests.detour_fixture import leftover_folders, sample_detour

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
COUNTS = ImportCounts(partners=3, offers=3, reviews=3, extras=3)
EXPORT = SQLITE_HEADER + b"rest of the database"


async def chunks_of(data: bytes, size: int = 8) -> AsyncIterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]


class FakeImport:
    """Stands in for import_detour: remembers the file it was given, and what was in it."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.path: Path | None = None
        self.data = b""

    async def __call__(self, path: Path) -> ImportCounts:
        self.path = path
        self.data = await asyncio.to_thread(path.read_bytes)
        if self.error is not None:
            raise self.error
        return COUNTS


@pytest.fixture
def fake_import(monkeypatch) -> FakeImport:
    fake = FakeImport()
    monkeypatch.setattr(upload, "import_detour", fake)
    return fake


async def test_the_upload_is_imported_from_a_server_named_file_then_deleted(fake_import):
    counts = await DetourUploadImporter(max_bytes=1000).import_export(chunks_of(EXPORT))

    assert counts == COUNTS
    assert fake_import.data == EXPORT
    assert fake_import.path.name == "detour.sqlite"
    assert fake_import.path.parent.parent == Path(tempfile.gettempdir())
    assert not fake_import.path.parent.exists()


async def test_the_file_is_deleted_when_the_import_fails(fake_import):
    fake_import.error = DetourImportError("offres F099: capacity")

    with pytest.raises(CatalogImportFailed, match="offres F099"):
        await DetourUploadImporter(max_bytes=1000).import_export(chunks_of(EXPORT))

    assert not fake_import.path.parent.exists()


async def test_a_running_import_is_reported(fake_import):
    fake_import.error = DetourImportBusy("another DÉTOUR import is running")

    with pytest.raises(CatalogImportRunning):
        await DetourUploadImporter(max_bytes=1000).import_export(chunks_of(EXPORT))

    assert not fake_import.path.parent.exists()


async def test_an_upload_over_the_limit_stops_before_the_import(fake_import):
    received = []

    async def endless() -> AsyncIterator[bytes]:
        while True:
            received.append(1)
            yield SQLITE_HEADER

    with pytest.raises(DetourExportTooLarge):
        await DetourUploadImporter(max_bytes=100).import_export(endless())

    assert fake_import.path is None
    assert len(received) == 7  # 7 * 16 bytes is the first chunk over 100
    assert not leftover_folders()


@pytest.mark.parametrize("data", [b"", b"PK\x03\x04 a zip file", b"SQLite format 2\x00..."])
async def test_a_file_that_is_not_sqlite_is_refused(fake_import, data):
    with pytest.raises(NotADetourExport):
        await DetourUploadImporter(max_bytes=1000).import_export(chunks_of(data))

    assert fake_import.path is None


async def test_the_made_up_export_passes_the_checks(fake_import, tmp_path):
    export = sample_detour(tmp_path / "anything.bin").read_bytes()

    await DetourUploadImporter(max_bytes=10_000_000).import_export(chunks_of(export, 4096))

    assert fake_import.data == export


# HTTP


class FakeImporter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.received = b""

    async def import_export(self, chunks: AsyncIterable[bytes]) -> ImportCounts:
        async for chunk in chunks:
            self.received += chunk
        if self.error is not None:
            raise self.error
        return COUNTS


def signed_in_as(role: Role) -> CurrentUserView:
    return CurrentUserView(
        user_id=UserId(USER_ID),
        email=Email("admin@example.com"),
        name=None,
        role=role,
        locale=Locale.EN,
        session_id=USER_ID,
    )


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _as(app, role: Role, importer: FakeImporter) -> None:
    app.dependency_overrides[current_user] = lambda: signed_in_as(role)
    app.dependency_overrides[get_import_catalog] = lambda: ImportCatalog(importer)


async def _upload(client: AsyncClient, data: bytes = EXPORT):
    return await client.post(
        "/admin/catalog/import",
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


async def test_an_admin_imports_an_export_and_gets_the_counts(app, client):
    importer = FakeImporter()
    _as(app, Role.ADMIN, importer)

    response = await _upload(client)

    assert response.status_code == 200
    assert response.json() == {"partners": 3, "offers": 3, "reviews": 3, "extras": 3}
    assert importer.received == EXPORT


async def test_the_page_reads_the_limit_from_the_settings(app, client):
    _as(app, Role.ADMIN, FakeImporter())
    app.dependency_overrides[get_detour_max_bytes] = lambda: 5_000_000

    response = await client.get("/admin/catalog/import")

    assert response.status_code == 200
    assert response.json() == {"max_bytes": 5_000_000}


async def test_the_limit_is_the_default_without_a_setting(app, client):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.ADMIN)

    assert (await client.get("/admin/catalog/import")).json() == {"max_bytes": 20_000_000}


async def test_the_import_uses_the_same_limit(monkeypatch):
    monkeypatch.setattr(upload, "import_detour", FakeImport())

    with pytest.raises(DetourExportTooLarge, match="larger than 2 MB"):
        await get_import_catalog(max_bytes=2_000_000)(chunks_of(EXPORT + bytes(2_000_000), 500_000))


async def test_a_super_admin_may_import(app, client):
    _as(app, Role.SUPER_ADMIN, FakeImporter())

    assert (await _upload(client)).status_code == 200


async def test_the_import_needs_a_session(client):
    assert (await _upload(client)).status_code == 401


@pytest.mark.parametrize("role", [Role.CLIENT, Role.AGENT])
async def test_only_admins_may_import(app, client, role):
    importer = FakeImporter()
    _as(app, role, importer)

    response = await _upload(client)

    assert response.status_code == 403
    assert importer.received == b""
    assert (await client.get("/admin/catalog/import")).status_code == 403


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (DetourExportTooLarge("the export is larger than 20 MB"), 413, "detour_export_too_large"),
        (NotADetourExport("not sqlite"), 422, "not_a_detour_export"),
        (CatalogImportFailed("offres F099: unknown partner"), 422, "detour_import_failed"),
        (CatalogImportRunning("another DÉTOUR import is running"), 409, "import_running"),
    ],
)
async def test_import_errors_have_their_status_and_code(app, client, error, status, code):
    _as(app, Role.ADMIN, FakeImporter(error))

    response = await _upload(client)

    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["detail"] == str(error)
