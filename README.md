# Barber Management System — 3-Tier Cloud Application

A 3-tier web application (Browser → Flask/gunicorn → PostgreSQL) built for **Creation and Administration of Cloud Based Applications** and prepared for both cloud paths:

* **Option 1 (Azure):** Azure Database for PostgreSQL Flexible Server + Azure Container Registry (ACR) + Azure Container Apps (ACA) + GitHub Actions
* **Option 2 (Render):** Render PostgreSQL + Render Web Service (Docker) + GitHub Container Registry (GHCR) + Render Deploy Hook

## Architecture & Project Structure

| Tier | Technology | Details |
|---|---|---|
| Presentation | Jinja2 HTML templates | Dashboard, Appointments, Barbers, Services (`templates/`) |
| Application | Python 3.12 + Flask + gunicorn | Web UI + REST CRUD API (`/api/barbers`, `/api/services`, `/api/appointments`) + `/health` (`app.py`) |
| Data | PostgreSQL 16 | `barbers`, `services`, `appointments` (`db/schema.sql`, `db/seed.sql`) |

```
.
├── app.py                          # Flask app + REST API + /health
├── templates/                      # HTML UI (Dashboard, Appointments, Barbers, Services)
├── db/
│   ├── schema.sql                  # Table definitions (run via VS Code or auto on startup)
│   └── seed.sql                    # Sample barbers, services and appointments
├── Dockerfile                      # python:3.12-slim, gunicorn, honours $PORT
├── docker-compose.yml              # One-command local run (app + postgres)
├── requirements.txt
├── .env.example
├── .github/workflows/
│   ├── deploy.yml                  # Option 2: build linux/amd64 → GHCR → Render deploy hook
│   └── azure-acr.yml               # Option 1: build linux/amd64 → ACR (skips if ACR secrets unset)
├── scripts/
│   ├── push-to-acr.sh              # Option 1: local linux/amd64 build, tag & push to ACR
│   ├── smoke-test.sh               # Automated 26-check CRUD + /health verification
│   └── make-zip.sh                 # Builds Moodle submission .zip (excludes .venv, __pycache__)
└── report/
    ├── build_report.py             # Generates report/Report.pdf from screenshots
    └── screenshots/                # Drop your screenshots here
```

## Environment Variables

| Variable | Used by | Description |
|---|---|---|
| `DATABASE_URL` | Render | Full PostgreSQL connection string (`postgresql://...`) |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Azure / Local | Individual PostgreSQL connection fields |
| `DB_SSLMODE` | Azure (`require`) | Forces SSL (`require`) when connecting to Azure PostgreSQL |
| `APP_PLATFORM` | Optional | Shown in UI footer (auto-detects `Render` / `Azure Container Apps`) |
| `PORT` | Render / Docker | Listening port (defaults to `5000`; Render injects its own `PORT`) |

---

## Local Run & Verification

On macOS, AirPlay Receiver often occupies port `5000`, so bind the host port to `5050` with `APP_PORT=5050`:

```bash
APP_PORT=5050 docker compose up -d --build
./scripts/smoke-test.sh http://localhost:5050
```

Open **http://localhost:5050** in your browser (or **http://localhost:5000** if port 5000 is free).
Stop local containers with:

```bash
docker compose down
```

---

## Step 0: Push to GitHub (Required for Both Options)

1. Create a new **empty** repository on GitHub named `barber-management-system` (do **not** initialize with README/gitignore).
2. Connect and push:
   ```bash
   cd ~/.gemini/antigravity/scratch/barber-management-system
   git remote add origin https://github.com/<YOUR_GITHUB_USER>/barber-management-system.git
   git push -u origin main
   ```

---

## Option 1: Azure (PostgreSQL + ACR + ACA + GitHub Actions)

