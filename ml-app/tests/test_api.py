"""Integration tests for the ml-app Flask API."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError

import main as ml_main
from main import app as flask_app
from recommender import ItemBasedRecommender

# ── Cursor / collection helpers ───────────────────────────────────────────────


class _Cursor:
    """Minimal MongoDB cursor stub supporting .sort().limit() chaining."""

    def __init__(self, items=None):
        self._items = list(items or [])

    def sort(self, *_args, **_kwargs):
        """Return self to allow chaining."""
        return self

    def limit(self, n):
        """Return first n items as an iterator."""
        return iter(self._items[:n])

    def __iter__(self):
        return iter(self._items)


def _col(items=None, find_one=None):
    """Return a mock collection backed by _Cursor."""
    col = MagicMock()
    col.find.return_value = _Cursor(items)
    col.find_one.return_value = find_one
    col.insert_one.return_value = MagicMock(inserted_id="test-id")
    return col


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Flask test client with a fresh, empty mock database."""
    flask_app.config["TESTING"] = True
    ml_main._DB_INITIALIZED = False  # pylint: disable=protected-access
    ml_main.recommender = ItemBasedRecommender()

    users = _col()
    songs = _col()
    events = _col()
    cols = {"users": users, "songs": songs, "events": events}

    db_mock = MagicMock()
    db_mock.__getitem__.side_effect = lambda k: cols.get(k, _col())

    with patch("database.init_db"), patch("database.get_db", return_value=db_mock):
        with flask_app.test_client() as c:
            yield c, cols

    ml_main._DB_INITIALIZED = False  # pylint: disable=protected-access
    ml_main.recommender = ItemBasedRecommender()


# ── GET /health ───────────────────────────────────────────────────────────────


def test_health(client):
    """GET /health should return 200 with status ok."""
    c, _ = client
    res = c.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


# ── POST /users ───────────────────────────────────────────────────────────────


