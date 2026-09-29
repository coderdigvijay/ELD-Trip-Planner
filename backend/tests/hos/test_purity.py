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


NONDETERMINISTIC = {"random", "secrets", "time", "datetime", "uuid", "os", "socket", "subprocess", "logging"}
ORACLE_ALLOWED_HOS_IMPORTS = {"hos.models"}


def test_hos_reads_no_clock_randomness_or_environment():
    """Same input, same output, byte for byte: no clock, no randomness, no I/O (HOS_ENGINE_SPEC intro)."""
    for path in HOS_DIR.rglob("*.py"):
        assert not imported_roots(path) & NONDETERMINISTIC, f"{path.name} imports a nondeterministic module"


def test_hos_imports_without_django_loaded():
    import subprocess
    import sys

    code = (
        "import sys, hos; assert 'django' not in sys.modules, sorted(m for m in sys.modules if 'django' in m)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=HOS_DIR.parent, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr


def test_public_api_is_plan_and_the_data_model():
    import hos

    for name in ("plan", "TripInput", "Leg", "PlanResult", "DutyEvent", "DaySheet", "HosInputError"):
        assert name in hos.__all__ and hasattr(hos, name)


def test_audit_oracle_never_imports_the_simulator():
    """The oracle must stay independent: hos.models is the only engine module it may import."""
    tree = ast.parse((Path(__file__).parent / "audit.py").read_text())
    engine_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "hos":
            engine_imports.add(node.module)
        elif isinstance(node, ast.Import):
            engine_imports |= {a.name for a in node.names if a.name.split(".")[0] == "hos"}
    assert engine_imports <= ORACLE_ALLOWED_HOS_IMPORTS, engine_imports
