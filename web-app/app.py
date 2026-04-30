"""Flask web application with MongoDB Atlas connection."""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "")
client = MongoClient(MONGO_URI)
db = client["webapp"]

users_col = db["users"]
songs_col = db["songs"]
events_col = db["events"]
playlists_col = db["playlists"]


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/health")
def health():
    """Check MongoDB connectivity and return status."""
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "connected"})
    except Exception as e:  # pylint: disable=broad-exception-caught
        return jsonify({"status": "error", "mongo": str(e)}), 500


@app.route("/settings")
def settings():
    """Render the settings page."""
    return render_template("settings.html")


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
