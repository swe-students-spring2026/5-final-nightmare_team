from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


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

    with TestClient(main.app) as test_client:
        yield test_client


def seed_minimal(client: TestClient) -> None:
    for user_id in ["u1", "u2", "u3"]:
        response = client.post("/users", json={"user_id": user_id, "name": user_id.upper()})
        assert response.status_code == 201

    songs = [
        {"song_id": "s1", "title": "Midnight City", "artist": "M83", "genre": "Electronic"},
        {"song_id": "s2", "title": "Electric Feel", "artist": "MGMT", "genre": "Indie Pop"},
        {"song_id": "s3", "title": "Dreams", "artist": "Fleetwood Mac", "genre": "Rock"},
        {"song_id": "s4", "title": "Redbone", "artist": "Childish Gambino", "genre": "R&B"},
    ]
    for song in songs:
        response = client.post("/songs", json=song)
        assert response.status_code == 201

    events = [
        {"user_id": "u1", "song_id": "s1", "event_type": "like"},
        {"user_id": "u1", "song_id": "s2", "event_type": "save"},
        {"user_id": "u2", "song_id": "s1", "event_type": "like"},
        {"user_id": "u2", "song_id": "s3", "event_type": "save"},
        {"user_id": "u3", "song_id": "s2", "event_type": "like"},
        {"user_id": "u3", "song_id": "s4", "event_type": "repeat"},
    ]
    for event in events:
        response = client.post("/events", json=event)
        assert response.status_code == 201


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mock_recommendations_before_training(client: TestClient) -> None:
    response = client.post("/users", json={"user_id": "u1", "name": "Avery"})
    assert response.status_code == 201

    response = client.get("/recommendations/u1?k=2")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "mock"
    assert body["user_id"] == "u1"
    assert len(body["recommendations"]) == 2


def test_records_event_and_rejects_unknown_song(client: TestClient) -> None:
    client.post("/users", json={"user_id": "u1"})
    response = client.post(
        "/events",
        json={"user_id": "u1", "song_id": "missing", "event_type": "like"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown song."


def test_rejects_unsupported_event_type(client: TestClient) -> None:
    client.post("/users", json={"user_id": "u1"})
    client.post("/songs", json={"song_id": "s1", "title": "One", "artist": "Artist"})

    response = client.post(
        "/events",
        json={"user_id": "u1", "song_id": "s1", "event_type": "dance"},
    )
    assert response.status_code == 422


def test_train_and_get_model_recommendations(client: TestClient) -> None:
    seed_minimal(client)

    train_response = client.post("/train")
    assert train_response.status_code == 200
    assert train_response.json()["source"] == "model"

    rec_response = client.get("/recommendations/u1?k=2")
    assert rec_response.status_code == 200
    rec_body = rec_response.json()
    assert rec_body["source"] == "model"
    assert rec_body["recommendations"]
    assert all(item["song_id"] not in {"s1", "s2"} for item in rec_body["recommendations"])


def test_train_and_get_similar_songs(client: TestClient) -> None:
    seed_minimal(client)
    assert client.post("/train").status_code == 200

    response = client.get("/songs/s1/similar?k=2")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "model"
    assert body["song_id"] == "s1"
    assert body["similar"]
    assert all(item["song_id"] != "s1" for item in body["similar"])
