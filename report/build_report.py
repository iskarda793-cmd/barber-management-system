"""
Builds report/Report.pdf from report/screenshots/* using headless Google Chrome.

1. Fill in CONFIG below.
2. Put screenshots into report/screenshots/ (file names are listed in SECTIONS).
3. python3 report/build_report.py
A section is left out if none of its screenshots exist. A missing *required*
screenshot in an included section shows a red placeholder.
"""
import base64
import html
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

# ----------------------------------------------------------------- CONFIG ----
CONFIG = {
    "title": "Barber Management System: Cloud Deployment (CaaS)",
    "students": "Arda Işık, <partner name>",
    "course": "Creation and Administration of Cloud Based Applications",
    "teacher": "dr inż. Aleksander Rewak",
    "github_repo": "https://github.com/<user>/barber-management-system",
    "aca_url": "https://barber-app.<random>.swedencentral.azurecontainerapps.io",
    "render_url": "https://barber-management-system.onrender.com",
}
# -----------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "screenshots"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

C = CONFIG
SECTIONS = [
    {
        "title": "Option 1: Azure (PostgreSQL Flexible Server, ACR, Container Apps, GitHub Actions)",
        "description": f"""
<ol>
<li><b>Database:</b> I created an <i>Azure Database for PostgreSQL Flexible Server</i>
(Burstable B1ms, region Sweden Central, public access with firewall rules for my IP and for
Azure services) and the database <code>barberdb</code>. I connected to it from VS Code (SSL
required) and initialized it with <code>db/schema.sql</code> and <code>db/seed.sql</code>
(tables <code>barbers</code>, <code>services</code>, <code>appointments</code>).</li>
<li><b>Container registry:</b> I provisioned an <i>Azure Container Registry</i> (Basic) in the
Portal, enabled the <b>Admin user</b>, and authenticated locally with
<code>docker login &lt;registry&gt;.azurecr.io</code>.</li>
<li><b>Image:</b> I built the app image for <code>linux/amd64</code>
(<code>docker build --platform linux/amd64</code>), tagged it as
<code>&lt;registry&gt;.azurecr.io/barber-app:v1</code>, and pushed it to ACR.</li>
<li><b>Azure Container Apps:</b> I deployed the image with external ingress on target port
5000. The environment variables are <code>DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_SSLMODE=require,
APP_PLATFORM</code>. <code>DB_PASSWORD</code> references the Container Apps secret
<code>db-password</code>.</li>
<li><b>CI:</b> I added the repository secrets <code>ACR_LOGIN_SERVER, ACR_USERNAME,
ACR_PASSWORD</code>. The workflow <code>.github/workflows/azure-acr.yml</code> builds and pushes
<code>barber-app:latest</code> and <code>barber-app:&lt;commit-sha&gt;</code> to ACR on every push
to <code>main</code>. The new image is then published manually in ACA by creating a new
revision.</li>
</ol>
<p>Public URL: <a href="{C['aca_url']}">{C['aca_url']}</a></p>""",
        "shots": [
            ("azure-actions.png", "Successfully completed GitHub Actions workflow (build and push to ACR)", True),
            ("azure-acr.png", "ACR Repositories view with the pushed barber-app image", True),
            ("azure-app.png", "Working web application on the public Azure Container Apps URL", True),
            ("azure-db-vscode.png", "Azure PostgreSQL initialized from VS Code", False),
            ("azure-aca-env.png", "Container App environment variables and secret", False),
        ],
    },
    {
        "title": "Option 2: Render (PostgreSQL, Web Service, GHCR, Deploy Hook)",
        "description": f"""
<ol>
<li><b>Database:</b> I created a managed <i>PostgreSQL</i> database on Render, connected from
VS Code with the <i>External Database URL</i>, and initialized the schema with
<code>db/schema.sql</code> and <code>db/seed.sql</code>.</li>
<li><b>Web Service:</b> I created a Render Web Service from the Docker image
<code>ghcr.io/&lt;user&gt;/barber-management-system:latest</code>. I <b>disabled Auto-Deploy</b>,
copied the <b>Deploy Hook URL</b>, and set <code>DATABASE_URL</code> to the
<i>Internal Database URL</i>.</li>
<li><b>GitHub configuration:</b> I set workflow permissions to <b>Read and write</b> and added the
secret <code>RENDER_DEPLOY_HOOK_URL</code>.</li>
<li><b>CI/CD:</b> The workflow <code>.github/workflows/deploy.yml</code> builds the
<code>linux/amd64</code> image, pushes it to <b>GHCR</b> (tags <code>latest</code> and the commit
SHA), and calls the Render Deploy Hook, so Render pulls the new image and redeploys
automatically.</li>
</ol>
<p>Public URL: <a href="{C['render_url']}">{C['render_url']}</a></p>""",
        "shots": [
            ("render-actions.png", "Successful GitHub Actions workflow (build, push to GHCR, Render deploy hook)", True),
            ("render-packages.png", "Pushed container image in the GitHub Packages section", True),
            ("render-app.png", "Working web application on the public Render URL", True),
            ("render-db-vscode.png", "Render PostgreSQL initialized from VS Code", False),
            ("render-settings.png", "Render Web Service settings (Auto-Deploy off, Deploy Hook)", False),
        ],
    },
]


