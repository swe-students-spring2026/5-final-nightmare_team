"""Flask web application with MongoDB Atlas connection."""

import os
from datetime import datetime, timezone

import requests as http
from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "")
ML_APP_URL = os.environ.get("ML_APP_URL", "http://ml-app:8000")

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
