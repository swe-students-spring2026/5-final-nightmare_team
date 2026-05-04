"""Flask web application with MongoDB Atlas connection."""

import base64
import os
import re
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["webapp"]

users_col = db["users"]
songs_col = db["songs"]
events_col = db["events"]
playlists_col = db["playlists"]

users_col.create_index("username", unique=True)

ALLOWED_GENRES = {
    "Pop", "Rock", "Hip-Hop", "R&B", "Electronic", "Indie", "Jazz",
    "Classical", "Metal", "Folk", "Soul", "Lo-fi", "Punk", "Reggae", "Country",
}
ALLOWED_ERAS = {"any", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


# ── Helpers ──────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    return users_col.find_one({"_id": ObjectId(session["user_id"])})


def validate_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def validate_playlist_size(size):
    return isinstance(size, int) and 5 <= size <= 50


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/settings")
def settings():
    """Render the settings page (requires login)."""
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("settings.html")


@app.route("/login")
def login_page():
    """Render the login page."""
    return render_template("login.html")


@app.route("/register")
def register_page():
    """Render the register page."""
    return render_template("register.html")


# ── Auth API ──────────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username:
        return jsonify({"error": "Username is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if users_col.find_one({"username": username}):
        return jsonify({"error": "Username already taken"}), 409

    doc = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "display_name": data.get("display_name", "").strip(),
        "email": data.get("email", "").strip(),
        "avatar": None,
        "settings": {
            "default_playlist_size": 20,
            "preferred_genres": [],
            "default_era": "any",
            "auto_save": False,
            "public_playlists": False,
            "spotify_connected": False,
        },
        "generation_history": [],
        "created_at": datetime.now(timezone.utc),
    }
    result = users_col.insert_one(doc)
    session["user_id"] = str(result.inserted_id)
    return jsonify({"success": True, "data": {"username": username}}), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Log in an existing user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = users_col.find_one({"username": username})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"] = str(user["_id"])
    return jsonify({"success": True, "data": {"username": username}}), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Log out the current user."""
    session.clear()
    return jsonify({"success": True}), 200


# ── Settings API ──────────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    """Return the current user's settings."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.pop("password_hash", None)
    user["_id"] = str(user["_id"])
    return jsonify({"success": True, "data": user}), 200


@app.route("/api/settings", methods=["PUT"])
@login_required
def update_settings():
    """Update the current user's settings (partial update)."""
    data = request.get_json(silent=True) or {}
    set_fields = {}

    if "display_name" in data:
        name = str(data["display_name"])[:100]
        set_fields["display_name"] = name

    if "email" in data:
        email = str(data["email"]).strip()
        if email and not validate_email(email):
            return jsonify({"error": "Invalid email address"}), 400
        set_fields["email"] = email

    nested = data.get("settings", {})

    if "default_playlist_size" in nested:
        size = nested["default_playlist_size"]
        if not validate_playlist_size(size):
            return jsonify({"error": "Playlist size must be an integer between 5 and 50"}), 400
        set_fields["settings.default_playlist_size"] = size

    if "preferred_genres" in nested:
        genres = nested["preferred_genres"]
        if not isinstance(genres, list) or not all(g in ALLOWED_GENRES for g in genres):
            return jsonify({"error": "Invalid genre selection"}), 400
        set_fields["settings.preferred_genres"] = genres

    if "default_era" in nested:
        era = nested["default_era"]
        if era not in ALLOWED_ERAS:
            return jsonify({"error": "Invalid era value"}), 400
        set_fields["settings.default_era"] = era

    if "auto_save" in nested:
        set_fields["settings.auto_save"] = bool(nested["auto_save"])

    if "public_playlists" in nested:
        set_fields["settings.public_playlists"] = bool(nested["public_playlists"])

    if set_fields:
        users_col.update_one(
            {"_id": ObjectId(session["user_id"])},
            {"$set": set_fields},
        )

    return jsonify({"success": True, "data": set_fields}), 200


@app.route("/api/settings/avatar", methods=["POST"])
@login_required
def update_avatar():
    """Upload a new avatar (base64 data-url)."""
    data = request.get_json(silent=True) or {}
    avatar = data.get("avatar", "")

    if not isinstance(avatar, str) or not avatar.startswith("data:image/"):
        return jsonify({"error": "Invalid avatar format"}), 400

    try:
        _, encoded = avatar.split(",", 1)
        decoded = base64.b64decode(encoded)
    except Exception:  # pylint: disable=broad-exception-caught
        return jsonify({"error": "Invalid base64 data"}), 400

    if len(decoded) > MAX_AVATAR_BYTES:
        return jsonify({"error": "Avatar must be under 2 MB"}), 413

    users_col.update_one(
        {"_id": ObjectId(session["user_id"])},
        {"$set": {"avatar": avatar}},
    )
    return jsonify({"success": True}), 200


@app.route("/api/settings/history", methods=["DELETE"])
@login_required
def clear_history():
    """Clear the current user's generation history."""
    users_col.update_one(
        {"_id": ObjectId(session["user_id"])},
        {"$set": {"generation_history": []}},
    )
    return jsonify({"success": True}), 200


@app.route("/api/settings/account", methods=["DELETE"])
@login_required
def delete_account():
    """Permanently delete the current user's account."""
    users_col.delete_one({"_id": ObjectId(session["user_id"])})
    session.clear()
    return jsonify({"success": True}), 200


# ── Health & existing routes ──────────────────────────────────────────────────

@app.route("/health")
def health():
    """Check MongoDB connectivity and return status."""
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "connected"})
    except Exception as e:  # pylint: disable=broad-exception-caught
        return jsonify({"status": "error", "mongo": str(e)}), 500


@app.route("/api/playlists", methods=["POST"])
def save_playlist():
    """Save a generated playlist to MongoDB."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("tracks"), list):
        return jsonify({"ok": False, "message": "Invalid payload"}), 400
    doc = {
        "tracks": data["tracks"],
        "savedAt": data.get("savedAt", datetime.now(timezone.utc).isoformat()),
        "createdAt": datetime.now(timezone.utc),
    }
    result = playlists_col.insert_one(doc)
    return jsonify({"ok": True, "id": str(result.inserted_id)}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
