"""Tests for the Flask web application."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock

import pytest

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
