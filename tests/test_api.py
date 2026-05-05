from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/")

    from app import database
    from app import main
    from app.recommender import ItemBasedRecommender

    importlib.reload(database)
    importlib.reload(main)
    database.reset_db()
    main.recommender = ItemBasedRecommender()
    main._db_initialized = True  # DB already initialised by reset_db above

    main.app.config["TESTING"] = True
    with main.app.test_client() as test_client:
        yield test_client


def seed_minimal(client) -> None:
    for user_id in ["u1", "u2", "u3"]:
        res = client.post("/users", json={"user_id": user_id, "name": user_id.upper()})
        assert res.status_code == 201

    songs = [
        {"song_id": "s1", "title": "Midnight City", "artist": "M83", "genre": "Electronic"},
        {"song_id": "s2", "title": "Electric Feel", "artist": "MGMT", "genre": "Indie Pop"},
        {"song_id": "s3", "title": "Dreams", "artist": "Fleetwood Mac", "genre": "Rock"},
        {"song_id": "s4", "title": "Redbone", "artist": "Childish Gambino", "genre": "R&B"},
    ]
    for song in songs:
        res = client.post("/songs", json=song)
        assert res.status_code == 201

    events = [
        {"user_id": "u1", "song_id": "s1", "event_type": "like"},
        {"user_id": "u1", "song_id": "s2", "event_type": "save"},
        {"user_id": "u2", "song_id": "s1", "event_type": "like"},
        {"user_id": "u2", "song_id": "s3", "event_type": "save"},
        {"user_id": "u3", "song_id": "s2", "event_type": "like"},
        {"user_id": "u3", "song_id": "s4", "event_type": "repeat"},
    ]
    for event in events:
        res = client.post("/events", json=event)
        assert res.status_code == 201


def test_health(client) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_mock_recommendations_before_training(client) -> None:
    client.post("/users", json={"user_id": "u1", "name": "Avery"})

    res = client.get("/recommendations/u1?k=2")
    assert res.status_code == 200
    body = res.get_json()
    assert body["source"] == "mock"
    assert body["user_id"] == "u1"
    assert len(body["recommendations"]) == 2


def test_records_event_and_rejects_unknown_song(client) -> None:
    client.post("/users", json={"user_id": "u1"})
    res = client.post(
        "/events",
        json={"user_id": "u1", "song_id": "missing", "event_type": "like"},
    )
    assert res.status_code == 404
    assert res.get_json()["error"] == "Unknown song."


def test_rejects_unsupported_event_type(client) -> None:
    client.post("/users", json={"user_id": "u1"})
    client.post("/songs", json={"song_id": "s1", "title": "One", "artist": "Artist"})

    res = client.post(
        "/events",
        json={"user_id": "u1", "song_id": "s1", "event_type": "dance"},
    )
    assert res.status_code == 400


def test_train_and_get_model_recommendations(client) -> None:
    seed_minimal(client)

    train_res = client.post("/train")
    assert train_res.status_code == 200
    assert train_res.get_json()["source"] == "model"

    rec_res = client.get("/recommendations/u1?k=2")
    assert rec_res.status_code == 200
    body = rec_res.get_json()
    assert body["source"] == "model"
    assert body["recommendations"]
    assert all(item["song_id"] not in {"s1", "s2"} for item in body["recommendations"])


def test_train_and_get_similar_songs(client) -> None:
    seed_minimal(client)
    assert client.post("/train").status_code == 200

    res = client.get("/songs/s1/similar?k=2")
    assert res.status_code == 200
    body = res.get_json()
    assert body["source"] == "model"
    assert body["song_id"] == "s1"
    assert body["similar"]
    assert all(item["song_id"] != "s1" for item in body["similar"])


def test_generate_playlist_by_tags(client) -> None:
    seed_minimal(client)

    res = client.post(
        "/generate-playlist",
        json={"tags": ["rock"], "size": 2},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["source"] == "tags"
    assert len(body["tracks"]) == 2
    assert all("title" in t and "artist" in t for t in body["tracks"])


def test_generate_playlist_by_seed(client) -> None:
    seed_minimal(client)

    res = client.post(
        "/generate-playlist",
        json={"seed_songs": ["M83"], "size": 2},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["source"] == "seeds"
    assert body["tracks"][0]["artist"] == "M83"


def test_generate_playlist_empty_db(client) -> None:
    res = client.post("/generate-playlist", json={"tags": ["pop"], "size": 5})
    assert res.status_code == 404
