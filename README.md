# Deploying JupyterLab on Scalingo with PostgreSQL Persistence

<img src="jupyter.png" alt="JupyterLab" width="50%">

This repository contains a preconfigured JupyterLab application ready to be deployed on **Scalingo**, with fully persistent notebook/file storage using **PostgreSQL + pgcontents**.

---

## Repository Structure

```
.
├── README.md
├── config_jupyter
├── Procfile
├── requirements.txt
└── jupyter_notebook_config.py
```

### Preconfigured Files

* **`config_jupyter`** - Bash script that initializes pgcontents and starts JupyterLab
* **`Procfile`** - Tells Scalingo how to run the app
  -> `web: bash -lc "bash ./config_jupyter"`
* **`requirements.txt`** - Python dependencies
* **`jupyter_notebook_config.py`** - Configures PostgreSQL as the Jupyter backend storage

---

## Architecture Overview

This app uses **pgcontents** to store all Jupyter files (notebooks, data, scripts…) **inside PostgreSQL**, instead of Scalingo’s ephemeral filesystem.

### Benefits

* **Full persistence** across restarts & redeployments
* **Multi-instance ready** (several containers share the same DB)
* **Automatic backups** thanks to Scalingo PostgreSQL plans
* **No data loss** due to ephemeral FS

---

## Requirements

* **Scalingo CLI installed**
  [Install the CLI](https://doc.scalingo.com/platform/cli/start)

  ```bash
  curl -O https://cli-dl.scalingo.com/install && bash install
  ```
* **Git** installed locally
* [**SSH key** configured on your Scalingo account](https://doc.scalingo.com/platform/getting-started/setup-ssh-macos#create-a-new-ssh-key-pair)

---

## Deployment Guide

---

### **Step 1 — Clone the repository**

```bash
git clone git@github.com:Amyti/jupyter_scalingo.git
cd jupyter_scalingo
```

---

### **Step 2 — Create the Scalingo app**

```bash
scalingo login

scalingo create jupyter-notebook-persistence

git remote add scalingo git@ssh.osc-fr1.scalingo.com:jupyter-notebook-persistence.git
```

Docs:
[How to create your app](https://doc.scalingo.com/platform/deployment/deploy-with-git#how-to-create-an-app)

---

### **Step 3 — Provision PostgreSQL**

```bash
scalingo --app jupyter-notebook-persistence addons-plans postgresql

scalingo --app jupyter-notebook-persistence addons-add postgresql postgresql-starter-512
```

Dashboard method:

1. [Connect to your Dashboard](https://dashboard.scalingo.com)
2. Select your app
3. *Resources* -> *Add an addon*
4. Choose **PostgreSQL**
5. Pick a plan and validate

Scalingo automatically injects these variables:

* `DATABASE_URL`
* `SCALINGO_POSTGRESQL_URL`

Docs: [https://doc.scalingo.com/databases/postgresql/start](https://doc.scalingo.com/databases/postgresql/start)

---

### **Step 4 — Configure environment variables**

Generate a secure token for JupyterLab:

```bash
scalingo --app jupyter-notebook-persistence env-set JUPYTER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

[Relevant env variables:](https://doc.scalingo.com/platform/app/environment)

* `DATABASE_URL` - auto-generated
* `SCALINGO_POSTGRESQL_URL` - auto-generated
* `JUPYTER_TOKEN` - Jupyter auth token
* `JUPYTER_NOTEBOOK_PASSWORD` - optional password
* `SCALINGO_UID` - user UID (optional)


---

### **Step 5 — Deploy to Scalingo**

```bash
git add *
git commit -m "initializing jupyter-app"
git push scalingo master
```

---

### **Step 6 — Open JupyterLab**

```bash
scalingo --app jupyter-notebook-persistence open
```

Authentication:

* Use the token from `JUPYTER_TOKEN`
* If no token is set -> Jupyter allows open access

### Generate a secure token manually

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
openssl rand -base64 32
```

---

## Advanced Configuration

### Change Jupyter token

```bash
scalingo --app jupyter-notebook-persistence env-set JUPYTER_TOKEN="new-secure-token"
scalingo --app jupyter-notebook-persistence restart
```

---

### List environment variables

```bash
scalingo --app jupyter-notebook-persistence env
```

---

### View live logs

```bash
scalingo --app jupyter-notebook-persistence logs --follow
```

---

### [Access PostgreSQL console](https://doc.scalingo.com/databases/postgresql/getting-started/accessing)

```bash
scalingo --app jupyter-notebook-persistence pgsql-console
```


---

### List files stored in PostgreSQL

Inside the console:

```sql
\dt
SELECT * FROM pgcontents.file;
```

---



## Resources

### Scalingo Documentation

* [https://doc.scalingo.com](https://doc.scalingo.com)
* PostgreSQL: [https://doc.scalingo.com/databases/postgresql/start](https://doc.scalingo.com/databases/postgresql/start)
* Environment variables: [https://doc.scalingo.com/platform/app/environment](https://doc.scalingo.com/platform/app/environment)
* Scalingo CLI: [https://doc.scalingo.com/platform/cli/start](https://doc.scalingo.com/platform/cli/start)

### Jupyter & pgcontents

* JupyterLab: [https://jupyterlab.readthedocs.io](https://jupyterlab.readthedocs.io)
* pgcontents: [https://github.com/quantopian/pgcontents](https://github.com/quantopian/pgcontents)
* Jupyter Server config: [https://jupyter-server.readthedocs.io](https://jupyter-server.readthedocs.io)

### Support

* Scalingo Support: [support@scalingo.com](mailto:support@scalingo.com)
* Status page: [https://status.scalingo.com](https://status.scalingo.com)
* Jupyter Forum: [https://discourse.jupyter.org](https://discourse.jupyter.org)

