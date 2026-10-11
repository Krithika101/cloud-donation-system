import math
import os

import psycopg
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "cloud-donation-secret-key")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE_URL = os.getenv("DATABASE_URL")

DEMO_USERS = {
    "admin@donation.com": {
        "id": 1,
        "name": "Admin User",
        "email": "admin@donation.com",
        "password": "admin123",
        "role": "admin",
    },
    "donor@example.com": {
        "id": 2,
        "name": "Demo Donor",
        "email": "donor@example.com",
        "password": "donor123",
        "role": "donor",
    },
}

DEMO_CAUSES = [
    {
        "id": 1,
        "title": "Community Food Drive",
        "description": "Provide food packages to local families.",
        "goal": 30000.0,
        "raised": 18500.0,
    },
    {
        "id": 2,
        "title": "Medical Aid",
        "description": "Support people who need help with medical costs.",
        "goal": 40000.0,
        "raised": 22675.0,
    },
    {
        "id": 3,
        "title": "Education Support",
        "description": "Help students access learning materials.",
        "goal": 500000.0,
        "raised": 198200.0,
    },
    {
        "id": 4,
        "title": "Clean Water Access",
        "description": "Help communities access safe drinking water and sanitation.",
        "goal": 80000.0,
        "raised": 12400.0,
    },
    {
        "id": 5,
        "title": "Emergency Shelter",
        "description": "Provide safe shelter and essential supplies after emergencies.",
        "goal": 60000.0,
        "raised": 7600.0,
    },
    {
        "id": 6,
        "title": "Skills and Livelihoods",
        "description": "Support practical training and small-business opportunities.",
        "goal": 50000.0,
        "raised": 5400.0,
    },
]


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(DATABASE_URL, autocommit=True)


def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_users (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'donor'
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS causes (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        goal_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS donations (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        cause_id BIGINT NOT NULL,
                        amount NUMERIC(12,2) NOT NULL,
                        donated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    DELETE FROM app_users
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id, ROW_NUMBER() OVER (PARTITION BY lower(email) ORDER BY id) AS rn
                            FROM app_users
                        ) t
                        WHERE rn > 1
                    )
                    """
                )

                cur.execute(
                    """
                    DELETE FROM causes
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id, ROW_NUMBER() OVER (PARTITION BY lower(name) ORDER BY id) AS rn
                            FROM causes
                        ) t
                        WHERE rn > 1
                    )
                    """
                )

                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_app_users_email ON app_users (lower(email))"
                )
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_causes_name ON causes (lower(name))"
                )

                cur.execute(
                    """
                    INSERT INTO causes (name, description, goal_amount, is_active)
                    SELECT v.name, v.description, v.goal_amount, v.is_active
                    FROM (
                        VALUES
                            ('Community Food Drive', 'Provide food packages to local families.', 30000, TRUE),
                            ('Medical Aid', 'Support people who need help with medical costs.', 40000, TRUE),
                            ('Education Support', 'Help students access learning materials.', 500000, TRUE),
                            ('Clean Water Access', 'Help communities access safe drinking water and sanitation.', 80000, TRUE),
                            ('Emergency Shelter', 'Provide safe shelter and essential supplies after emergencies.', 60000, TRUE),
                            ('Skills and Livelihoods', 'Support practical training and small-business opportunities.', 50000, TRUE)
                    ) AS v(name, description, goal_amount, is_active)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM causes WHERE lower(name) = lower(v.name)
                    )
                    """
                )

                cur.execute(
                    """
                    INSERT INTO app_users (name, email, password_hash, role)
                    SELECT 'Admin User', 'admin@donation.com', 'admin123', 'admin'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM app_users WHERE lower(email) = lower('admin@donation.com')
                    )
                    """
                )
    except Exception:
        pass


init_db()


def fetch_causes():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.name AS title, c.description,
                           c.goal_amount AS goal,
                           COALESCE(SUM(d.amount), 0) AS raised
                    FROM causes c
                    LEFT JOIN donations d ON d.cause_id = c.id
                    WHERE c.is_active = TRUE
                    GROUP BY lower(c.name), c.id, c.name, c.description, c.goal_amount
                    ORDER BY MIN(c.id)
                    """
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "goal": float(row[3]),
                        "raised": float(row[4]),
                    }
                    for row in rows
                ]
    except Exception:
        return DEMO_CAUSES


def fetch_users():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name, email, role FROM app_users ORDER BY id")
                rows = cur.fetchall()
                return [{"name": row[0], "email": row[1], "role": row[2]} for row in rows]
    except Exception:
        return []


