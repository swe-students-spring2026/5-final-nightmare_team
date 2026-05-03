"""Flask web application with MongoDB Atlas connection."""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import requests as http
from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

MONGO_URI = os.environ.get("MONGO_URI", "")
ML_APP_URL = os.environ.get("ML_APP_URL", "http://ml-app:8000")

client = MongoClient(MONGO_URI)
db = client["webapp"]

users_col = db["users"]
songs_col = db["songs"]
events_col = db["events"]
playlists_col = db["playlists"]


AUTH_MESSAGE_MAP = {
    "logged_in": "Signed in successfully.",
    "registered": "Account created successfully. You are now signed in.",
    "logged_out": "Signed out successfully.",
    "missing_login_fields": "Enter both your email and password to sign in.",
    "missing_register_fields": (
        "Name, email, and password are all required to create an account."
    ),
    "invalid_credentials": (
        "That email and password combination does not match our records."
    ),
    "user_exists": "An account with that email already exists. Try signing in instead.",
    "weak_password": "Use a password with at least 8 characters.",
}


def normalize_email(value):
    """Normalize an email address before lookup/storage."""
    return value.strip().lower()


def get_auth_message(code):
    """Translate a short auth status code into user-facing text."""
    return AUTH_MESSAGE_MAP.get(code)


def build_session_user(user_doc):
    """Store only the minimum user data needed in the Flask session."""
    return {
        "id": str(user_doc.get("_id", "")),
        "name": user_doc.get("name") or user_doc.get("email") or "Listener",
        "email": user_doc.get("email", ""),
    }


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Render and process the email/password login form."""
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")

        if not email or not password:
            return redirect(url_for("login", error="missing_login_fields", email=email))

        user_doc = users_col.find_one({"email": email})
        if not user_doc or not check_password_hash(
            user_doc.get("passwordHash", ""), password
        ):
            return redirect(url_for("login", error="invalid_credentials", email=email))

        session["auth_user"] = build_session_user(user_doc)
        return redirect(url_for("index"))

    return render_template(
        "login.html",
        auth_error=get_auth_message(request.args.get("error")),
        auth_success=get_auth_message(request.args.get("success")),
        current_user=session.get("auth_user"),
        login_email=request.args.get("email", ""),
    )


@app.route("/register", methods=["POST"])
def register():
    """Create a basic email/password user in MongoDB."""
    name = request.form.get("name", "").strip()
    email = normalize_email(request.form.get("email", ""))
    password = request.form.get("password", "")

    if not name or not email or not password:
        return redirect(url_for("login", error="missing_register_fields"))

    if len(password) < 8:
        return redirect(url_for("login", error="weak_password"))

    if users_col.find_one({"email": email}):
        return redirect(url_for("login", error="user_exists", email=email))

    user_doc = {
        "name": name,
        "email": email,
        "passwordHash": generate_password_hash(password),
        "createdAt": datetime.now(timezone.utc),
    }
    result = users_col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    session["auth_user"] = build_session_user(user_doc)
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    """Clear the signed-in user from the session."""
    session.pop("auth_user", None)
    return redirect(url_for("login", success="logged_out"))


@app.route("/health")
def health():
    """Check MongoDB connectivity and return status."""
    # pylint: disable=invalid-name
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "connected"})
    except Exception as e:  # pylint: disable=broad-exception-caught
        return jsonify({"status": "error", "mongo": str(e)}), 500
    # pylint: enable=invalid-name


@app.route("/settings")
def settings():
    """Render the settings page."""
    return render_template("settings.html")


@app.route("/api/recommendations/<user_id>")
def get_recommendations(user_id):
    """Proxy recommendation request to the ml-app service."""
    k = request.args.get("k", 10)
    try:
        resp = http.get(
            f"{ML_APP_URL}/recommendations/{user_id}",
            params={"k": k},
            timeout=5,
        )
        return jsonify(resp.json()), resp.status_code
    except http.exceptions.RequestException as exc:
        return (
            jsonify(
                {"error": "Recommendation service unavailable", "detail": str(exc)}
            ),
            503,
        )


@app.route("/api/playlists", methods=["POST"])
def save_playlist():
    """Save a generated playlist to MongoDB and record save events in ml-app."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("tracks"), list):
        return jsonify({"ok": False, "message": "Invalid payload"}), 400

    doc = {
        "user_id": data.get("user_id") or None,
        "tracks": data["tracks"],
        "savedAt": data.get("savedAt", datetime.now(timezone.utc).isoformat()),
        "createdAt": datetime.now(timezone.utc),
    }
    result = playlists_col.insert_one(doc)

    user_id = data.get("user_id")
    if user_id:
        for track in data["tracks"]:
            song_id = track.get("song_id") if isinstance(track, dict) else None
            if song_id:
                try:
                    http.post(
                        f"{ML_APP_URL}/events",
                        json={
                            "user_id": user_id,
                            "song_id": song_id,
                            "event_type": "save",
                        },
                        timeout=3,
                    )
                except http.exceptions.RequestException:
                    pass  # best-effort: don't fail the save if ml-app is unreachable

    return jsonify({"ok": True, "id": str(result.inserted_id)}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
