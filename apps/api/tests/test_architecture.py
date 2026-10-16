"""Architecture rules, checked on every import of src/novoya_api.

The code is split into modules (accounts, catalog, wishes, planning, quoting, health)
plus a shared kernel. Inside each one, Clean Architecture layers:

    presentation  ->  application  ->  domain
    infrastructure ->  application  ->  domain

1. Layers: dependencies only point inward. The domain and the use cases never import
   a framework, an SDK or an outer layer. Presentation reaches infrastructure only in
   its composition root (presentation/http/dependencies.py).
2. Modules: a module uses another module only through that module's public.py, and
   only from its infrastructure (adapters), its presentation or its own public.py.
3. Shared kernel: it never imports a module.
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

PACKAGE = Path(__file__).parent.parent / "src" / "novoya_api"

LAYERS = ("domain", "application", "infrastructure", "presentation")
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
# What each layer of a module may import from its own module and from shared.
INNER = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "application", "infrastructure"},
    "presentation": {"domain", "application", "presentation"},
}
COMPOSITION_ROOT = "presentation/http/dependencies.py"
TOP_LEVEL = {"main", "config", "openapi"}


@dataclass(frozen=True)
class Source:
    path: Path
    module: str | None  # None for main.py, config.py, openapi.py
    layer: str | None  # one of LAYERS, "public", or None for a package __init__

    @property
    def name(self) -> str:
        return self.path.relative_to(PACKAGE).as_posix()


def classify(path: Path) -> Source:
    parts = path.relative_to(PACKAGE).parts
    if len(parts) == 1:
        return Source(path, None, None)
    module = parts[0]
    if parts[1] == "public.py":
        return Source(path, module, "public")
    return Source(path, module, parts[1] if parts[1] in LAYERS else None)


def imports_of(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def problems(source: Source, name: str) -> str | None:
    parts = name.split(".")
    if parts[0] in FRAMEWORKS and source.layer in ("domain", "application"):
        return "framework in an inner layer"
    if parts[0] != "novoya_api" or len(parts) == 1 or source.module is None:
        return None
    target = parts[1]
    target_layer = parts[2] if len(parts) > 2 else None

    if target in TOP_LEVEL:
        if target == "config" and source.layer in ("infrastructure", "presentation", None):
            return None
        return f"{source.layer or 'package'} imports {target}"

    if source.module == "shared" and target != "shared":
        return "shared kernel imports a module"

    if target != source.module and target != "shared":
        if target_layer != "public":
            return "reaches into another module (use its public.py)"
        if source.layer in ("domain", "application"):
            return "inner layer uses another module (declare a port instead)"
        return None

    if source.layer in (None, "public"):
        return None
    if target_layer not in INNER[source.layer]:
        if (
            source.layer == "presentation"
            and target_layer == "infrastructure"
            and source.name.endswith(COMPOSITION_ROOT)
        ):
            return None
        return f"{source.layer} imports {target_layer}"
    return None


def violations(root: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.py")):
        source = classify(path)
        for name in sorted(imports_of(path)):
            reason = problems(source, name)
            if reason:
                found.append(f"{source.name} imports {name}: {reason}")
    return found


def test_the_code_follows_the_architecture_rules():
    assert violations(PACKAGE) == []


def plant(tmp_path: Path, relative: str, code: str) -> list[str]:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code)
    return violations(tmp_path)


def test_rules_catch_violations(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "PACKAGE", tmp_path)
    cases = {
        "wishes/domain/leak.py": "from sqlalchemy import select\n",
        "wishes/application/a.py": "from novoya_api.wishes.infrastructure.db import x\n",
        "wishes/presentation/http/router.py": "from novoya_api.wishes.infrastructure import y\n",
        "wishes/infrastructure/b.py": "from novoya_api.catalog.domain import Offer\n",
        "wishes/application/c.py": "from novoya_api.catalog.public import search\n",
        "shared/domain/d.py": "from novoya_api.wishes.public import get_wish\n",
        "catalog/domain/e.py": "from novoya_api.config import get_settings\n",
    }
    for relative, code in cases.items():
        assert plant(tmp_path, relative, code), f"not caught: {relative}"
        (tmp_path / relative).unlink()


def test_rules_allow_the_intended_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "PACKAGE", tmp_path)
    allowed = {
        "wishes/infrastructure/catalog.py": "from novoya_api.catalog.public import search\n",
        "wishes/application/u.py": "from novoya_api.shared.domain.errors import NotFound\n",
        "wishes/presentation/http/dependencies.py": (
            "from novoya_api.wishes.infrastructure import a\n"
        ),
    }
    for relative, code in allowed.items():
        assert plant(tmp_path, relative, code) == [], relative
