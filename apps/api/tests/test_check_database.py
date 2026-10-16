"""Use cases are tested with fake ports: no database, no FastAPI."""

from novoya_api.health.application.use_cases.check_database import CheckDatabase


class FakeProbe:
    def __init__(self, fails: bool) -> None:
        self.fails = fails

    async def ping(self) -> None:
        if self.fails:
            raise ConnectionError("database down")


async def test_database_is_up_when_probe_answers():
    assert await CheckDatabase(FakeProbe(fails=False))() is True


async def test_database_is_down_when_probe_fails():
    assert await CheckDatabase(FakeProbe(fails=True))() is False
