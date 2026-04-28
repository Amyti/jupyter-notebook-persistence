import mimetypes
import posixpath

import nbformat
from sqlalchemy import create_engine, text
from tornado.web import HTTPError
from traitlets import Unicode, default

from jupyter_server.services.contents.manager import ContentsManager

from .checkpoints import PGCheckpoints
from .utils import _INIT_SQL, _base_model, _check_size, _clean, _like_prefix, _ts


class PostgreSQLContentsManager(ContentsManager):

    db_url = Unicode("", config=True, help="PostgreSQL connection URL (postgresql://...)")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine = create_engine(self.db_url, pool_pre_ping=True)
        with self._engine.connect() as conn:
            conn.execute(text(_INIT_SQL))
            conn.commit()

    @default("checkpoints_class")
    def _checkpoints_class_default(self):
        return PGCheckpoints

    @default("checkpoints_kwargs")
    def _checkpoints_kwargs_default(self):
        return {"engine": self._engine}

    # --- helpers ---

    def _row_to_model(self, path, row, content=True) -> dict:
        is_notebook = path.endswith(".ipynb")
        model = _base_model(
            name=posixpath.basename(path),
            path=path,
            kind="notebook" if is_notebook else "file",
            mimetype=row[2],
            last_modified=_ts(row[4]),
            created=_ts(row[3]),
        )
        if content:
            if is_notebook:
                model["content"] = nbformat.reads(row[0], as_version=4)
                model["format"] = "json"
            else:
                model["content"] = row[0]
                model["format"] = row[1]
        return model

    def _dir_model(self, path, content=True) -> dict:
        model = _base_model(
            name=posixpath.basename(path) if path else "",
            path=path,
            kind="directory",
            format="json",
        )
        if not content:
            return model

        prefix = (path + "/") if path else ""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT path FROM jnb_files WHERE path LIKE :pat ESCAPE '\\'"),
                {"pat": _like_prefix(prefix)},
            ).fetchall()

        seen = {}
        for (p,) in rows:
            rel = p[len(prefix):]
            top = rel.split("/")[0]
            child_path = prefix + top
            is_dir = "/" in rel
            seen.setdefault(
                child_path,
                _base_model(
                    name=top,
                    path=child_path,
                    kind="directory" if is_dir else ("notebook" if top.endswith(".ipynb") else "file"),
                    format="json" if is_dir else None,
                ),
            )

        model["content"] = list(seen.values())
        return model

    # --- ContentsManager API ---

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
        path = _clean(path)
        if type == "directory" or not path or (type is None and not self.file_exists(path)):
            if path and not self.dir_exists(path):
                raise HTTPError(404, f"No such directory: {path}")
            return self._dir_model(path, content)

        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT content, format, mimetype, created_at, updated_at FROM jnb_files WHERE path = :path"),
                {"path": path},
            ).fetchone()
        if row is None:
            raise HTTPError(404, f"No such file: {path}")
        return self._row_to_model(path, row, content)

    def save(self, model, path) -> dict:
        path = _clean(path)
        if not path:
            raise HTTPError(400, "Cannot save to root")

        if model["type"] == "directory":
            return self._dir_model(path, content=False)

        if model["type"] == "notebook":
            nb = nbformat.from_dict(model["content"])
            nbformat.validate(nb)
            content_str = nbformat.writes(nb)
            _check_size(content_str, "Notebook")
            fmt, mime = "text", "application/x-ipynb+json"
        elif model["type"] == "file":
            content_str = model.get("content", "")
            _check_size(content_str, "File")
            fmt = model.get("format", "text")
            mime = model.get("mimetype") or mimetypes.guess_type(path)[0] or "text/plain"
        else:
            raise HTTPError(400, f"Unknown type: {model['type']}")

        self.run_pre_save_hooks(model=model, path=path)

        with self._engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO jnb_files (path, content, format, mimetype, created_at, updated_at)
                    VALUES (:path, :content, :format, :mime, NOW(), NOW())
                    ON CONFLICT (path) DO UPDATE SET
                        content    = EXCLUDED.content,
                        format     = EXCLUDED.format,
                        mimetype   = EXCLUDED.mimetype,
                        updated_at = NOW()
                """),
                {"path": path, "content": content_str, "format": fmt, "mime": mime},
            )
            conn.commit()

        return self.get(path, content=False)

    def delete_file(self, path):
        path = _clean(path)
        with self._engine.connect() as conn:
            conn.execute(text("DELETE FROM jnb_files WHERE path = :path"), {"path": path})
            conn.execute(text("DELETE FROM jnb_checkpoints WHERE path = :path"), {"path": path})
            conn.commit()

    def rename_file(self, old_path, new_path):
        old_path, new_path = _clean(old_path), _clean(new_path)
        if self.file_exists(new_path):
            raise HTTPError(409, f"File already exists: {new_path}")
        with self._engine.connect() as conn:
            conn.execute(text("UPDATE jnb_files SET path = :new WHERE path = :old"), {"new": new_path, "old": old_path})
            conn.execute(text("UPDATE jnb_checkpoints SET path = :new WHERE path = :old"), {"new": new_path, "old": old_path})
            conn.commit()