def test_create_user_success(client):
    """POST /users with a valid payload should return 201."""
    c, _ = client
    res = c.post("/users", json={"user_id": "u1", "name": "Alice"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["user_id"] == "u1"
    assert data["name"] == "Alice"


def test_create_user_missing_id(client):
    """POST /users without user_id should return 400."""
    c, _ = client
    res = c.post("/users", json={"name": "Alice"})
    assert res.status_code == 400


def test_create_user_duplicate(client):
    """POST /users with an existing user_id should return 409."""
    c, cols = client
    cols["users"].insert_one.side_effect = DuplicateKeyError("dup key", 11000)
    res = c.post("/users", json={"user_id": "u1"})
    assert res.status_code == 409


# ── POST /songs ───────────────────────────────────────────────────────────────


def test_create_song_success(client):
    """POST /songs with a valid payload should return 201."""
    c, _ = client
    res = c.post(
        "/songs",
        json={"song_id": "s1", "title": "My Song", "artist": "Band", "genre": "pop"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["song_id"] == "s1"
    assert data["title"] == "My Song"


def test_create_song_missing_fields(client):
    """POST /songs without required fields should return 400."""
    c, _ = client
    res = c.post("/songs", json={"song_id": "s1"})
    assert res.status_code == 400


def test_create_song_duplicate(client):
    """POST /songs with an existing song_id should return 409."""
    c, cols = client
    cols["songs"].insert_one.side_effect = DuplicateKeyError("dup key", 11000)
    res = c.post("/songs", json={"song_id": "s1", "title": "My Song", "artist": "Band"})
    assert res.status_code == 409


# ── POST /events ──────────────────────────────────────────────────────────────


def test_record_event_success(client):
    """POST /events with valid data should return 201."""
    c, cols = client
    cols["users"].find_one.return_value = {"user_id": "u1"}
    cols["songs"].find_one.return_value = {"song_id": "s1"}
    res = c.post(
        "/events", json={"user_id": "u1", "song_id": "s1", "event_type": "like"}
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["user_id"] == "u1"
    assert data["weight"] == 5.0


def test_record_event_missing_fields(client):
    """POST /events without required fields should return 400."""
    c, _ = client
    res = c.post("/events", json={"user_id": "u1"})
    assert res.status_code == 400


def test_record_event_invalid_type(client):
    """POST /events with an unsupported event_type should return 400."""
    c, cols = client
    cols["users"].find_one.return_value = {"user_id": "u1"}
    cols["songs"].find_one.return_value = {"song_id": "s1"}
    res = c.post(
        "/events", json={"user_id": "u1", "song_id": "s1", "event_type": "nod"}
    )
    assert res.status_code == 400


def test_record_event_unknown_user(client):
    """POST /events for a user that does not exist should return 404."""
    c, cols = client
    cols["users"].find_one.return_value = None
    res = c.post(
        "/events", json={"user_id": "ghost", "song_id": "s1", "event_type": "like"}
    )
    assert res.status_code == 404


def test_record_event_unknown_song(client):
    """POST /events for a song that does not exist should return 404."""
    c, cols = client
    cols["users"].find_one.return_value = {"user_id": "u1"}
    cols["songs"].find_one.return_value = None
    res = c.post(
        "/events", json={"user_id": "u1", "song_id": "ghost", "event_type": "like"}
    )
    assert res.status_code == 404


# ── GET /songs ────────────────────────────────────────────────────────────────


def test_list_songs_empty(client):
    """GET /songs with no songs in the DB should return an empty list."""
    c, _ = client
    res = c.get("/songs")
    assert res.status_code == 200
    assert res.get_json() == []


def test_list_songs_returns_all(client):
    """GET /songs should return all songs from the database."""
    c, cols = client
    cols["songs"].find.return_value = _Cursor(
        [{"song_id": "s1", "title": "Song One", "artist": "A"}]
    )
    res = c.get("/songs")
    assert res.status_code == 200
    assert len(res.get_json()) == 1


# ── GET /recommendations/<user_id> ────────────────────────────────────────────


def test_recommendations_unknown_user(client):
    """GET /recommendations for an unknown user should return 404."""
    c, cols = client
    cols["users"].find_one.return_value = None
    res = c.get("/recommendations/nobody")
    assert res.status_code == 404


def test_recommendations_untrained_returns_mock(client):
    """GET /recommendations when model is untrained should return mock source."""
    c, cols = client
    cols["users"].find_one.return_value = {"user_id": "u1"}
    res = c.get("/recommendations/u1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["source"] == "mock"
    assert data["user_id"] == "u1"
    assert isinstance(data["recommendations"], list)


def test_recommendations_untrained_respects_k(client):
    """GET /recommendations should cap mock fallback results at requested k."""
    c, cols = client
    cols["users"].find_one.return_value = {"user_id": "u1"}
    cols["songs"].find.return_value = _Cursor(
        [
            {"song_id": "s1", "title": "One", "artist": "A", "genre": "pop"},
            {"song_id": "s2", "title": "Two", "artist": "B", "genre": "rock"},
        ]
    )
    res = c.get("/recommendations/u1?k=2")
    data = res.get_json()
    assert res.status_code == 200
    assert data["source"] == "mock"
    assert len(data["recommendations"]) == 2
    assert [item["song_id"] for item in data["recommendations"]] == ["s1", "s2"]


def test_recommendations_trained_returns_model_source(client):
    """GET /recommendations should return model source after successful training."""
    c, cols = client
    cols["events"].find.return_value = _Cursor(
        [
            {"user_id": "u1", "song_id": "s1", "event_type": "like", "weight": 5.0},
            {"user_id": "u1", "song_id": "s2", "event_type": "like", "weight": 5.0},
            {"user_id": "u2", "song_id": "s2", "event_type": "like", "weight": 5.0},
            {"user_id": "u2", "song_id": "s3", "event_type": "like", "weight": 5.0},
        ]
    )
    cols["songs"].find.return_value = _Cursor(
        [
            {"song_id": "s1", "title": "T1", "artist": "A1", "genre": "pop"},
            {"song_id": "s2", "title": "T2", "artist": "A2", "genre": "rock"},
            {"song_id": "s3", "title": "T3", "artist": "A3", "genre": "indie"},
        ]
    )
    cols["users"].find.return_value = _Cursor([{"user_id": "u1"}, {"user_id": "u2"}])
    assert c.post("/train").status_code == 200

    cols["users"].find_one.return_value = {"user_id": "u1"}
    res = c.get("/recommendations/u1?k=5")
    data = res.get_json()
    assert res.status_code == 200
    assert data["source"] == "model"
    assert [item["song_id"] for item in data["recommendations"]] == ["s3"]


# ── GET /songs/<song_id>/similar ──────────────────────────────────────────────


def test_similar_songs_unknown_song(client):
    """GET /songs/<id>/similar for an unknown song should return 404."""
    c, cols = client
    cols["songs"].find_one.return_value = None
    res = c.get("/songs/ghost/similar")
    assert res.status_code == 404


def test_similar_songs_untrained_returns_mock(client):
    """GET /songs/<id>/similar when model is untrained should return mock source."""
    c, cols = client
    cols["songs"].find_one.return_value = {"song_id": "s1"}
    res = c.get("/songs/s1/similar")
    assert res.status_code == 200
    data = res.get_json()
    assert data["source"] == "mock"
    assert data["song_id"] == "s1"


def test_similar_songs_untrained_excludes_source_song(client):
    """GET /songs/<id>/similar mock fallback should exclude the requested song."""
    c, cols = client
    cols["songs"].find_one.return_value = {"song_id": "s1"}
    cols["songs"].find.return_value = _Cursor(
        [
            {"song_id": "s1", "title": "One", "artist": "A", "genre": "pop"},
            {"song_id": "s2", "title": "Two", "artist": "B", "genre": "rock"},
            {"song_id": "s3", "title": "Three", "artist": "C", "genre": "indie"},
        ]
    )
    res = c.get("/songs/s1/similar?k=2")
    data = res.get_json()
    assert res.status_code == 200
    assert data["source"] == "mock"
    assert [item["song_id"] for item in data["similar"]] == ["s2", "s3"]


def test_similar_songs_trained_returns_model_source(client):
    """GET /songs/<id>/similar should return model source after training."""
    c, cols = client
    cols["events"].find.return_value = _Cursor(
        [
            {"user_id": "u1", "song_id": "s1", "event_type": "like", "weight": 5.0},
            {"user_id": "u1", "song_id": "s2", "event_type": "like", "weight": 5.0},
            {"user_id": "u2", "song_id": "s2", "event_type": "like", "weight": 5.0},
            {"user_id": "u2", "song_id": "s3", "event_type": "like", "weight": 5.0},
        ]
    )
    cols["songs"].find.return_value = _Cursor(
        [
            {"song_id": "s1", "title": "T1", "artist": "A1", "genre": "pop"},
            {"song_id": "s2", "title": "T2", "artist": "A2", "genre": "rock"},
            {"song_id": "s3", "title": "T3", "artist": "A3", "genre": "indie"},
        ]
    )
    cols["users"].find.return_value = _Cursor([{"user_id": "u1"}, {"user_id": "u2"}])
    assert c.post("/train").status_code == 200

    cols["songs"].find_one.return_value = {"song_id": "s1"}
    res = c.get("/songs/s1/similar?k=2")
    data = res.get_json()
    assert res.status_code == 200
    assert data["source"] == "model"
    assert all(item["song_id"] != "s1" for item in data["similar"])


# ── POST /train ───────────────────────────────────────────────────────────────


def test_train_insufficient_data(client):
    """POST /train with no events in the DB should return 409."""
    c, _ = client
    res = c.post("/train")
    assert res.status_code == 409


def test_train_success(client):
    """POST /train with sufficient data should return 200 and mark model trained."""
    c, cols = client
    cols["events"].find.return_value = _Cursor(
        [
            {"user_id": "u1", "song_id": "s1", "event_type": "like", "weight": 5.0},
            {"user_id": "u1", "song_id": "s2", "event_type": "like", "weight": 5.0},
            {"user_id": "u2", "song_id": "s2", "event_type": "like", "weight": 5.0},
            {"user_id": "u2", "song_id": "s3", "event_type": "like", "weight": 5.0},
        ]
    )
    cols["songs"].find.return_value = _Cursor(
        [
            {"song_id": "s1", "title": "T1", "artist": "A1", "genre": "pop"},
            {"song_id": "s2", "title": "T2", "artist": "A2", "genre": "rock"},
            {"song_id": "s3", "title": "T3", "artist": "A3", "genre": "indie"},
        ]
    )
    cols["users"].find.return_value = _Cursor([{"user_id": "u1"}, {"user_id": "u2"}])
    res = c.post("/train")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "trained"
    assert data["source"] == "model"
    assert ml_main.recommender.trained is True


# ── POST /generate-playlist ───────────────────────────────────────────────────


def test_generate_playlist_no_songs(client):
    """POST /generate-playlist with an empty DB should return 404."""
    c, _ = client
    res = c.post("/generate-playlist", json={"tags": ["pop"], "size": 10})
    assert res.status_code == 404


def test_generate_playlist_with_songs(client):
    """POST /generate-playlist with songs in the DB should return a playlist."""
    c, cols = client
    cols["songs"].find.return_value = _Cursor(
        [
            {
                "song_id": "s1",
                "title": "Pop Hit",
                "artist": "Pop Band",
                "genre": "pop",
                "mood": ["happy"],
                "era": "10s",
                "energy": "high",
            }
        ]
    )
    res = c.post("/generate-playlist", json={"tags": ["pop"], "size": 5})
    assert res.status_code == 200
    data = res.get_json()
    assert "tracks" in data
    assert "source" in data
    assert "size" in data
    assert len(data["tracks"]) >= 1


def test_generate_playlist_source_tags(client):
    """POST /generate-playlist with only tags should report source as 'tags'."""
    c, cols = client
    cols["songs"].find.return_value = _Cursor(
        [{"song_id": "s1", "title": "T", "artist": "A", "genre": "pop", "mood": []}]
    )
    res = c.post("/generate-playlist", json={"tags": ["pop"]})
    assert res.get_json()["source"] == "tags"


def test_generate_playlist_source_random(client):
    """POST /generate-playlist with no tags or seeds should report source as 'random'."""
    c, cols = client
    cols["songs"].find.return_value = _Cursor(
        [{"song_id": "s1", "title": "T", "artist": "A", "genre": "pop", "mood": []}]
    )
    res = c.post("/generate-playlist", json={})
    assert res.get_json()["source"] == "random"


def test_generate_playlist_size_clamped(client):
    """POST /generate-playlist size should be clamped to [5, 50]."""
    c, cols = client
    cols["songs"].find.return_value = _Cursor(
        [
            {
                "song_id": f"s{i}",
                "title": f"T{i}",
                "artist": "A",
                "genre": "pop",
                "mood": [],
            }
            for i in range(10)
        ]
    )
    res = c.post("/generate-playlist", json={"size": 999})
    assert res.get_json()["size"] <= 50
