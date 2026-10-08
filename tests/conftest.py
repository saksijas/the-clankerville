import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
for path in (str(APP_DIR), str(TESTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(autouse=True)
def app_storage(tmp_path, monkeypatch):
    """Every test gets its own app storage dir, so state files never leak between tests."""
    monkeypatch.setenv("APP_STORAGE_DIR", str(tmp_path / "storage"))
    return tmp_path / "storage"
