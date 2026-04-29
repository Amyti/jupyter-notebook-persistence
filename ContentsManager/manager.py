import mimetypes
import posixpath

import nbformat
from sqlalchemy import create_engine, text
from tornado.web import HTTPError
from traitlets import Unicode, default

from jupyter_server.services.contents.manager import ContentsManager

from .checkpoints import PGCheckpoints
from .utils import _INIT_SQL, _clean, _like_prefix, _now, _ts, MAX_CONTENT_BYTES


class PostgreSQLContentsManager(ContentsManager):
    """ContentsManager Jupyter utilisant PostgreSQL à la place du filesystem local.
    Les tables sont créées automatiquement au démarrage si elles n'existent pas.
    """

    db_url = Unicode("", config=True, help="URL de connexion PostgreSQL (postgresql://...)")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine = create_engine(self.db_url, pool_pre_ping=True)
        # Création des tables et de l'index au démarrage.
        with self._engine.connect() as conn:
            conn.execute(text(_INIT_SQL))
            conn.commit()

    @default("checkpoints_class")
    def _checkpoints_class_default(self):
        return PGCheckpoints

    @default("checkpoints_kwargs")
    def _checkpoints_kwargs_default(self):
        # On partage le même engine entre le manager et les checkpoints.
        return {"engine": self._engine}

    # --- helpers ---

    def _row_to_model(self, path, row, content=True) -> dict:
        # Construit le dict attendu par l'API Jupyter à partir d'une ligne DB.
        content_str, content_format, mimetype, created_at, updated_at = row
        is_notebook = path.endswith(".ipynb")
        model = {
            "name": posixpath.basename(path),
            "path": path,
            "type": "notebook" if is_notebook else "file",
            "writable": True,
            "last_modified": _ts(updated_at),
            "created": _ts(created_at),
            "content": None,
            "format": None,
            "mimetype": mimetype,
        }
        if content:
            if is_notebook:
                model["content"] = nbformat.reads(content_str, as_version=4)
                model["format"] = "json"
            else:
                model["content"] = content_str
                model["format"] = content_format
        return model

    def _dir_model(self, path, content=True) -> dict:
        # Construit le dict d'un répertoire avec la liste de ses enfants directs.
        model = {
            "name": posixpath.basename(path) if path else "",
            "path": path,
            "type": "directory",
            "writable": True,
            "last_modified": _now(),
            "created": _now(),
            "content": None,
            "format": "json",
            "mimetype": None,
        }
        if not content:
            return model

        prefix = (path + "/") if path else ""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT path FROM jnb_files WHERE path LIKE :pat ESCAPE '\\'"),
                {"pat": _like_prefix(prefix)},
            ).fetchall()

        # Les répertoires sont virtuels : un dossier existe dès qu'un fichier a ce préfixe.
        # On déduplique avec setdefault pour n'afficher chaque enfant qu'une fois.
        seen = {}
        for (file_path,) in rows:
            relative_path = file_path[len(prefix):]
            child_name = relative_path.split("/")[0]
            child_path = prefix + child_name
            is_dir = "/" in relative_path
            seen.setdefault(child_path, {
                "name": child_name,
                "path": child_path,
                "type": "directory" if is_dir else ("notebook" if child_name.endswith(".ipynb") else "file"),
                "writable": True,
                "last_modified": _now(),
                "created": _now(),
                "content": None,
                "format": "json" if is_dir else None,
                "mimetype": None,
            })

        model["content"] = list(seen.values())
        return model

    # --- API ContentsManager ---

    def file_exists(self, path="") -> bool:
        path = _clean(path)
        if not path:
            return False
        with self._engine.connect() as conn:
            return conn.execute(
                text("SELECT 1 FROM jnb_files WHERE path = :path"),
                {"path": path},
            ).fetchone() is not None

    def dir_exists(self, path) -> bool:
        # Un répertoire existe si au moins un fichier a ce chemin comme préfixe.
        path = _clean(path)
        if not path:
            return True
        with self._engine.connect() as conn:
            return conn.execute(
                text("SELECT 1 FROM jnb_files WHERE path LIKE :pat ESCAPE '\\' LIMIT 1"),
                {"pat": _like_prefix(path + "/")},
            ).fetchone() is not None

    def is_hidden(self, path) -> bool:
        return False

    def get(self, path, content=True, type=None, format=None) -> dict:
        # Si le chemin ne correspond à aucun fichier, on tente de le résoudre comme répertoire.
        path = _clean(path)
        if type == "directory" or not path or (type is None and not self.file_exists(path)):
            if path and not self.dir_exists(path):
                raise HTTPError(404, f"Répertoire introuvable : {path}")
            return self._dir_model(path, content)

        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT content, format, mimetype, created_at, updated_at FROM jnb_files WHERE path = :path"),
                {"path": path},
            ).fetchone()
        if row is None:
            raise HTTPError(404, f"Fichier introuvable : {path}")
        return self._row_to_model(path, row, content)

    def save(self, model, path) -> dict:
        path = _clean(path)
        if not path:
            raise HTTPError(400, "Impossible de sauvegarder à la racine")

        if model["type"] == "directory":
            return self._dir_model(path, content=False)

        if model["type"] == "notebook":
            nb = nbformat.from_dict(model["content"])
            try:
                nbformat.validate(nb)
            except nbformat.ValidationError as e:
                raise HTTPError(400, f"Notebook invalide : {e}")
            content_str = nbformat.writes(nb)
            if len(content_str.encode()) > MAX_CONTENT_BYTES:
                raise HTTPError(413, f"Notebook dépasse la taille maximale de {MAX_CONTENT_BYTES // 1024 // 1024} Mo")
            content_format = "text"
            mimetype = "application/x-ipynb+json"
        elif model["type"] == "file":
            content_str = model.get("content") or ""
            if len(content_str.encode()) > MAX_CONTENT_BYTES:
                raise HTTPError(413, f"Fichier dépasse la taille maximale de {MAX_CONTENT_BYTES // 1024 // 1024} Mo")
            content_format = model.get("format", "text")
            mimetype = model.get("mimetype") or mimetypes.guess_type(path)[0] or "text/plain"
        else:
            raise HTTPError(400, f"Type inconnu : {model['type']}")

        self.run_pre_save_hooks(model=model, path=path)

        # INSERT ou UPDATE selon que le fichier existe déjà.
        with self._engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO jnb_files (path, content, format, mimetype, created_at, updated_at)
                    VALUES (:path, :content, :content_format, :mimetype, NOW(), NOW())
                    ON CONFLICT (path) DO UPDATE SET
                        content        = EXCLUDED.content,
                        format         = EXCLUDED.format,
                        mimetype       = EXCLUDED.mimetype,
                        updated_at     = NOW()
                """),
                {"path": path, "content": content_str, "content_format": content_format, "mimetype": mimetype},
            )
            conn.commit()

        return self.get(path, content=False)

    def delete_file(self, path):
        # Supprime le fichier et ses checkpoints associés en une seule transaction.
        path = _clean(path)
        with self._engine.connect() as conn:
            conn.execute(text("DELETE FROM jnb_files WHERE path = :path"), {"path": path})
            conn.execute(text("DELETE FROM jnb_checkpoints WHERE path = :path"), {"path": path})
            conn.commit()

    def rename_file(self, old_path, new_path):
        old_path, new_path = _clean(old_path), _clean(new_path)
        if not self.file_exists(old_path):
            raise HTTPError(404, f"Fichier introuvable : {old_path}")
        if self.file_exists(new_path):
            raise HTTPError(409, f"Un fichier existe déjà à ce chemin : {new_path}")
        with self._engine.connect() as conn:
            conn.execute(text("UPDATE jnb_files SET path = :new WHERE path = :old"), {"new": new_path, "old": old_path})
            conn.execute(text("UPDATE jnb_checkpoints SET path = :new WHERE path = :old"), {"new": new_path, "old": old_path})
            conn.commit()