> **Azure for Students note:** Allowed regions are typically `swedencentral`, `norwayeast`, `uksouth`, `italynorth`, `spaincentral`. Use the same region (e.g., **Sweden Central**) for all resources in one Resource Group (`rg-barber-cloud`) so cleanup at the end is one click.

### 1.1 Azure Database for PostgreSQL Flexible Server
1. Azure Portal → **Create a resource → Azure Database for PostgreSQL Flexible Server**.
   * Resource group: `rg-barber-cloud` (create new)
   * Server name: e.g. `barberpg-<yourname>`
   * Region: **Sweden Central**
   * PostgreSQL version: **16**, Workload type: **Development** (Burstable B1ms)
   * Authentication: **PostgreSQL authentication only**, Admin username: `pgadmin`, set a strong password
   * Networking: **Public access**, check **Allow public access from any Azure service within Azure to this server**, and click **+ Add current client IP address**
2. After creation → **Settings → Databases → + Add** → name it `barberdb`.
3. In **VS Code**, install the **PostgreSQL** extension (Microsoft or SQLTools + PostgreSQL driver) and connect:
   * Host: `barberpg-<yourname>.postgres.database.azure.com`
   * Port: `5432`, Database: `barberdb`, User: `pgadmin`, Password: `<your password>`, SSL Mode: `require`
4. Open `db/schema.sql` and execute it, then open `db/seed.sql` and execute it.

### 1.2 Azure Container Registry (ACR)
1. Azure Portal → **Create a resource → Container Registry**.
   * Resource group: `rg-barber-cloud`, Registry name: e.g. `barberacr<yourname>` (lowercase alphanumeric), Location: **Sweden Central**, SKU: **Basic**.
2. Open the created ACR → **Settings → Access keys** → enable **Admin user**.
3. Copy **Login server** (`barberacr<yourname>.azurecr.io`), **Username**, and **password**.
4. Configure local Docker authentication:
   ```bash
   docker login barberacr<yourname>.azurecr.io
   ```

### 1.3 Build (`linux/amd64`), Tag, and Push Locally
Make sure Docker Desktop is running, then run:
```bash
./scripts/push-to-acr.sh barberacr<yourname> v1
```
(This runs `docker build --platform linux/amd64`, tags the image, and pushes `:v1` and `:latest`.)
Verify in Azure Portal → ACR → **Services → Repositories** → `barber-app`.

### 1.4 Deploy to Azure Container Apps (ACA)
1. Azure Portal → **Create a resource → Container App**.
   * Resource group: `rg-barber-cloud`, Container app name: `barber-app`, Region: **Sweden Central** (creates a Container Apps Environment automatically).
2. **Container** tab:
   * Uncheck *Use quickstart image*
   * Image source: **Azure Container Registry**, select your registry, image `barber-app`, tag `v1` (authentication: Admin credentials)
   * First create a secret (or add it right after deployment under **Settings → Secrets → + Add**):
     * Secret name: `db-password`, Value: `<your postgres password>`
   * Environment variables:
     * `DB_HOST` = `barberpg-<yourname>.postgres.database.azure.com` (Manual)
     * `DB_PORT` = `5432` (Manual)
     * `DB_NAME` = `barberdb` (Manual)
     * `DB_USER` = `pgadmin` (Manual)
     * `DB_SSLMODE` = `require` (Manual)
     * `DB_PASSWORD` = Reference secret `db-password`
3. **Ingress** tab:
   * Ingress: **Enabled**
   * Ingress traffic: **Accepting traffic from anywhere**
   * Target port: `5000`
4. Deploy and open the **Application Url** (`https://barber-app.<random>.swedencentral.azurecontainerapps.io`).

### 1.5 GitHub Actions → ACR (Manual Publish in ACA)
1. GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**:
   * `ACR_LOGIN_SERVER` = `barberacr<yourname>.azurecr.io`
   * `ACR_USERNAME` = ACR admin username
   * `ACR_PASSWORD` = ACR admin password
