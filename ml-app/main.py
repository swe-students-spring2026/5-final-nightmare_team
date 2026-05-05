"""Flask application for the music recommendation service."""

from __future__ import annotations

import random

import pandas as pd
from flask import Flask, jsonify, request
from pymongo.errors import DuplicateKeyError

from app import database
from app.models import EVENT_WEIGHTS, MOCK_SONGS
from app.recommender import ItemBasedRecommender, NotEnoughDataError

recommender = ItemBasedRecommender()
_DB_INITIALIZED = False  # pylint: disable=invalid-name

app = Flask(__name__)


@app.before_request
def _ensure_db():
    global _DB_INITIALIZED  # pylint: disable=global-statement,invalid-name
    if not _DB_INITIALIZED:
        database.init_db()
        _startup_train()
        _DB_INITIALIZED = True


def _startup_train():
    """Train the recommender on startup if data exists."""
    db = database.get_db()
    events = pd.DataFrame(list(db["events"].find({}, {"_id": 0})))
    songs = pd.DataFrame(list(db["songs"].find({}, {"_id": 0})))
    try:
        recommender.fit(events, songs)
    except NotEnoughDataError:
        pass  # not enough data yet — model stays untrained until /train is called


@app.get("/health")
def health():
    """Return service health status."""
    return jsonify({"status": "ok"})


@app.post("/users")
def create_user():
    """Create a new user."""
    data = request.get_json(force=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    db = database.get_db()
    try:
        db["users"].insert_one({"user_id": user_id, "name": data.get("name")})
    except DuplicateKeyError:
        return jsonify({"error": "User already exists."}), 409
    return jsonify({"user_id": user_id, "name": data.get("name")}), 201


@app.post("/songs")
def create_song():
    """Create a new song."""
    data = request.get_json(force=True) or {}
    song_id = str(data.get("song_id", "")).strip()
    title = str(data.get("title", "")).strip()
    artist = str(data.get("artist", "")).strip()
    if not song_id or not title or not artist:
        return jsonify({"error": "song_id, title, and artist are required"}), 400
    db = database.get_db()
    doc = {
        "song_id": song_id,
        "title": title,
        "artist": artist,
        "genre": data.get("genre"),
        "mood": data.get("mood", []),
        "era": data.get("era"),
        "energy": data.get("energy"),
    }
    try:
        db["songs"].insert_one(doc)
    except DuplicateKeyError:
        return jsonify({"error": "Song already exists."}), 409
    doc.pop("_id", None)
    return jsonify(doc), 201


@app.post("/events")
def record_event():
    """Record a user-song interaction event."""
    data = request.get_json(force=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    song_id = str(data.get("song_id", "")).strip()
    event_type = str(data.get("event_type", "")).strip()
    if not user_id or not song_id or not event_type:
        return jsonify({"error": "user_id, song_id, and event_type are required"}), 400
    if event_type not in EVENT_WEIGHTS:
        return jsonify({"error": f"Unsupported event_type: {event_type}"}), 400
    if not _user_exists(user_id):
        return jsonify({"error": "Unknown user."}), 404
    if not _song_exists(song_id):
        return jsonify({"error": "Unknown song."}), 404
    db = database.get_db()
    weight = EVENT_WEIGHTS[event_type]
    result = db["events"].insert_one(
        {
            "user_id": user_id,
            "song_id": song_id,
            "event_type": event_type,
            "weight": weight,
        }
    )
    return (
        jsonify(
            {
                "event_id": str(result.inserted_id),
                "user_id": user_id,
                "song_id": song_id,
                "event_type": event_type,
                "weight": weight,
            }
        ),
        201,
    )


@app.get("/songs")
def list_songs():
    """Return all songs in the database."""
    db = database.get_db()
    songs = list(db["songs"].find({}, {"_id": 0}))
    return jsonify(songs)


@app.get("/recommendations/<user_id>")
def get_recommendations(user_id):
    """Return top-k song recommendations for a user."""
    k = request.args.get("k", 10, type=int)
    if not _user_exists(user_id):
        return jsonify({"error": "Unknown user."}), 404
    if not recommender.trained:
        return jsonify(
            {"user_id": user_id, "source": "mock", "recommendations": _mock_items(k)}
        )
    try:
        recs = recommender.recommend(user_id, k)
    except (NotEnoughDataError, KeyError):
        recs = []
    if not recs:
        return jsonify(
            {"user_id": user_id, "source": "mock", "recommendations": _mock_items(k)}
        )
    return jsonify({"user_id": user_id, "source": "model", "recommendations": recs})


@app.get("/songs/<song_id>/similar")
def get_similar_songs(song_id):
    """Return top-k songs most similar to the given song."""
    k = request.args.get("k", 10, type=int)
    if not _song_exists(song_id):
        return jsonify({"error": "Unknown song."}), 404
    if not recommender.trained:
        return jsonify(
            {
                "song_id": song_id,
                "source": "mock",
                "similar": _mock_items(k, exclude_song_id=song_id),
            }
        )
    try:
        similar = recommender.similar_songs(song_id, k)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    if not similar:
        return jsonify({"error": "Not enough data to find similar songs."}), 409
    return jsonify({"song_id": song_id, "source": "model", "similar": similar})


@app.post("/train")
def train():
    """Train the recommendation model on all stored events."""
    db = database.get_db()
    events = pd.DataFrame(list(db["events"].find({}, {"_id": 0})))
    songs = pd.DataFrame(list(db["songs"].find({}, {"_id": 0})))
    users = list(db["users"].find({}))
    try:
        recommender.fit(events, songs)
    except NotEnoughDataError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "status": "trained",
            "source": "model",
            "users": len(users),
            "songs": len(songs),
            "events": len(events),
        }
    )


