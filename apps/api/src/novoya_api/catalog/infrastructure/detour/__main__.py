"""uv run python -m novoya_api.catalog.infrastructure.detour --source path/to/detour.sqlite

Prints counts only. An error names the DÉTOUR table and id, never a name or an email."""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from novoya_api.catalog.infrastructure.detour.mapping import DetourImportError
from novoya_api.catalog.infrastructure.detour.run import ImportCounts, import_detour
from novoya_api.shared.infrastructure.db.session import close_db


async def _run(source: Path) -> ImportCounts:
    try:
        return await import_detour(source)
    finally:
        await close_db()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="novoya_api.catalog.infrastructure.detour")
    parser.add_argument("--source", required=True, type=Path, help="the DÉTOUR sqlite file")
    args = parser.parse_args(argv)
    source: Path = args.source

    if not source.is_file():
        print(f"error: no DÉTOUR file at {source}", file=sys.stderr)
        return 1
    try:
        counts = asyncio.run(_run(source))
    except DetourImportError as error:
        print(f"error: nothing imported: {error}", file=sys.stderr)
        return 1
    except SQLAlchemyError as error:  # the engine hides the values; the class name is enough
        print(f"error: nothing imported: database {type(error).__name__}", file=sys.stderr)
        return 1
    print(
        f"imported {counts.partners} partners, {counts.offers} offers,"
        f" {counts.reviews} reviews, {counts.extras} extras"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
