try:
    import os, traceback
    import sys
    sys.path.insert(0, '/app')
    from ContentsManager import PostgreSQLContentsManager
    from jupyter_server.auth import passwd

    c = get_config()

    c.ServerApp.root_dir = '/'

    passwd_env = os.environ.get("JUPYTER_NOTEBOOK_PASSWORD", "")
    if passwd_env:
        if len(passwd_env) < 12:
            print("ERROR: JUPYTER_NOTEBOOK_PASSWORD must be at least 12 characters")
            exit(-1)
        c.ServerApp.password = passwd(passwd_env)

    c.ServerApp.terminals_enabled = False

    db_url = os.getenv('DATABASE_URL') or os.getenv('SCALINGO_POSTGRESQL_URL', '')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    c.ServerApp.contents_manager_class = PostgreSQLContentsManager
    c.PostgreSQLContentsManager.db_url = db_url

    print("Using PostgreSQLContentsManager")

except Exception:
    traceback.print_exc()
    exit(-1)
