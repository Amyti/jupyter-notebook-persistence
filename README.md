# Deploying JupyterLab on Scalingo with PostgreSQL Persistence

<img src="jupyter.png" alt="JupyterLab" width="50%">

This repository contains a preconfigured JupyterLab application ready to be deployed on **Scalingo**, with fully persistent notebook/file storage using **PostgreSQL**.

---

## Security notices

> **Authentication is mandatory.** The app will refuse to start if neither `JUPYTER_TOKEN` nor `JUPYTER_NOTEBOOK_PASSWORD` is configured.

> **Terminal access is disabled.** The JupyterLab terminal is intentionally disabled to prevent access to environment variables, credentials, and the container filesystem.

---

## Repository structure

```
.
├── README.md
├── Procfile
├── config_jupyter
├── requirements.txt
├── jupyter_notebook_config.py
└── ContentsManager/
    ├── __init__.py
    ├── manager.py
    ├── checkpoints.py
    └── utils.py
```

- **`config_jupyter`** — starts JupyterLab after validating authentication config
- **`Procfile`** — tells Scalingo how to run the app
- **`requirements.txt`** — pinned Python dependencies
- **`jupyter_notebook_config.py`** — configures PostgreSQL as the Jupyter storage backend
- **`ContentsManager/`** — custom Jupyter contents manager backed by PostgreSQL

---

## Architecture

All Jupyter files (notebooks, scripts, data…) are stored directly in **PostgreSQL** instead of Scalingo's ephemeral filesystem.

**Benefits:**
- Persistence across restarts and redeployments
- Multi-instance ready (several containers share the same DB)
- Automatic backups via Scalingo PostgreSQL plans
- No data loss from ephemeral filesystem

---

## Requirements

- **Scalingo CLI** — [installation guide](https://doc.scalingo.com/platform/cli/start)

  ```bash
  curl -O https://cli-dl.scalingo.com/install && bash install
  ```

- **Git** installed locally
- [SSH key configured on your Scalingo account](https://doc.scalingo.com/platform/getting-started/setup-ssh-macos#create-a-new-ssh-key-pair)

---

## Deployment

### Step 1 — Clone the repository

```bash
git clone git@github.com:Amyti/jupyter_scalingo.git
cd jupyter_scalingo
```

### Step 2 — Create the Scalingo app

```bash
scalingo login
scalingo create jupyter-notebook-persistence
git remote add scalingo git@ssh.osc-fr1.scalingo.com:jupyter-notebook-persistence.git
```

### Step 3 — Provision PostgreSQL

```bash
scalingo --app jupyter-notebook-persistence addons-add postgresql postgresql-starter-512
```

Or via the dashboard: **Resources → Add an addon → PostgreSQL**.

Scalingo automatically injects `DATABASE_URL` and `SCALINGO_POSTGRESQL_URL`.

### Step 4 — Set authentication (required)

**Option A — Token**

```bash
scalingo --app jupyter-notebook-persistence env-set \
  JUPYTER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

**Option B — Password** (minimum 12 characters)

```bash
scalingo --app jupyter-notebook-persistence env-set JUPYTER_NOTEBOOK_PASSWORD="your-password"
```

The app will **refuse to start** if neither variable is set, or if the password is shorter than 12 characters.

### Step 5 — Deploy

```bash
git add .
git commit -m "deploy jupyterlab"
git push scalingo main
```

### Step 6 — Open JupyterLab

```bash
scalingo --app jupyter-notebook-persistence open
```

Authenticate with the token or password configured in Step 4.

---

## Operations

### Rotate the token

```bash
scalingo --app jupyter-notebook-persistence env-set \
  JUPYTER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
scalingo --app jupyter-notebook-persistence restart
```

### View logs

```bash
scalingo --app jupyter-notebook-persistence logs --follow
```

### List environment variables

```bash
scalingo --app jupyter-notebook-persistence env
```

### Inspect stored notebooks in PostgreSQL

```bash
scalingo --app jupyter-notebook-persistence pgsql-console
```

```sql
SELECT path, updated_at FROM jnb_files ORDER BY updated_at DESC;
```

---

## Dependencies

All dependencies are pinned to exact versions. Update them after checking for CVEs on [osv.dev](https://osv.dev).

| Package | Version |
|---|---|
| jupyterlab | 4.5.6 |
| notebook | 7.5.5 |
| psycopg2-binary | 2.9.12 |
| sqlalchemy | 2.0.49 |
| nbformat | 5.10.4 |
| ipython | 9.13.0 |

---

## Resources

- Scalingo docs: [https://doc.scalingo.com](https://doc.scalingo.com)
- JupyterLab: [https://jupyterlab.readthedocs.io](https://jupyterlab.readthedocs.io)
- Jupyter Server config: [https://jupyter-server.readthedocs.io](https://jupyter-server.readthedocs.io)
- Scalingo support: [support@scalingo.com](mailto:support@scalingo.com)
