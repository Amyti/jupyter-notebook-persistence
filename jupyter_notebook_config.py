try:
    import os, traceback
    import pgcontents
    from jupyter_server.auth import passwd

    c = get_config()

    c.ServerApp.root_dir = '/'
    uid = os.environ.get('SCALINGO_UID', '')

    passwd_env = os.environ.get("JUPYTER_NOTEBOOK_PASSWORD", "")
    if passwd_env:
        c.ServerApp.password = passwd(passwd_env)
    else:
        c.ServerApp.token = ""
        c.ServerApp.password = ""

    c.ServerApp.terminado_settings = {'shell_command': ['/bin/bash']}

    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    s3_endpoint = os.getenv("S3_ENDPOINT")

    if s3_access_key and s3_secret_key and s3_bucket_name and s3_endpoint:

        if not s3_endpoint.startswith("http"):
            raise ValueError("S3_ENDPOINT must start with http:// or https://")

        from s3contents import S3ContentsManager

        c.ServerApp.contents_manager_class = S3ContentsManager
        c.S3ContentsManager.bucket = s3_bucket_name
        c.S3ContentsManager.prefix = ""
        c.S3ContentsManager.access_key_id = s3_access_key
        c.S3ContentsManager.secret_access_key = s3_secret_key
        c.S3ContentsManager.endpoint_url = s3_endpoint

        print("Using S3ContentsManager")

    else:
        db_url = os.getenv("DATABASE_URL") or os.getenv("SCALINGO_POSTGRESQL_URL", "")
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        c.ServerApp.contents_manager_class = pgcontents.PostgresContentsManager
        c.PostgresContentsManager.db_url = db_url
        c.PostgresContentsManager.user_id = uid

        print("Using pgcontents/PostgresContentsManager")

except Exception:
    traceback.print_exc()
    exit(1)