def fetch_user_by_email(email):
    normalized_email = (email or "").strip().lower()
    if normalized_email in DEMO_USERS:
        return DEMO_USERS[normalized_email]

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, email, password_hash, role FROM app_users WHERE lower(email) = %s",
                    (normalized_email,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "password": row[3],
                    "role": row[4],
                }
    except Exception:
        return DEMO_USERS.get(normalized_email)


def fetch_donations_for_user(email):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.name, d.amount
                    FROM donations d
                    JOIN app_users u ON u.id = d.user_id
                    JOIN causes c ON c.id = d.cause_id
                    WHERE u.email = %s
                    ORDER BY d.donated_at DESC
                    """,
                    (email,),
                )
                return [{"cause": row[0], "amount": float(row[1])} for row in cur.fetchall()]
    except Exception:
        return []


def fetch_all_donations():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.name, c.name, d.amount
                    FROM donations d
                    JOIN app_users u ON u.id = d.user_id
                    JOIN causes c ON c.id = d.cause_id
                    ORDER BY d.donated_at DESC
                    """
                )
                return [{"name": row[0], "cause": row[1], "amount": float(row[2])} for row in cur.fetchall()]
    except Exception:
        return []


def fetch_donation_history_by_email(email):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.name, d.amount, d.donated_at
                    FROM donations d
                    JOIN app_users u ON u.id = d.user_id
                    JOIN causes c ON c.id = d.cause_id
                    WHERE u.email = %s
                    ORDER BY d.donated_at DESC
                    """,
                    (email,),
                )
                return [
                    {"cause": row[0], "amount": float(row[1]), "date": row[2]}
                    for row in cur.fetchall()
                ]
    except Exception:
        return []


def fetch_donation_history(limit=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT u.name, c.name, d.amount, d.donated_at
                    FROM donations d
                    JOIN app_users u ON u.id = d.user_id
                    JOIN causes c ON c.id = d.cause_id
                    ORDER BY d.donated_at DESC
                """
                params = ()
                if limit is not None:
                    query += " LIMIT %s"
                    params = (limit,)
                cur.execute(query, params)
                return [
                    {"donor": row[0], "cause": row[1], "amount": float(row[2]), "date": row[3]}
                    for row in cur.fetchall()
                ]
    except Exception:
        return []


def fetch_dashboard_summary():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(SUM(amount), 0) FROM donations")
                total_raised = float(cur.fetchone()[0] or 0)

                cur.execute("SELECT COUNT(DISTINCT user_id) FROM donations")
                total_donors = int(cur.fetchone()[0] or 0)

                cur.execute("SELECT COUNT(*) FROM causes WHERE is_active = TRUE")
                total_causes = int(cur.fetchone()[0] or 0)

                return {
                    "total_raised": total_raised,
                    "total_donors": total_donors,
                    "total_causes": total_causes,
                }
    except Exception:
        total_raised = sum(cause["raised"] for cause in DEMO_CAUSES)
        return {
            "total_raised": total_raised,
            "total_donors": 124,
            "total_causes": len(DEMO_CAUSES),
        }


def fetch_recent_donations(limit=5):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.name, c.name, d.amount, d.donated_at
                    FROM donations d
                    JOIN app_users u ON u.id = d.user_id
                    JOIN causes c ON c.id = d.cause_id
                    ORDER BY d.donated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [{
                    "name": row[0],
                    "cause": row[1],
                    "amount": float(row[2]),
                    "time": row[3],
                } for row in cur.fetchall()]
    except Exception:
        return []


def insert_user(name, email, password, role="donor"):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (name, email, password, role),
                )
                return True
    except Exception:
        return False


def insert_cause(name, description, goal_amount):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO causes (name, description, goal_amount, is_active) VALUES (%s, %s, %s, TRUE)",
                    (name, description, goal_amount),
                )
    except psycopg.errors.UniqueViolation:
        return "duplicate"
    except Exception:
        return "error"
    return "created"


def insert_donation(user_email, cause_id, amount):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM app_users WHERE email = %s",
                    (user_email,),
                )
                user_row = cur.fetchone()
                if not user_row:
                    return False

                user_id = user_row[0]
                cur.execute(
                    "INSERT INTO donations (user_id, cause_id, amount) VALUES (%s, %s, %s)",
                    (user_id, cause_id, amount),
                )
                return True
    except Exception:
        return False


