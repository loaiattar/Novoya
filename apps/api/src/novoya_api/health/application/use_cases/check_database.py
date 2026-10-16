from novoya_api.health.application.ports import DatabaseProbe


class CheckDatabase:
    """Tell whether the database answers."""

    def __init__(self, probe: DatabaseProbe) -> None:
        self._probe = probe

    async def __call__(self) -> bool:
        try:
            await self._probe.ping()
        except Exception:
            return False
        return True
