"""Tests for the Flask web application."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock

import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from app import client as mongo_client
from app import users_col


@pytest.fixture
def http_client():
    """Provide a Flask test client."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client


def test_index_redirects_when_logged_out(http_client):
    """Test that the index route redirects unauthenticated users to login."""
    res = http_client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_index_accessible_when_logged_in(http_client):
    """Test that the index route renders for authenticated users."""
    with http_client.session_transaction() as sess:
        sess["auth_user"] = {"id": "u1", "name": "Tester", "email": "t@t.com"}
    res = http_client.get("/")
    assert res.status_code == 200


def test_login_page(http_client):
    """Test that the login route returns 200."""
    res = http_client.get("/login")
    assert res.status_code == 200


def test_register_creates_user(http_client):
    """Test that POST /register creates a new user and signs them in."""
    users_col.find_one = MagicMock(return_value=None)
    users_col.insert_one = MagicMock(return_value=MagicMock(inserted_id="user-123"))

    res = http_client.post(
        "/register",
        data={
            "name": "Test Listener",
            "email": "listener@example.com",
            "password": "password123",
        },
    )

    assert res.status_code == 302
    assert res.headers["Location"].endswith("/")

    inserted_doc = users_col.insert_one.call_args[0][0]
    assert inserted_doc["email"] == "listener@example.com"
    assert inserted_doc["name"] == "Test Listener"
    assert inserted_doc["passwordHash"] != "password123"

    with http_client.session_transaction() as browser_session:
        assert browser_session["auth_user"]["email"] == "listener@example.com"


def test_register_rejects_duplicate_email(http_client):
    """Test that POST /register rejects an existing email."""
    users_col.find_one = MagicMock(return_value={"email": "listener@example.com"})

    res = http_client.post(
        "/register",
        data={
            "name": "Test Listener",
            "email": "listener@example.com",
            "password": "password123",
        },
    )

    assert res.status_code == 302
    assert "/login?error=user_exists" in res.headers["Location"]


def test_login_success(http_client):
    """Test that POST /login signs in with valid credentials."""
    users_col.find_one = MagicMock(
        return_value={
            "_id": "user-123",
            "name": "Test Listener",
            "email": "listener@example.com",
            "passwordHash": generate_password_hash("password123"),
        }
    )

    res = http_client.post(
        "/login",
        data={"email": "listener@example.com", "password": "password123"},
    )

    assert res.status_code == 302
    assert res.headers["Location"].endswith("/")

    with http_client.session_transaction() as browser_session:
        assert browser_session["auth_user"]["name"] == "Test Listener"


def test_login_invalid_credentials(http_client):
    """Test that POST /login rejects invalid credentials."""
    users_col.find_one = MagicMock(return_value=None)

    res = http_client.post(
        "/login",
        data={"email": "listener@example.com", "password": "wrong-password"},
    )

    assert res.status_code == 302
    assert "/login?error=invalid_credentials" in res.headers["Location"]


def test_logout_clears_session(http_client):
    """Test that GET /logout clears the signed-in session."""
    with http_client.session_transaction() as browser_session:
        browser_session["auth_user"] = {
            "id": "user-123",
            "name": "Test Listener",
            "email": "listener@example.com",
        }

    res = http_client.get("/logout")

    assert res.status_code == 302
    assert "/login?success=logged_out" in res.headers["Location"]

    with http_client.session_transaction() as browser_session:
        assert "auth_user" not in browser_session


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


def test_save_playlist_requires_login(http_client):
    """Test POST /api/playlists returns 401 when not logged in."""
    res = http_client.post("/api/playlists", json={"tracks": []})
    assert res.status_code == 401


def test_save_playlist_valid(http_client):
    """Test POST /api/playlists with a valid payload returns 201."""
    with http_client.session_transaction() as sess:
        sess["auth_user"] = {"id": "u1", "name": "Tester", "email": "t@t.com"}
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
    with http_client.session_transaction() as sess:
        sess["auth_user"] = {"id": "u1", "name": "Tester", "email": "t@t.com"}
    res = http_client.post("/api/playlists", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False


def test_save_playlist_invalid_tracks_type(http_client):
    """Test POST /api/playlists with tracks as non-list returns 400."""
    with http_client.session_transaction() as sess:
        sess["auth_user"] = {"id": "u1", "name": "Tester", "email": "t@t.com"}
    res = http_client.post("/api/playlists", json={"tracks": "not-a-list"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False
