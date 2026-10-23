"""The API's startup: expired sessions and email links are deleted, and a database that
does not answer does not stop the API from starting."""

from fastapi.testclient import TestClient

from novoya_api import main


def test_startup_deletes_the_expired_sign_ins(monkeypatch):
    calls = []

    async def clean_up() -> None:
        calls.append("cleaned")

    monkeypatch.setattr(main, "clean_up_sign_ins", clean_up)

    with TestClient(main.create_app()) as client:
        assert client.get("/health").status_code == 200

    assert calls == ["cleaned"]


def test_a_database_that_does_not_answer_does_not_stop_the_startup(monkeypatch, caplog):
    def broken_sessionmaker():
        raise ConnectionRefusedError("no database")

    monkeypatch.setattr(main, "get_sessionmaker", broken_sessionmaker)
    # Alembic's fileConfig (run by the migration tests) disables the loggers that exist.
    monkeypatch.setattr(main.logger, "disabled", False)

    with TestClient(main.create_app()) as client:
        assert client.get("/health").status_code == 200

    assert "Deleting expired sessions at startup failed: ConnectionRefusedError" in caplog.text