@app.post("/generate-playlist")
def generate_playlist():
    """Generate a playlist based on tags and seed songs."""
    data = request.get_json(force=True) or {}
    tags = [str(t).lower().strip() for t in data.get("tags", []) if t]
    seed_songs = [str(s).lower().strip() for s in data.get("seed_songs", []) if s]
    size = max(5, min(50, int(data.get("size", 20))))

    db = database.get_db()
    all_songs = list(db["songs"].find({}, {"_id": 0}))
    if not all_songs:
        return (
            jsonify({"error": "No songs in database. Run the seed script first."}),
            404,
        )

    def score_song(song):
        score = 0.0
        song_tags = set()
        if song.get("genre"):
            song_tags.add(song["genre"].lower())
        for mood in song.get("mood", []):
            song_tags.add(mood.lower())
        if song.get("era"):
            song_tags.add(song["era"].lower())
        if song.get("energy"):
            song_tags.add(song["energy"].lower())

        for tag in tags:
            if tag in song_tags:
                score += 2.0
            elif any(tag in t or t in tag for t in song_tags):
                score += 0.5

        title_l = song["title"].lower()
        artist_l = song["artist"].lower()
        for seed in seed_songs:
            if seed in title_l or seed in artist_l:
                score += 5.0
            elif title_l in seed or artist_l in seed:
                score += 3.0

        score += random.uniform(0, 0.4)
        return score

    scored = [(song, score_song(song)) for song in all_songs]
    scored.sort(key=lambda x: x[1], reverse=True)

    if tags or seed_songs:
        matched = [s for s in scored if s[1] > 0.4]
        rest = [s for s in scored if s[1] <= 0.4]
        random.shuffle(rest)
        combined = matched + rest
    else:
        random.shuffle(scored)
        combined = scored

    tracks = []
    for song, score in combined[:size]:
        tracks.append(
            {
                "song_id": song["song_id"],
                "title": song["title"],
                "artist": song["artist"],
                "genre": song.get("genre"),
                "mood": song.get("mood", []),
                "era": song.get("era"),
                "score": round(min(score, 10.0), 3),
            }
        )

    if seed_songs and tags:
        source = "mixed"
    elif tags:
        source = "tags"
    elif seed_songs:
        source = "seeds"
    else:
        source = "random"

    return jsonify({"tracks": tracks, "source": source, "size": len(tracks)})


def _user_exists(user_id: str) -> bool:
    return database.get_db()["users"].find_one({"user_id": user_id}) is not None


def _song_exists(song_id: str) -> bool:
    return database.get_db()["songs"].find_one({"song_id": song_id}) is not None


def _mock_items(k: int, exclude_song_id: str | None = None) -> list[dict]:
    db = database.get_db()
    rows = list(
        db["songs"]
        .find({}, {"_id": 0, "song_id": 1, "title": 1, "artist": 1, "genre": 1})
        .sort("song_id", 1)
        .limit(k + 1)
    )
    items: list[dict] = []
    for i, row in enumerate(rows):
        if row["song_id"] == exclude_song_id:
            continue
        items.append(
            {
                "song_id": row["song_id"],
                "title": row["title"],
                "artist": row["artist"],
                "genre": row.get("genre"),
                "score": round(0.95 - (i * 0.04), 4),
            }
        )
        if len(items) >= k:
            return items
    for i, song in enumerate(MOCK_SONGS):
        if song.song_id == exclude_song_id:
            continue
        items.append(
            {
                "song_id": song.song_id,
                "title": song.title,
                "artist": song.artist,
                "genre": song.genre,
                "score": round(0.91 - (i * 0.03), 4),
            }
        )
        if len(items) >= k:
            break
    return items


if __name__ == "__main__":
    database.init_db()
    app.run(host="0.0.0.0", port=8000)