2. Make a small code update (e.g. header/text), commit, and push to `main`.
3. Workflow `.github/workflows/azure-acr.yml` builds `linux/amd64` and pushes `:latest` and `:<commit-sha>` to ACR.
4. In ACA → **Application → Revisions and replicas → Create new revision** → select the new image tag (`:<commit-sha>` or `:latest`) and deploy manually.

📸 **Screenshots for Option 1:**
* `report/screenshots/azure-actions.png` — GitHub Actions workflow run succeeded
* `report/screenshots/azure-acr.png` — ACR Repositories view showing `barber-app`
* `report/screenshots/azure-app.png` — Working app on the public ACA URL

---

## Option 2: Render (PostgreSQL + Web Service + GHCR + Deploy Hook)

### 2.1 Render Managed PostgreSQL + VS Code Setup
1. On **https://dashboard.render.com** → **New → Postgres**:
   * Name: `barberdb`, Database: `barberdb`, Region: e.g. **Frankfurt**, Plan: **Free** → **Create Database**.
2. In **VS Code**, connect using the **External Database URL** from Render (Host `dpg-xxxx.frankfurt-postgres.render.com`, Port `5432`, User, Password, Database, **SSL: require**).
3. Run `db/schema.sql`, then run `db/seed.sql`.

### 2.2 GitHub Permissions & First GHCR Push
1. GitHub repository → **Settings → Actions → General → Workflow permissions** → select **Read and write permissions** → **Save**.
2. Push your code to `main` (Step 0). `.github/workflows/deploy.yml` runs and pushes `ghcr.io/<your_user_lowercase>/barber-management-system:latest` (the Render deploy hook step skips safely until the secret is added).
3. Go to your GitHub profile → **Packages** → `barber-management-system` → **Package settings** → **Change visibility → Public** so Render can pull the image without credentials.

### 2.3 Render Web Service (Docker / Existing Image)
1. Render Dashboard → **New → Web Service → Existing Image**.
   * Image URL: `ghcr.io/<your_user_lowercase>/barber-management-system:latest`
   * Name: `barber-management-system`, same region as your Postgres (**Frankfurt**), Plan: **Free**.
2. Under **Environment Variables**, add:
   * `DATABASE_URL` = **Internal Database URL** copied from your Render Postgres page.
3. Create the Web Service, then go to **Settings**:
   * **Auto-Deploy**: set to **Off** (Disabled)
   * **Deploy Hook**: copy the **Deploy Hook URL**
   * **Health Check Path**: `/health` (optional)

### 2.4 GitHub Secret & End-to-End CI/CD Test
1. GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**:
   * Name: `RENDER_DEPLOY_HOOK_URL`
   * Value: the Deploy Hook URL copied from Render
2. Make a small visible change (or trigger **Actions → Build, push to GHCR and deploy to Render → Run workflow**), push to `main`, and watch:
   * GitHub Actions builds `linux/amd64`, pushes to GHCR, and triggers the Render Deploy Hook.
   * Render pulls the updated image and deploys automatically.

📸 **Screenshots for Option 2:**
* `report/screenshots/render-actions.png` — GitHub Actions workflow run succeeded
* `report/screenshots/render-packages.png` — Pushed image in GitHub Packages (`ghcr.io`)
* `report/screenshots/render-app.png` — Working app on the public Render URL

---

## Generating Deliverables (PDF Report + Source Code `.zip`)

1. Put your screenshots in `report/screenshots/` using the filenames listed above.
2. Update your names, GitHub repo URL, and live URLs at the top of `report/build_report.py`.
3. Generate the PDF report and Moodle source zip:
   ```bash
   python3 report/build_report.py   # creates report/Report.pdf
   ./scripts/make-zip.sh            # creates ../barber-management-system.zip
   ```
   (`make-zip.sh` automatically excludes `.venv`, `venv`, `__pycache__`, `*.pyc`, `.git`, `.env`, and generated report artifacts.)
