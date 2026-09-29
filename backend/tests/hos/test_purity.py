"""hos/ is a pure engine: no Django, no other app packages, no I/O libraries."""

import ast
from pathlib import Path

HOS_DIR = Path(__file__).resolve().parents[2] / "hos"
FORBIDDEN = {"django", "rest_framework", "routing", "trips", "config", "httpx", "requests"}


def imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_hos_imports_nothing_forbidden():
    files = list(HOS_DIR.rglob("*.py"))
    assert files, "hos/ has no modules"
    for path in files:
        assert not imported_roots(path) & FORBIDDEN, f"{path.name} imports a forbidden package"
