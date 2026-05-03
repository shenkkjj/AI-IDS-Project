import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    with open(_ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

os.environ.setdefault("APP_SECRET", "test-secret-key-for-unit-tests-only-32b")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'data' / 'test.db'}")

sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root():
    return _PROJECT_ROOT


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)