def find_shot(name):
    stem = Path(name).stem
    for ext in (".png", ".jpg", ".jpeg"):
        p = SHOTS / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def img_tag(path):
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f'<img src="data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}">'


def build_html():
    body, fig = [], 0
    for sec in SECTIONS:
        found = [(find_shot(f), cap, req) for f, cap, req in sec["shots"]]
        if not any(p for p, _, _ in found):
            continue
        body.append(f'<section><h2>{sec["title"]}</h2>{sec["description"]}')
        for p, cap, req in found:
            if not p and not req:
                continue
            fig += 1
            body.append("<figure>")
            body.append(img_tag(p) if p else '<div class="missing">Screenshot missing</div>')
            body.append(f"<figcaption>Figure {fig}: {html.escape(cap)}</figcaption></figure>")
        body.append("</section>")
    if not body:
        sys.exit(f"No screenshots found in {SHOTS}. See README for the file names.")

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
 @page {{ size: A4; margin: 16mm 15mm; }}
 body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 10.5pt; color:#222; line-height:1.45 }}
 h1 {{ color:#1d1f24; margin:0 0 6px; border-left:8px solid #c9a24b; padding-left:10px }}
 h2 {{ color:#1d1f24; border-bottom:3px solid #c9a24b; padding-bottom:4px; page-break-before: always }}
 .meta td {{ padding:2px 14px 2px 0; vertical-align:top }}
 code {{ background:#f2f0ea; padding:1px 4px; border-radius:3px; font-size:9pt }}
 li {{ margin-bottom:5px }}
 figure {{ margin:14px 0 20px; page-break-inside: avoid; text-align:center }}
 figure img {{ max-width:100%; max-height:190mm; border:1px solid #ccc; border-radius:4px }}
 figcaption {{ font-size:9pt; color:#555; margin-top:4px; font-style:italic }}
 .missing {{ border:2px dashed #c0392b; color:#c0392b; padding:40px }}
 a {{ color:#2c6fbb }}
</style></head><body>
<h1>{html.escape(C['title'])}</h1>
<table class="meta">
<tr><td><b>Students</b></td><td>{html.escape(C['students'])}</td></tr>
<tr><td><b>Course</b></td><td>{html.escape(C['course'])} ({html.escape(C['teacher'])})</td></tr>
<tr><td><b>Date</b></td><td>{date.today():%d.%m.%Y}</td></tr>
<tr><td><b>Repository</b></td><td><a href="{C['github_repo']}">{C['github_repo']}</a></td></tr>
</table>
<h3>Application</h3>
<p>The <b>Barber Management System</b> is our semester 3-tier project. Staff can manage
<b>barbers</b>, <b>services</b> (duration and price), and customer <b>appointments</b>
(scheduled, completed or cancelled). The dashboard shows today's and upcoming appointments and
the revenue from completed visits.</p>
<ul>
<li><b>Presentation tier:</b> Flask Jinja2 HTML templates.</li>
<li><b>Application tier:</b> Python/Flask served by gunicorn. HTML pages plus a REST API with full CRUD:
<code>GET/POST /api/&lt;resource&gt;</code> and <code>GET/PUT/DELETE /api/&lt;resource&gt;/&lt;id&gt;</code>
for barbers, services and appointments.</li>
<li><b>Data tier:</b> PostgreSQL 16.</li>
</ul>
<p>All database settings come from environment variables (<code>DATABASE_URL</code> or
<code>DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD</code>, plus <code>DB_SSLMODE</code>), so the
same Docker image runs locally (<code>docker compose up</code>), on Azure and on Render.
<code>/health</code> returns <code>{{"status": "ok", "db": "connected"}}</code>.</p>
{''.join(body)}
</body></html>"""


def main():
    out_html, out_pdf = HERE / "report.html", HERE / "Report.pdf"
    out_html.write_text(build_html(), encoding="utf-8")
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found. Open {out_html} in a browser and use Print → Save as PDF.")
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out_pdf}", out_html.as_uri()],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"Created {out_pdf}")


if __name__ == "__main__":
    main()
