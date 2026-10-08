"""The back room's small JSON state files, kept in the app's own storage dir.

Writes are atomic (temp file + os.replace) so a crash mid-write leaves the old
file intact. A missing or unreadable file reads as the caller's default; every
file here can be rebuilt (desks reassign, progress re-derives from history).
"""

import json
import os
import tempfile
from pathlib import Path


def state_dir():
    path = Path(os.environ["APP_STORAGE_DIR"]) / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(name, default):
    try:
        return json.loads((state_dir() / name).read_text())
    except (OSError, ValueError):
        return default


def write_json(name, data):
    target = state_dir() / name
    fd, temp = tempfile.mkstemp(dir=target.parent, prefix=f".{name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp, target)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
