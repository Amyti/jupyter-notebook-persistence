try:
    import os, hashlib
    import traceback
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

    db_url = os.getenv('DATABASE_URL', None) or os.getenv('SCALINGO_POSTGRESQL_URL', '')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if db_url:
        c.ServerApp.contents_manager_class = pgcontents.PostgresContentsManager
        c.PostgresContentsManager.db_url = db_url
        c.PostgresContentsManager.user_id = uid

except Exception:
    traceback.print_exc()
    exit(-1)