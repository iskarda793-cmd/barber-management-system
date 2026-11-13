"""
Barber Management System: 3-tier cloud application

  Presentation tier : Jinja2 HTML templates (templates/)
  Application tier  : Flask + gunicorn (this file). HTML pages + REST API (CRUD)
  Data tier         : PostgreSQL (db/schema.sql)

All database settings come from environment variables (never hardcoded):
  DATABASE_URL                     e.g. Render: postgresql://user:pass@host:5432/barberdb
  or DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD   (Azure, docker compose)
  DB_SSLMODE   (optional)          "require" for Azure PostgreSQL Flexible Server
  DB_TIMEZONE  (optional)          session time zone, default Europe/Warsaw
  APP_PLATFORM (optional)          text shown in the UI, e.g. "Render"
"""
import os
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

# --------------------------------------------------------------------------
# Configuration (environment variables only)
# --------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
# Accept SQLAlchemy-style URLs too (postgresql+psycopg2://...)
DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://", 1)
DB_SSLMODE = os.environ.get("DB_SSLMODE", "").strip()
DB_TIMEZONE = os.environ.get("DB_TIMEZONE", "Europe/Warsaw").strip()
APP_PLATFORM = (
    os.environ.get("APP_PLATFORM", "").strip()
    or ("Render" if os.environ.get("RENDER") else "")
    or ("Azure Container Apps" if os.environ.get("CONTAINER_APP_NAME") else "")
    or "Docker"
)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "barberdb"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

if DATABASE_URL:
    # Only used to display host / database name in the UI (never the password)
    _url = urlparse(DATABASE_URL)
    DB_CONFIG["host"] = _url.hostname or DB_CONFIG["host"]
    DB_CONFIG["dbname"] = (_url.path or "/").lstrip("/") or DB_CONFIG["dbname"]

SCHEMA_FILE = Path(__file__).parent / "db" / "schema.sql"

# Whitelist of tables (resources) and the columns a client may write.
# Table/column names are ONLY taken from here, so building SQL with them is safe;
# all values are always passed as query parameters (%s).
RESOURCES = {
    "barbers": {
        "columns": ("name", "phone", "specialty"),
        "required": ("name",),
        "order_by": "name",
    },
    "services": {
        "columns": ("name", "duration_minutes", "price"),
        "required": ("name", "duration_minutes", "price"),
        "order_by": "name",
    },
    "appointments": {
        "columns": (
            "customer_name", "customer_phone", "barber_id", "service_id",
            "appointment_time", "status", "notes",
        ),
        "required": ("customer_name", "barber_id", "service_id", "appointment_time"),
        "order_by": "appointment_time",
    },
}

# Appointments are shown together with the barber and service names
SELECT_SQL = {
    "barbers": "SELECT * FROM barbers",
    "services": "SELECT * FROM services",
    "appointments": """
        SELECT a.*, b.name AS barber_name, s.name AS service_name,
               s.price, s.duration_minutes
        FROM appointments a
        JOIN barbers  b ON b.id = a.barber_id
        JOIN services s ON s.id = a.service_id
    """,
}

STATUSES = ("scheduled", "completed", "cancelled")


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_connection():
    """Open a new connection to PostgreSQL."""
    extra = {"connect_timeout": 5}
    if DB_SSLMODE:
        extra["sslmode"] = DB_SSLMODE
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, **extra)
    return psycopg2.connect(**DB_CONFIG, **extra)


@contextmanager
def db_cursor():
    """Cursor returning rows as dicts. Commits on success, rolls back on error."""
    conn = get_connection()
    try:
        with conn:  # transaction
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if DB_TIMEZONE:
                    cur.execute("SET LOCAL TIME ZONE %s;", (DB_TIMEZONE,))
                yield cur
    finally:
        conn.close()


def init_db(retries: int = 3, delay: int = 2):
    """Create the tables (db/schema.sql) if they do not exist yet."""
    for attempt in range(1, retries + 1):
        try:
            with db_cursor() as cur:
                # Several gunicorn workers start at once: serialize schema creation
                cur.execute("SELECT pg_advisory_xact_lock(424242);")
                cur.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
            print("Database schema is ready.", flush=True)
            return
        except psycopg2.OperationalError as exc:
            print(f"[{attempt}/{retries}] Database not ready yet: {exc}".strip(), flush=True)
            time.sleep(delay)
    # Do not crash the container: pages and /health will show the DB error,
    # which makes troubleshooting cloud configuration easier.
    print("WARNING: could not initialize the database.", flush=True)


def list_rows(resource):
    order = RESOURCES[resource]["order_by"]
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM ({SELECT_SQL[resource]}) t ORDER BY {order}, id;")
        return cur.fetchall()


