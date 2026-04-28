"""Tests for the Flask web application."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock, patch

import pytest
import requests as req

from app import app as flask_app
from app import client as mongo_client


@pytest.fixture
def http_client():
    """Provide a Flask test client."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client


def test_index(http_client):
    """Test that the index route returns 200."""
    res = http_client.get("/")
    assert res.status_code == 200


def test_health_ok(http_client):
    """Test health endpoint when MongoDB is reachable."""
    mongo_client.admin.command = MagicMock(return_value={"ok": 1})
    res = http_client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_health_error(http_client):
    """Test health endpoint when MongoDB is unreachable."""
    mongo_client.admin.command = MagicMock(side_effect=Exception("unreachable"))
    res = http_client.get("/health")
    assert res.status_code == 500
    data = res.get_json()
    assert data["status"] == "error"


def test_save_playlist_valid(http_client):
    """Test POST /api/playlists with a valid payload returns 201."""
    payload = {
        "tracks": [
            {"id": 1, "title": "Test Track", "artist": "Artist", "duration": "3:00"}
        ]
    }
    res = http_client.post("/api/playlists", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert "id" in data


def test_save_playlist_missing_tracks(http_client):
    """Test POST /api/playlists with no tracks key returns 400."""
    res = http_client.post("/api/playlists", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False


def test_save_playlist_invalid_tracks_type(http_client):
    """Test POST /api/playlists with tracks as non-list returns 400."""
    res = http_client.post("/api/playlists", json={"tracks": "not-a-list"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False


# ── /api/ml/users ─────────────────────────────────────────────────────────────

def test_create_ml_user_valid(http_client):
    """Test POST /api/ml/users proxies to ml-app and returns 201."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"user_id": "u1", "name": "Alice"}
    with patch("app.requests.post", return_value=mock_resp):
        res = http_client.post("/api/ml/users", json={"user_id": "u1", "name": "Alice"})
    assert res.status_code == 201
    assert res.get_json()["user_id"] == "u1"


def test_create_ml_user_missing_user_id(http_client):
    """Test POST /api/ml/users without user_id returns 400."""
    res = http_client.post("/api/ml/users", json={"name": "Alice"})
    assert res.status_code == 400
    assert res.get_json()["ok"] is False


def test_create_ml_user_service_unavailable(http_client):
    """Test POST /api/ml/users returns 503 when ml-app is down."""
    with patch("app.requests.post", side_effect=req.RequestException("down")):
        res = http_client.post("/api/ml/users", json={"user_id": "u1"})
    assert res.status_code == 503


# ── /api/ml/events ────────────────────────────────────────────────────────────

def test_record_ml_event_valid(http_client):
    """Test POST /api/ml/events proxies to ml-app and returns 201."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "event_id": 1, "user_id": "u1", "song_id": "s1",
        "event_type": "like", "weight": 5.0,
    }
    with patch("app.requests.post", return_value=mock_resp):
        res = http_client.post(
            "/api/ml/events",
            json={"user_id": "u1", "song_id": "s1", "event_type": "like"},
        )
    assert res.status_code == 201
    assert res.get_json()["event_type"] == "like"


def test_record_ml_event_invalid_type(http_client):
    """Test POST /api/ml/events rejects disallowed event types."""
    res = http_client.post(
        "/api/ml/events",
        json={"user_id": "u1", "song_id": "s1", "event_type": "play"},
    )
    assert res.status_code == 400
    assert res.get_json()["ok"] is False


def test_record_ml_event_missing_fields(http_client):
    """Test POST /api/ml/events with missing fields returns 400."""
    res = http_client.post("/api/ml/events", json={"user_id": "u1"})
    assert res.status_code == 400
    assert res.get_json()["ok"] is False


def test_record_ml_event_service_unavailable(http_client):
    """Test POST /api/ml/events returns 503 when ml-app is down."""
    with patch("app.requests.post", side_effect=req.RequestException("down")):
        res = http_client.post(
            "/api/ml/events",
            json={"user_id": "u1", "song_id": "s1", "event_type": "save"},
        )
    assert res.status_code == 503


# ── /api/ml/train ─────────────────────────────────────────────────────────────

def test_train_ml_model(http_client):
    """Test POST /api/ml/train proxies to ml-app and returns 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "trained", "source": "model",
        "users": 5, "songs": 10, "events": 50,
    }
    with patch("app.requests.post", return_value=mock_resp):
        res = http_client.post("/api/ml/train")
    assert res.status_code == 200
    assert res.get_json()["status"] == "trained"


def test_train_ml_model_service_unavailable(http_client):
    """Test POST /api/ml/train returns 503 when ml-app is down."""
    with patch("app.requests.post", side_effect=req.RequestException("down")):
        res = http_client.post("/api/ml/train")
    assert res.status_code == 503
