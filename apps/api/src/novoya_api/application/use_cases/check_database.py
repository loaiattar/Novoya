from novoya_api.application.ports.health import DatabaseProbe


class CheckDatabase:
    """Tell whether the database answers. The smallest example of a use case with a port."""

    def __init__(self, probe: DatabaseProbe) -> None:
        self._probe = probe

    async def __call__(self) -> bool:
        try:
            await self._probe.ping()
        except Exception:
            return False
        return True
