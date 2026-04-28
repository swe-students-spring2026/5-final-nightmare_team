"""Flask web application with MongoDB connection."""

import os
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/")
ML_APP_URL = os.environ.get("ML_APP_URL", "http://ml-app:8000")

client = MongoClient(MONGO_URI)
db = client["webapp"]

VALID_EVENT_TYPES = {"like", "dislike", "save"}


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
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("tracks"), list):
        return jsonify({"ok": False, "message": "Invalid payload"}), 400
    doc = {
        "tracks": data["tracks"],
        "savedAt": data.get("savedAt", datetime.now(timezone.utc).isoformat()),
        "createdAt": datetime.now(timezone.utc),
    }
    result = db["playlists"].insert_one(doc)
    return jsonify({"ok": True, "id": str(result.inserted_id)}), 201


@app.route("/api/ml/users", methods=["POST"])
def create_ml_user():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("user_id"), str) or not data["user_id"]:
        return jsonify({"ok": False, "message": "user_id is required"}), 400
    try:
        resp = requests.post(f"{ML_APP_URL}/users", json=data, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException:
        return jsonify({"ok": False, "message": "ML service unavailable"}), 503


@app.route("/api/ml/events", methods=["POST"])
def record_ml_event():
    data = request.get_json(silent=True)
    if not data or not {"user_id", "song_id", "event_type"}.issubset(data):
        return jsonify({"ok": False, "message": "user_id, song_id, and event_type are required"}), 400
    if data["event_type"] not in VALID_EVENT_TYPES:
        return jsonify({"ok": False, "message": "event_type must be like, dislike, or save"}), 400
    try:
        resp = requests.post(f"{ML_APP_URL}/events", json=data, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException:
        return jsonify({"ok": False, "message": "ML service unavailable"}), 503


@app.route("/api/ml/train", methods=["POST"])
def train_ml_model():
    try:
        resp = requests.post(f"{ML_APP_URL}/train", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException:
        return jsonify({"ok": False, "message": "ML service unavailable"}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