def get_row(resource, row_id):
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM ({SELECT_SQL[resource]}) t WHERE id = %s;", (row_id,))
        return cur.fetchone()


def create_row(resource, data):
    cols = list(data)
    placeholders = ", ".join(["%s"] * len(cols))
    with db_cursor() as cur:
        cur.execute(
            f"INSERT INTO {resource} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id;",
            [data[c] for c in cols],
        )
        return cur.fetchone()["id"]


def update_row(resource, row_id, data):
    cols = list(data)
    assignments = ", ".join(f"{c} = %s" for c in cols)
    with db_cursor() as cur:
        cur.execute(
            f"UPDATE {resource} SET {assignments} WHERE id = %s RETURNING id;",
            [data[c] for c in cols] + [row_id],
        )
        return cur.fetchone() is not None


def delete_row(resource, row_id):
    with db_cursor() as cur:
        cur.execute(f"DELETE FROM {resource} WHERE id = %s RETURNING id;", (row_id,))
        return cur.fetchone() is not None


# --------------------------------------------------------------------------
# Validation / conversion
# --------------------------------------------------------------------------
class ValidationError(ValueError):
    pass


def clean(resource, data, partial=False):
    """Validate form/JSON input and convert it to Python types.

    partial=True is used by the REST API PUT/PATCH (only send the fields to change).
    """
    spec = RESOURCES[resource]
    out = {}
    for col in spec["columns"]:
        if col not in data:
            continue
        raw = data[col]
        value = raw.strip() if isinstance(raw, str) else raw
        if value == "":
            value = None
        if value is None:
            if col == "status":  # let the DB default ('scheduled') apply
                continue
            out[col] = None
            continue
        try:
            if col in ("barber_id", "service_id", "duration_minutes"):
                value = int(value)
            elif col == "price":
                value = Decimal(str(value))
            elif col == "appointment_time":
                value = datetime.fromisoformat(str(value))
        except (ValueError, InvalidOperation):
            raise ValidationError(f"Invalid value for '{col}': {raw!r}")
        if col == "duration_minutes" and value <= 0:
            raise ValidationError("Duration must be greater than 0.")
        if col == "price" and value < 0:
            raise ValidationError("Price cannot be negative.")
        if col == "status" and value not in STATUSES:
            raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}.")
        out[col] = value

    required = spec["required"]
    missing = [c for c in required if (c in out or not partial) and out.get(c) is None]
    if missing:
        raise ValidationError("Missing required field(s): " + ", ".join(missing))
    if not out:
        raise ValidationError("No valid fields provided.")
    return out


def integrity_message(exc):
    """Human readable message for database constraint errors."""
    if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        if "still referenced" in str(exc):
            return "Cannot delete: this record is used by existing appointments."
        return "The selected barber or service does not exist."
    return f"Database constraint error: {exc.diag.message_primary}"


def to_json(row):
    """Make a DB row JSON friendly (ISO dates, numbers instead of Decimal)."""
    out = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        out[key] = value
    return out


def check_resource(resource):
    if resource not in RESOURCES:
        abort(404)


# --------------------------------------------------------------------------
# Presentation tier: HTML pages
# --------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {
        "platform": APP_PLATFORM,
        "db_host": DB_CONFIG["host"],
        "db_name": DB_CONFIG["dbname"],
        "hostname": os.environ.get("HOSTNAME", "local"),
    }


