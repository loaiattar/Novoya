"""Clean Architecture dependency rule: source code dependencies only point inward.

    presentation  ->  application  ->  domain
    infrastructure ->  application  ->  domain

The domain and the use cases never import frameworks, SDKs or outer layers.
Only the composition root (main.py and presentation/http/dependencies.py) may wire
infrastructure into the presentation layer.
"""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parent.parent / "src" / "novoya_api"

FRAMEWORKS = {
    "alembic",
    "asyncpg",
    "fastapi",
    "httpx",
    "jinja2",
    "openai",
    "pydantic",
    "pydantic_settings",
    "sqlalchemy",
    "starlette",
    "uvicorn",
    "weasyprint",
}
COMPOSITION_ROOT = {"main.py", "presentation/http/dependencies.py"}


def imports_of(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def modules_in(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


def violations(layer: str, allowed_inner: tuple[str, ...], forbid_frameworks: bool) -> list[str]:
    found = []
    for path in modules_in(layer):
        relative = path.relative_to(PACKAGE).as_posix()
        for name in imports_of(path):
            top = name.split(".")[0]
            if top == "novoya_api" and not name.startswith(allowed_inner):
                found.append(f"{relative} imports {name}")
            elif forbid_frameworks and top in FRAMEWORKS:
                found.append(f"{relative} imports framework {name}")
    return found


@pytest.mark.parametrize(
    ("layer", "allowed_inner"),
    [
        ("domain", ("novoya_api.domain",)),
        ("application", ("novoya_api.domain", "novoya_api.application")),
    ],
)
def test_inner_layers_depend_on_nothing_outside(layer, allowed_inner):
    assert violations(layer, allowed_inner, forbid_frameworks=True) == []


def test_infrastructure_does_not_depend_on_presentation():
    found = [
        f"{path.relative_to(PACKAGE).as_posix()} imports {name}"
        for path in modules_in("infrastructure")
        for name in imports_of(path)
        if name.startswith("novoya_api.presentation")
    ]
    assert found == []


def test_only_the_composition_root_wires_infrastructure_into_presentation():
    found = []
    for path in modules_in("presentation"):
        relative = path.relative_to(PACKAGE).as_posix()
        if relative in COMPOSITION_ROOT:
            continue
        found += [
            f"{relative} imports {name}"
            for name in imports_of(path)
            if name.startswith("novoya_api.infrastructure")
        ]
    assert found == []


def test_the_rule_catches_a_violation(tmp_path, monkeypatch):
    bad = tmp_path / "domain"
    bad.mkdir()
    (bad / "leak.py").write_text("from sqlalchemy import select\n")
    monkeypatch.setattr(sys.modules[__name__], "PACKAGE", tmp_path)
    assert violations("domain", ("novoya_api.domain",), forbid_frameworks=True) == [
        "domain/leak.py imports framework sqlalchemy"
    ]
