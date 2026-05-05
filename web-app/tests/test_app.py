"""Tests for the Flask web application."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock, patch

import pytest
import requests
from bson import ObjectId
from werkzeug.security import generate_password_hash

from app import app as flask_app
from app import client as mongo_client
from app import playlists_col, users_col


@pytest.fixture
def http_client():
    """Provide a Flask test client."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_client(http_client):
    """Provide a Flask test client with a logged-in session."""
    with http_client.session_transaction() as sess:
        sess["auth_user"] = {
            "id": "user-123",
            "user_id": "user-123",
            "name": "Test Listener",
            "email": "listener@example.com",
        }
    return http_client


def test_index(http_client):
    """Test that the index route returns 200."""
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


def test_save_playlist_unauthenticated(http_client):
    """Test POST /api/playlists without a session returns 401."""
    res = http_client.post("/api/playlists", json={"tracks": []})
    assert res.status_code == 401
    assert res.get_json()["ok"] is False


def test_save_playlist_valid(auth_client):
    """Test POST /api/playlists with a valid payload returns 201."""
    payload = {
        "tracks": [
            {"id": 1, "title": "Test Track", "artist": "Artist", "duration": "3:00"}
        ]
    }
    res = auth_client.post("/api/playlists", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert "id" in data


def test_save_playlist_missing_tracks(auth_client):
    """Test POST /api/playlists with no tracks key returns 400."""
    res = auth_client.post("/api/playlists", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False


def test_save_playlist_invalid_tracks_type(auth_client):
    """Test POST /api/playlists with tracks as non-list returns 400."""
    res = auth_client.post("/api/playlists", json={"tracks": "not-a-list"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False


def test_save_playlist_no_body(auth_client):
    """Test POST /api/playlists with no JSON body returns 400."""
    res = auth_client.post("/api/playlists", content_type="application/json", data="")
    assert res.status_code == 400
    assert res.get_json()["ok"] is False


def test_save_playlist_fires_ml_events(auth_client):
    """Test POST /api/playlists fires best-effort events using the session user_id."""
    playlists_col.insert_one = MagicMock(return_value=MagicMock(inserted_id="pl-1"))
    payload = {"tracks": [{"song_id": "s1"}, {"song_id": "s2"}]}
    with patch("app.http.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        res = auth_client.post("/api/playlists", json=payload)

    assert res.status_code == 201
    assert mock_post.call_count == 2
    call_bodies = [c.kwargs["json"] for c in mock_post.call_args_list]
    assert {"user_id": "user-123", "song_id": "s1", "event_type": "save"} in call_bodies
    assert {"user_id": "user-123", "song_id": "s2", "event_type": "save"} in call_bodies


def test_save_playlist_ml_unavailable_still_saves(auth_client):
    """Test POST /api/playlists still returns 201 when ml-app is unreachable."""
    playlists_col.insert_one = MagicMock(return_value=MagicMock(inserted_id="pl-2"))
    payload = {"tracks": [{"song_id": "s1"}]}
    with patch("app.http.post", side_effect=requests.exceptions.ConnectionError):
        res = auth_client.post("/api/playlists", json=payload)

    assert res.status_code == 201
    assert res.get_json()["ok"] is True


# ---------------------------------------------------------------------------
# GET /api/playlists
# ---------------------------------------------------------------------------


def test_get_playlists_unauthenticated(http_client):
    """Test GET /api/playlists without a session returns 401."""
    res = http_client.get("/api/playlists")
    assert res.status_code == 401


def test_get_playlists_returns_user_playlists(auth_client):
    """Test GET /api/playlists returns only the session user's playlists."""
    oid = ObjectId()
    playlists_col.find = MagicMock(
        return_value=MagicMock(
            sort=lambda *_: MagicMock(
                limit=lambda *_: [
                    {
                        "_id": oid,
                        "user_id": "user-123",
                        "savedAt": "2024-01-01",
                        "tracks": [],
                    }
                ]
            )
        )
    )

    res = auth_client.get("/api/playlists")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["id"] == str(oid)
    assert "_id" not in data[0]
    query_arg = playlists_col.find.call_args[0][0]
    assert query_arg == {"user_id": "user-123"}


# ---------------------------------------------------------------------------
# GET /api/recommendations/<user_id>
# ---------------------------------------------------------------------------


def test_get_recommendations_proxies_ml_app(http_client):
    """Test GET /api/recommendations proxies to ml-app and returns its response."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = [{"song_id": "s1", "title": "Test Song"}]

    with patch("app.http.get", return_value=mock_resp) as mock_get:
        res = http_client.get("/api/recommendations/user-123?k=5")

    assert res.status_code == 200
    data = res.get_json()
    assert data[0]["song_id"] == "s1"
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "user-123" in call_url


def test_get_recommendations_ml_unavailable(http_client):
    """Test GET /api/recommendations returns 503 when ml-app is unreachable."""
    with patch("app.http.get", side_effect=requests.exceptions.ConnectionError):
        res = http_client.get("/api/recommendations/user-123")

    assert res.status_code == 503
    assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


def test_settings_page(http_client):
    """Test that the settings route returns 200."""
    res = http_client.get("/settings")
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Register validation edge cases
# ---------------------------------------------------------------------------


def test_register_missing_fields(http_client):
    """Test POST /register with missing fields redirects with error."""
    res = http_client.post("/register", data={"name": "", "email": "", "password": ""})
    assert res.status_code == 302
    assert "/login?error=missing_register_fields" in res.headers["Location"]


def test_register_weak_password(http_client):
    """Test POST /register with password shorter than 8 chars redirects with error."""
    res = http_client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "short"},
    )
    assert res.status_code == 302
    assert "/login?error=weak_password" in res.headers["Location"]


# ---------------------------------------------------------------------------
# Login validation edge cases
# ---------------------------------------------------------------------------


def test_login_missing_fields(http_client):
    """Test POST /login with empty email/password redirects with error."""
    res = http_client.post("/login", data={"email": "", "password": ""})
    assert res.status_code == 302
    assert "/login?error=missing_login_fields" in res.headers["Location"]


def test_login_missing_password(http_client):
    """Test POST /login with email but no password redirects with error."""
    res = http_client.post("/login", data={"email": "user@example.com", "password": ""})
    assert res.status_code == 302
    assert "/login?error=missing_login_fields" in res.headers["Location"]