@app.get("/")
def dashboard():
    stats, upcoming, db_version, db_error = {}, [], "", None
    try:
        with db_cursor() as cur:
            cur.execute("SELECT version() AS v;")
            db_version = cur.fetchone()["v"]
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM barbers)  AS barbers,
                  (SELECT COUNT(*) FROM services) AS services,
                  (SELECT COUNT(*) FROM appointments
                     WHERE appointment_time::date = CURRENT_DATE
                       AND status <> 'cancelled') AS today,
                  (SELECT COUNT(*) FROM appointments
                     WHERE status = 'scheduled'
                       AND appointment_time >= LOCALTIMESTAMP) AS upcoming,
                  (SELECT COALESCE(SUM(s.price), 0) FROM appointments a
                     JOIN services s ON s.id = a.service_id
                     WHERE a.status = 'completed') AS revenue;
                """
            )
            stats = cur.fetchone()
            cur.execute(
                f"""SELECT * FROM ({SELECT_SQL['appointments']}) t
                    WHERE status = 'scheduled' AND appointment_time >= LOCALTIMESTAMP
                    ORDER BY appointment_time LIMIT 8;"""
            )
            upcoming = cur.fetchall()
    except psycopg2.Error as exc:
        db_error = str(exc)
    return render_template(
        "index.html", stats=stats, upcoming=upcoming,
        db_version=db_version, db_error=db_error,
    )


@app.get("/<resource>")
@app.get("/<resource>/<int:row_id>/edit")
def page(resource, row_id=None):
    """List page with an add form (or an edit form when row_id is given)."""
    check_resource(resource)
    context = {"error": request.args.get("error"), "editing": None, "statuses": STATUSES}
    try:
        context["rows"] = list_rows(resource)
        if row_id is not None:
            context["editing"] = get_row(resource, row_id)
            if context["editing"] is None:
                abort(404)
        if resource == "appointments":
            context["barbers"] = list_rows("barbers")
            context["services"] = list_rows("services")
    except psycopg2.Error as exc:
        return render_template("db_error.html", db_error=str(exc)), 503
    return render_template(f"{resource}.html", **context)


@app.post("/<resource>")
@app.post("/<resource>/<int:row_id>")
def page_save(resource, row_id=None):
    """Create (no row_id) or update (row_id) from an HTML form."""
    check_resource(resource)
    try:
        data = clean(resource, request.form)
        if row_id is None:
            create_row(resource, data)
        elif not update_row(resource, row_id, data):
            abort(404)
    except ValidationError as exc:
        return redirect(url_for("page", resource=resource, row_id=row_id, error=str(exc)))
    except psycopg2.IntegrityError as exc:
        return redirect(url_for("page", resource=resource, row_id=row_id,
                                error=integrity_message(exc)))
    return redirect(url_for("page", resource=resource))


@app.post("/<resource>/<int:row_id>/delete")
def page_delete(resource, row_id):
    check_resource(resource)
    try:
        delete_row(resource, row_id)
    except psycopg2.IntegrityError as exc:
        return redirect(url_for("page", resource=resource, error=integrity_message(exc)))
    return redirect(url_for("page", resource=resource))


# --------------------------------------------------------------------------
# Application tier: REST API (CRUD)
#   GET    /api/<resource>          list
#   POST   /api/<resource>          create
#   GET    /api/<resource>/<id>     read one
#   PUT    /api/<resource>/<id>     update (partial updates allowed)
#   DELETE /api/<resource>/<id>     delete
# resource = barbers | services | appointments
# --------------------------------------------------------------------------
@app.get("/api/<resource>")
def api_list(resource):
    check_resource(resource)
    return jsonify([to_json(r) for r in list_rows(resource)])


@app.post("/api/<resource>")
def api_create(resource):
    check_resource(resource)
    try:
        row_id = create_row(resource, clean(resource, request.get_json(silent=True) or {}))
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    except psycopg2.IntegrityError as exc:
        return jsonify(error=integrity_message(exc)), 409
    return jsonify(to_json(get_row(resource, row_id))), 201


@app.get("/api/<resource>/<int:row_id>")
def api_get(resource, row_id):
    check_resource(resource)
    row = get_row(resource, row_id)
    if row is None:
        return jsonify(error="Not found"), 404
    return jsonify(to_json(row))


@app.route("/api/<resource>/<int:row_id>", methods=["PUT", "PATCH"])
def api_update(resource, row_id):
    check_resource(resource)
    try:
        data = clean(resource, request.get_json(silent=True) or {}, partial=True)
        if not update_row(resource, row_id, data):
            return jsonify(error="Not found"), 404
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    except psycopg2.IntegrityError as exc:
        return jsonify(error=integrity_message(exc)), 409
    return jsonify(to_json(get_row(resource, row_id)))


@app.delete("/api/<resource>/<int:row_id>")
def api_delete(resource, row_id):
    check_resource(resource)
    try:
        if not delete_row(resource, row_id):
            return jsonify(error="Not found"), 404
    except psycopg2.IntegrityError as exc:
        return jsonify(error=integrity_message(exc)), 409
    return "", 204


@app.errorhandler(psycopg2.OperationalError)
def handle_db_down(exc):
    if request.path.startswith("/api/"):
        return jsonify(error="Database unavailable", detail=str(exc)), 503
    return render_template("db_error.html", db_error=str(exc)), 503


# --------------------------------------------------------------------------
# Health check (monitoring / Kubernetes readiness probe)
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    try:
        with db_cursor() as cur:
            cur.execute("SELECT 1;")
        return jsonify(status="ok", db="connected"), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify(status="error", db="disconnected", detail=str(exc)), 503


# Create tables when the module is loaded (works with gunicorn too)
init_db(retries=int(os.environ.get("DB_INIT_RETRIES", 3)))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
