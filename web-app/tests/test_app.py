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


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_register_creates_user(http_client):
    """POST /api/auth/register with valid payload returns 201."""
    from app import users_col  # pylint: disable=import-outside-toplevel
    users_col.find_one.return_value = None
    users_col.insert_one.return_value = MagicMock(inserted_id="deadbeef00000000deadbeef")
    res = http_client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "password123"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True


def test_register_duplicate_username(http_client):
    """POST /api/auth/register with a taken username returns 409."""
    from app import users_col  # pylint: disable=import-outside-toplevel
    users_col.find_one.return_value = {"username": "testuser"}
    res = http_client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "password123"},
    )
    assert res.status_code == 409


def test_register_short_password(http_client):
    """POST /api/auth/register with a password shorter than 8 chars returns 400."""
    res = http_client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "abc"},
    )
    assert res.status_code == 400


def test_login_valid(http_client):
    """POST /api/auth/login with correct credentials returns 200."""
    from app import users_col  # pylint: disable=import-outside-toplevel
    from werkzeug.security import generate_password_hash  # pylint: disable=import-outside-toplevel
    users_col.find_one.return_value = {
        "_id": "deadbeef00000000deadbeef",
        "username": "testuser",
        "password_hash": generate_password_hash("password123"),
    }
    res = http_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_login_wrong_password(http_client):
    """POST /api/auth/login with wrong password returns 401."""
    from app import users_col  # pylint: disable=import-outside-toplevel
    from werkzeug.security import generate_password_hash  # pylint: disable=import-outside-toplevel
    users_col.find_one.return_value = {
        "_id": "deadbeef00000000deadbeef",
        "username": "testuser",
        "password_hash": generate_password_hash("correct"),
    }
    res = http_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrong"},
    )
    assert res.status_code == 401


def test_login_unknown_user(http_client):
    """POST /api/auth/login with an unknown username returns 401."""
    from app import users_col  # pylint: disable=import-outside-toplevel
    users_col.find_one.return_value = None
    res = http_client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert res.status_code == 401


def test_logout(http_client):
    """POST /api/auth/logout returns 200."""
    res = http_client.post("/api/auth/logout")
    assert res.status_code == 200


# ── Settings API tests ────────────────────────────────────────────────────────

def test_get_settings_requires_auth(http_client):
    """GET /api/settings without a session returns 401."""
    res = http_client.get("/api/settings")
    assert res.status_code == 401


def test_get_settings_authenticated(http_client):
    """GET /api/settings with a valid session returns 200 and the user data."""
    from app import users_col  # pylint: disable=import-outside-toplevel
    fake_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    users_col.find_one.return_value = {
        "_id": fake_id,
        "username": "testuser",
        "display_name": "Test",
        "email": "t@t.com",
        "avatar": None,
        "settings": {
            "default_playlist_size": 20,
            "preferred_genres": [],
            "default_era": "any",
            "auto_save": False,
            "public_playlists": False,
            "spotify_connected": False,
        },
    }
    with http_client.session_transaction() as sess:
        sess["user_id"] = fake_id
    res = http_client.get("/api/settings")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "password_hash" not in data["data"]


def test_put_settings_invalid_playlist_size(http_client):
    """PUT /api/settings with an out-of-range playlist size returns 400."""
    fake_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    with http_client.session_transaction() as sess:
        sess["user_id"] = fake_id
    res = http_client.put(
        "/api/settings",
        json={"settings": {"default_playlist_size": 999}},
    )
    assert res.status_code == 400


def test_put_settings_invalid_email(http_client):
    """PUT /api/settings with a malformed email returns 400."""
    fake_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    with http_client.session_transaction() as sess:
        sess["user_id"] = fake_id
    res = http_client.put(
        "/api/settings",
        json={"email": "not-an-email"},
    )
    assert res.status_code == 400


def test_delete_history_requires_auth(http_client):
    """DELETE /api/settings/history without a session returns 401."""
    res = http_client.delete("/api/settings/history")
    assert res.status_code == 401


def test_delete_account_requires_auth(http_client):
    """DELETE /api/settings/account without a session returns 401."""
    res = http_client.delete("/api/settings/account")
    assert res.status_code == 401


def test_settings_page_redirects_unauthenticated(http_client):
    """GET /settings without a session redirects to /login."""
    res = http_client.get("/settings")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
