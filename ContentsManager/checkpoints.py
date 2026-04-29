import nbformat
from sqlalchemy import text
from tornado.web import HTTPError

from jupyter_server.services.contents.checkpoints import Checkpoints, GenericCheckpointsMixin

from .utils import _now, _ts


class PGCheckpoints(GenericCheckpointsMixin, Checkpoints):
    """Gestion des checkpoints Jupyter stockés en PostgreSQL (table jnb_checkpoints).
    Un seul checkpoint par fichier est conservé — l'ancien est écrasé à chaque sauvegarde.
    """

    def __init__(self, engine, **kwargs):
        super().__init__(**kwargs)
        self._engine = engine

    def _exec(self, sql, **params):
        # Exécute une requête d'écriture et commit immédiatement.
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params)
            conn.commit()
            return result

    def create_file_checkpoint(self, content, content_format, path):
        # Insère ou remplace le checkpoint existant pour ce fichier.
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
        # Sérialise le notebook avant de le sauvegarder comme checkpoint.
        return self.create_file_checkpoint(nbformat.writes(nb), "text", path)

    def get_file_checkpoint(self, checkpoint_id, path):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT content, created_at FROM jnb_checkpoints WHERE path = :path AND checkpoint_id = :cid"),
                {"path": path, "cid": checkpoint_id},
            ).fetchone()
        if row is None:
            raise HTTPError(404, f"Checkpoint {checkpoint_id} introuvable pour {path}")
        content, created_at = row
        return {"type": "file", "content": content, "format": "text", "last_modified": _ts(created_at)}

    def get_notebook_checkpoint(self, checkpoint_id, path):
        # Récupère le checkpoint et le désérialise en objet notebook.
        checkpoint = self.get_file_checkpoint(checkpoint_id, path)
        return {"type": "notebook", "content": nbformat.reads(checkpoint["content"], as_version=4)}

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
        return [{"id": checkpoint_id, "last_modified": _ts(created_at)} for checkpoint_id, created_at in rows]

    def rename_all_checkpoints(self, old_path, new_path):
        # Appelé automatiquement lors d'un renommage de fichier.
        self._exec("UPDATE jnb_checkpoints SET path = :new WHERE path = :old", new=new_path, old=old_path)

    def delete_all_checkpoints(self, path):
        # Appelé automatiquement lors d'une suppression de fichier.
        self._exec("DELETE FROM jnb_checkpoints WHERE path = :path", path=path)
