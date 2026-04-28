import nbformat
from sqlalchemy import text
from tornado.web import HTTPError

from jupyter_server.services.contents.checkpoints import Checkpoints, GenericCheckpointsMixin

from .utils import _now, _ts


class PGCheckpoints(GenericCheckpointsMixin, Checkpoints):

    def __init__(self, engine, **kwargs):
        super().__init__(**kwargs)
        self._engine = engine

    def _exec(self, sql, **params):
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params)
            conn.commit()
            return result

    def create_file_checkpoint(self, content, format, path):
        self._exec(
            """
            INSERT INTO jnb_checkpoints (path, checkpoint_id, content, created_at)
            VALUES (:path, '1', :content, NOW())
            ON CONFLICT (path, checkpoint_id)
            DO UPDATE SET content = EXCLUDED.content, created_at = NOW()
            """,
            path=path, content=content,
        )
        return {"id": "1", "last_modified": _now()}

    def create_notebook_checkpoint(self, nb, path):
        return self.create_file_checkpoint(nbformat.writes(nb), "text", path)

    def get_file_checkpoint(self, checkpoint_id, path):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT content, created_at FROM jnb_checkpoints WHERE path = :path AND checkpoint_id = :cid"),
                {"path": path, "cid": checkpoint_id},
            ).fetchone()
        if row is None:
            raise HTTPError(404, f"Checkpoint {checkpoint_id} not found for {path}")
        return {"type": "file", "content": row[0], "format": "text", "last_modified": _ts(row[1])}

    def get_notebook_checkpoint(self, checkpoint_id, path):
        cp = self.get_file_checkpoint(checkpoint_id, path)
        return {"type": "notebook", "content": nbformat.reads(cp["content"], as_version=4)}

    def delete_checkpoint(self, checkpoint_id, path):
        self._exec(
            "DELETE FROM jnb_checkpoints WHERE path = :path AND checkpoint_id = :cid",
            path=path, cid=checkpoint_id,
        )

    def list_checkpoints(self, path):
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT checkpoint_id, created_at FROM jnb_checkpoints WHERE path = :path"),
                {"path": path},
            ).fetchall()
        return [{"id": r[0], "last_modified": _ts(r[1])} for r in rows]

    def rename_all_checkpoints(self, old_path, new_path):
        self._exec("UPDATE jnb_checkpoints SET path = :new WHERE path = :old", new=new_path, old=old_path)

    def delete_all_checkpoints(self, path):
        self._exec("DELETE FROM jnb_checkpoints WHERE path = :path", path=path)
