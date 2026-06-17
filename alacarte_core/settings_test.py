"""
Settings override for CI / automated testing.
Uses SQLite in-memory so no external database is needed.
Disables Gemini API dependency.
"""
from .settings import *  # noqa: F401,F403
import os

# ── Database: SQLite in-memory for fast, isolated tests ──
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# ── Security: Use a fixed secret key for CI ──
SECRET_KEY = 'ci-test-secret-key-not-for-production'

# ── Debug off to simulate closer-to-prod behaviour ──
DEBUG = False
ALLOWED_HOSTS = ['*']

# ── Disable password validators in tests (not relevant) ──
AUTH_PASSWORD_VALIDATORS = []

# ── Dummy Gemini key so imports don't crash ──
os.environ.setdefault('GEMINI_API_KEY', 'fake-key-for-ci')
