"""Alembic's history must end in one revision: `alembic upgrade head` fails with two."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_a_single_head():
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1
