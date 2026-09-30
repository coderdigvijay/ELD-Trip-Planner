"""Test settings: the real settings evaluated under a production-like env (DEBUG false).

Dummy values only. pytest-django imports settings before any conftest runs, so the env has to
be prepared here. The production guard itself is tested in a subprocess (test_settings_guard.py).
"""

import os

os.environ["ELD_SKIP_DOTENV"] = "1"  # hermetic: never read backend/.env
os.environ.setdefault("DJANGO_DEBUG", "false")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ORS_API_KEY", "test-ors-key")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
os.environ.setdefault("NUM_PROXIES", "1")

from config.settings import *  # noqa: E402, F403
