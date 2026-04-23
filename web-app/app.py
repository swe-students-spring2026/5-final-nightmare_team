from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
from datetime import datetime, timezone
import os

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/")
client = MongoClient(MONGO_URI)
db = client["webapp"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "mongo": str(e)}), 500


@app.route("/api/playlists", methods=["POST"])
def save_playlist():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("tracks"), list):
        return jsonify({"ok": False, "message": "Invalid payload"}), 400
    doc = {
        "tracks":   data["tracks"],
        "savedAt":  data.get("savedAt", datetime.now(timezone.utc).isoformat()),
        "createdAt": datetime.now(timezone.utc),
    }
    result = db["playlists"].insert_one(doc)
    return jsonify({"ok": True, "id": str(result.inserted_id)}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
