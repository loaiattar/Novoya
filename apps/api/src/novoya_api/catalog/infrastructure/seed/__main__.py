import asyncio

from novoya_api.catalog.infrastructure.seed.run import seed_catalog
from novoya_api.shared.infrastructure.db.session import close_db


async def _run() -> None:
    try:
        await seed_catalog()
    finally:
        await close_db()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
