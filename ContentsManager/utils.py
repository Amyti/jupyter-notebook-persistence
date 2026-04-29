from datetime import datetime, timezone

from tornado.web import HTTPError

MAX_CONTENT_BYTES = 50 * 1024 * 1024  # 50 Mo maximum par fichier

# SQL exécuté au démarrage pour créer les tables et l'index si nécessaire.
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
    # Convertit un datetime issu de la DB en ISO 8601. Retourne l'heure actuelle si None.
    if dt is None:
        return _now()
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


def _clean(path: str) -> str:
    # Normalise le chemin et bloque les tentatives de path traversal (null bytes, .., .).
    if "\x00" in path:
        raise HTTPError(400, "Chemin invalide")
    path = path.strip("/")
    for part in (path.split("/") if path else []):
        if part in (".", "..") or not part:
            raise HTTPError(400, "Chemin invalide")
    return path


def _like_prefix(prefix: str) -> str:
    # Échappe les caractères spéciaux SQL LIKE (%, _, \) puis ajoute % pour la recherche par préfixe.
    return prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
