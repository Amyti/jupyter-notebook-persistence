import os
import traceback
import pgcontents
from jupyter_server.auth import passwd

# --- FIX CRITIQUE POUR S3 SUR SCALINGO ---
# Les nouvelles versions de boto3/s3fs activent des checksums par défaut 
# que certains fournisseurs S3 ne supportent pas encore.
# On force la désactivation ici via les variables d'environnement.
os.environ["AWS_REQUEST_CHECKSUM_CALCULATION"] = "when_required"
os.environ["AWS_RESPONSE_CHECKSUM_VALIDATION"] = "when_required"
# -----------------------------------------

try:
    c = get_config()

    c.ServerApp.root_dir = '/'
    uid = os.environ.get('SCALINGO_UID', '')

    # Gestion de l'authentification (compatible Jupyter Server 2.0+)
    passwd_env = os.environ.get("JUPYTER_NOTEBOOK_PASSWORD", "")
    if passwd_env:
        # Note: ServerApp.password est déprécié mais fonctionne encore.
        # Pour une compatibilité future stricte, on pourrait utiliser IdentityProvider,
        # mais on garde ça simple pour s'assurer que ça marche maintenant.
        c.ServerApp.password = passwd(passwd_env)
    else:
        c.ServerApp.token = ""
        c.ServerApp.password = ""

    c.ServerApp.terminado_settings = {'shell_command': ['/bin/bash']}

    # Configuration S3
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    s3_endpoint = os.getenv("S3_ENDPOINT")

    if s3_access_key and s3_secret_key and s3_bucket_name:
        print("Configuration: Using S3ContentsManager (S3 Object Storage)")
        
        from s3contents import S3ContentsManager

        c.ServerApp.contents_manager_class = S3ContentsManager
        c.S3ContentsManager.bucket = s3_bucket_name
        c.S3ContentsManager.prefix = ""
        c.S3ContentsManager.access_key_id = s3_access_key
        c.S3ContentsManager.secret_access_key = s3_secret_key
        c.S3ContentsManager.endpoint_url = s3_endpoint

        # CORRECTION ICI : Remplacement de s3fs_kwargs par s3fs_config_kwargs
        # Et ajout de la configuration pour désactiver les checksums explicites
        c.S3ContentsManager.s3fs_config_kwargs = {
            "config_kwargs": {
                "request_checksum_calculation": "when_required",
                "check_exchange": False,
            }
        }

    else:
        print("Configuration: Using pgcontents/PostgresContentsManager")
        
        db_url = os.getenv('DATABASE_URL') or os.getenv('SCALINGO_POSTGRESQL_URL', '')
        # Fix pour SQLAlchemy qui requiert postgresql:// au lieu de postgres://
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        c.ServerApp.contents_manager_class = pgcontents.PostgresContentsManager
        c.PostgresContentsManager.db_url = db_url
        c.PostgresContentsManager.user_id = uid

except Exception:
    traceback.print_exc()
    # On évite le exit(-1) brutal pour voir les logs si besoin, 
    # mais Jupyter risque de ne pas démarrer correctement sans config.
    exit(-1)