@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template(
        "index.html",
        causes=fetch_causes(),
        summary=fetch_dashboard_summary(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    user = fetch_user_by_email(email)

    if user and user["password"] == password:
        session["user"] = {
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        }
        return redirect(url_for("dashboard"))

    return render_template("login.html", error="Invalid email or password.")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not name or not email or not password:
            return render_template("register.html", error="Please fill in all fields.")

        if fetch_user_by_email(email):
            return render_template("register.html", error="This email is already registered.")

        if not insert_user(name, email, password, "donor"):
            return render_template("register.html", error="Registration failed. Please try again.")

        session["user"] = {
            "email": email,
            "name": name,
            "role": "donor",
        }
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("home"))

    current_user = session["user"]
    user_donations = fetch_donations_for_user(current_user["email"])
    all_causes = fetch_causes()
    summary = fetch_dashboard_summary()

    if current_user["role"] == "admin":
        return render_template(
            "admin_dashboard.html",
            user=current_user,
            users=fetch_users(),
            donations=fetch_all_donations(),
            causes=all_causes,
            summary=summary,
            recent_donations=fetch_recent_donations(5),
        )

    return render_template(
        "donor_dashboard.html",
        user=current_user,
        donations=user_donations,
        causes=all_causes,
        summary=summary,
        recent_donations=fetch_recent_donations(5),
    )


@app.route("/admin/causes", methods=["POST"])
def create_cause():
    current_user = session.get("user")
    if not current_user:
        return redirect(url_for("home"))
    if current_user.get("role") != "admin":
        abort(403)

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    try:
        goal_amount = float(request.form.get("goal_amount", ""))
    except (TypeError, ValueError):
        goal_amount = 0

    if not name or not description or not math.isfinite(goal_amount) or goal_amount <= 0:
        flash("Enter a cause name, description, and a goal greater than zero.", "error")
        return redirect(url_for("dashboard"))

    result = insert_cause(name, description, goal_amount)
    if result == "created":
        flash("Cause added and saved to the cloud database.", "success")
    elif result == "duplicate":
        flash("A cause with that name already exists.", "error")
    else:
        flash("The cause could not be saved. Check the cloud database connection and try again.", "error")
    return redirect(url_for("dashboard"))


@app.route("/causes")
def causes_page():
    search_query = (request.args.get("search") or "").strip().lower()
    causes = fetch_causes()

    if search_query:
        causes = [
            cause
            for cause in causes
            if search_query in cause["title"].lower() or search_query in cause["description"].lower()
        ]

    return render_template(
        "causes.html",
        causes=causes,
        summary=fetch_dashboard_summary(),
        search_query=request.args.get("search", ""),
    )


@app.route("/history")
def donation_history():
    if "user" not in session:
        return redirect(url_for("home"))

    current_user = session["user"]
    if current_user["role"] == "admin":
        history = fetch_donation_history()
        total_amount = sum(item["amount"] for item in history)
        return render_template(
            "history.html",
            user=current_user,
            title="Donation History",
            donations=history,
            total_amount=total_amount,
            summary=fetch_dashboard_summary(),
        )

    history = fetch_donation_history_by_email(current_user["email"])
    total_amount = sum(item["amount"] for item in history)
    return render_template(
        "history.html",
        user=current_user,
        title="My Donation History",
        donations=history,
        total_amount=total_amount,
        summary=fetch_dashboard_summary(),
    )


@app.route("/donate", methods=["GET", "POST"])
def donate():
    if "user" not in session:
        return redirect(url_for("home"))

    current_user = session["user"]
    selected_cause_id = request.args.get("cause_id", type=int)

    if current_user.get("role") == "admin" and selected_cause_id is None:
        return redirect(url_for("dashboard"))

    if current_user.get("role") == "admin" and request.method == "POST":
        return redirect(url_for("dashboard"))

    all_causes = fetch_causes()

    if request.method == "POST":
        cause_id = int(request.form.get("cause_id", 0))
        amount = float(request.form.get("amount", 0) or 0)

        if amount <= 0:
            return render_template("donate.html", causes=all_causes, user=current_user, selected_cause_id=cause_id, error="Donation amount must be greater than zero.")

        cause = next((item for item in all_causes if item["id"] == cause_id), None)
        if not cause:
            return render_template("donate.html", causes=all_causes, user=current_user, selected_cause_id=cause_id, error="Selected cause was not found.")

        if not insert_donation(current_user["email"], cause_id, amount):
            return render_template("donate.html", causes=all_causes, user=current_user, selected_cause_id=cause_id, error="Donation failed. Please try again.")

        return redirect(url_for("dashboard"))

    return render_template(
        "donate.html",
        causes=all_causes,
        user=current_user,
        selected_cause_id=selected_cause_id,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/index")
def index_page():
    return render_template("index.html", causes=fetch_causes(), summary=fetch_dashboard_summary())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)