import mimetypes
from datetime import datetime, timezone

from tornado.web import HTTPError

MAX_CONTENT_BYTES = 50 * 1024 * 1024  # 50 MB

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS jnb_files (
    path        TEXT        PRIMARY KEY,
    content     TEXT        NOT NULL,
    format      TEXT        NOT NULL DEFAULT 'text',
    mimetype    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS jnb_checkpoints (
    path           TEXT        NOT NULL,
    checkpoint_id  TEXT        NOT NULL DEFAULT '1',
    content        TEXT        NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (path, checkpoint_id)
);
CREATE INDEX IF NOT EXISTS jnb_files_path_prefix
    ON jnb_files (path text_pattern_ops);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(dt) -> str:
    if dt is None:
        return _now()
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


def _clean(path: str) -> str:
    """Normalize path and reject traversal attempts."""
    if "\x00" in path:
        raise HTTPError(400, "Invalid path")
    path = path.strip("/")
    for part in (path.split("/") if path else []):
        if part in (".", "..") or not part:
            raise HTTPError(400, "Invalid path")
    return path


def _like_prefix(prefix: str) -> str:
    """Escape SQL LIKE special chars in prefix, then append %."""
    return prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _check_size(content_str: str, label: str):
    if len(content_str.encode()) > MAX_CONTENT_BYTES:
        raise HTTPError(413, f"{label} exceeds maximum size of {MAX_CONTENT_BYTES // 1024 // 1024} MB")


def _base_model(name: str, path: str, kind: str, **extra) -> dict:
    return {
        "name": name,
        "path": path,
        "type": kind,
        "writable": True,
        "last_modified": _now(),
        "created": _now(),
        "content": None,
        "format": None,
        "mimetype": None,
        **extra,
    }
