"""Production settings guard. Runs settings in a fresh interpreter so the env is fully controlled."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PROD_ENV = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "x" * 50,
    "ORS_API_KEY": "k",
    "DJANGO_ALLOWED_HOSTS": "api.example.com",
    "NUM_PROXIES": "1",
}


def load_settings(**overrides: str | None) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ["PATH"],
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "ELD_SKIP_DOTENV": "1",  # hermetic: a local backend/.env must not fill in "missing" vars
        **PROD_ENV,
    }
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import config.settings"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_valid_production_env_boots():
    assert load_settings().returncode == 0


@pytest.mark.parametrize("value", [None, "0", "-1", "abc", ""])
def test_production_refuses_missing_or_invalid_num_proxies(value):
    result = load_settings(NUM_PROXIES=value)
    assert result.returncode != 0
    assert "NUM_PROXIES" in result.stderr


@pytest.mark.parametrize("missing", ["DJANGO_SECRET_KEY", "ORS_API_KEY", "DJANGO_ALLOWED_HOSTS"])
def test_production_refuses_missing_required_vars(missing):
    result = load_settings(**{missing: None})
    assert result.returncode != 0
    assert missing in result.stderr


@pytest.mark.parametrize("empty", ["DJANGO_SECRET_KEY", "ORS_API_KEY"])
def test_production_refuses_empty_secrets(empty):
    result = load_settings(**{empty: ""})
    assert result.returncode != 0
    assert empty in result.stderr


def test_debug_true_empty_secret_key_falls_back_to_dev_key():
    result = load_settings(
        DJANGO_DEBUG="true", DJANGO_SECRET_KEY="", NUM_PROXIES=None, DJANGO_ALLOWED_HOSTS=None
    )
    assert result.returncode == 0


def test_debug_true_is_refused_on_render():
    result = load_settings(DJANGO_DEBUG="true", RENDER="true")
    assert result.returncode != 0
    assert "Render" in result.stderr


def test_debug_true_boots_locally_without_secrets():
    result = load_settings(
        DJANGO_DEBUG="true",
        DJANGO_SECRET_KEY=None,
        ORS_API_KEY=None,
        DJANGO_ALLOWED_HOSTS=None,
        NUM_PROXIES=None,
    )
    assert result.returncode == 0
