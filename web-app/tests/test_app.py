"""Tests for the Flask web application."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock, patch

import pytest
import requests
from werkzeug.security import generate_password_hash

from app import app as flask_app
from app import client as mongo_client
from app import playlists_col, users_col

_AUTH_USER = {"id": "user-123", "name": "Tester", "email": "t@t.com"}


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
        sess["auth_user"] = _AUTH_USER.copy()
    return http_client


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Login / register / logout
# ---------------------------------------------------------------------------


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


def test_register_missing_fields(http_client):
    """Test POST /register with missing fields redirects with error."""
    res = http_client.post("/register", data={"name": "", "email": "", "password": ""})
    assert res.status_code == 302
    assert "/login?error=missing_register_fields" in res.headers["Location"]


def test_register_weak_password(http_client):
    """Test POST /register with password under 8 chars redirects with error."""
    res = http_client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "short"},
    )
    assert res.status_code == 302
    assert "/login?error=weak_password" in res.headers["Location"]


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


def test_login_missing_fields(http_client):
    """Test POST /login with empty credentials redirects with error."""
    res = http_client.post("/login", data={"email": "", "password": ""})
    assert res.status_code == 302
    assert "/login?error=missing_login_fields" in res.headers["Location"]


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


# ---------------------------------------------------------------------------
# Health / settings
# ---------------------------------------------------------------------------


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


def test_settings_page(http_client):
    """Test that the settings route returns 200."""
    res = http_client.get("/settings")
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/playlists
# ---------------------------------------------------------------------------


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


def test_save_playlist_no_body(auth_client):
    """Test POST /api/playlists with no JSON body returns 400."""
    res = auth_client.post("/api/playlists", content_type="application/json", data="")
    assert res.status_code == 400
    assert res.get_json()["ok"] is False


def test_save_playlist_fires_ml_events(auth_client):
    """Test POST /api/playlists fires per-track save events using session user_id."""
    playlists_col.insert_one = MagicMock(return_value=MagicMock(inserted_id="pl-1"))
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {}
    payload = {"tracks": [{"song_id": "s1"}, {"song_id": "s2"}]}

    with patch("app.http.post", return_value=mock_resp) as mock_post:
        res = auth_client.post("/api/playlists", json=payload)

    assert res.status_code == 201
    event_calls = [c for c in mock_post.call_args_list if "/events" in c.args[0]]
    assert len(event_calls) == 2
    bodies = [c.kwargs["json"] for c in event_calls]
    assert {"user_id": "user-123", "song_id": "s1", "event_type": "save"} in bodies
    assert {"user_id": "user-123", "song_id": "s2", "event_type": "save"} in bodies


def test_save_playlist_ml_unavailable_still_saves(auth_client):
    """Test POST /api/playlists still returns 201 when ml-app is unreachable."""
    playlists_col.insert_one = MagicMock(return_value=MagicMock(inserted_id="pl-2"))
    with patch("app.http.post", side_effect=requests.exceptions.ConnectionError):
        res = auth_client.post("/api/playlists", json={"tracks": [{"song_id": "s1"}]})

    assert res.status_code == 201
    assert res.get_json()["ok"] is True


# ---------------------------------------------------------------------------
# POST /api/events
# ---------------------------------------------------------------------------


def test_record_event_requires_login(http_client):
    """Test POST /api/events returns 401 when not logged in."""
    res = http_client.post("/api/events", json={"song_id": "s1", "event_type": "like"})
    assert res.status_code == 401


def test_record_event_proxies_ml_app(auth_client):
    """Test POST /api/events proxies to ml-app and returns its response."""
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {
        "event_id": "ev1",
        "user_id": "user-123",
        "song_id": "s1",
        "event_type": "like",
        "weight": 1.0,
    }
    with patch("app.http.post", return_value=mock_resp):
        res = auth_client.post(
            "/api/events", json={"song_id": "s1", "event_type": "like"}
        )
    assert res.status_code == 201
    assert res.get_json()["event_id"] == "ev1"


def test_record_event_ml_unavailable(auth_client):
    """Test POST /api/events returns 503 when ml-app is unreachable."""
    with patch("app.http.post", side_effect=requests.exceptions.ConnectionError):
        res = auth_client.post(
            "/api/events", json={"song_id": "s1", "event_type": "like"}
        )
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/generate-playlist
# ---------------------------------------------------------------------------


def test_generate_playlist_proxies_ml_app(http_client):
    """Test POST /api/generate-playlist proxies to ml-app and returns its response."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"tracks": [], "size": 0, "source": "random"}
    with patch("app.http.post", return_value=mock_resp):
        res = http_client.post(
            "/api/generate-playlist", json={"tags": ["pop"], "size": 10}
        )
    assert res.status_code == 200
    assert "tracks" in res.get_json()


def test_generate_playlist_ml_unavailable(http_client):
    """Test POST /api/generate-playlist returns 503 when ml-app is unreachable."""
    with patch("app.http.post", side_effect=requests.exceptions.ConnectionError):
        res = http_client.post("/api/generate-playlist", json={})
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/recommendations/<user_id>
# ---------------------------------------------------------------------------


def test_get_recommendations_proxies_ml_app(http_client):
    """Test GET /api/recommendations proxies to ml-app and returns its response."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"user_id": "user-123", "recommendations": []}
    with patch("app.http.get", return_value=mock_resp) as mock_get:
        res = http_client.get("/api/recommendations/user-123?k=5")
    assert res.status_code == 200
    assert "user_id" in res.get_json()
    call_url = mock_get.call_args.args[0]
    assert "user-123" in call_url


def test_get_recommendations_ml_unavailable(http_client):
    """Test GET /api/recommendations returns 503 when ml-app is unreachable."""
    with patch("app.http.get", side_effect=requests.exceptions.ConnectionError):
        res = http_client.get("/api/recommendations/user-123")
    assert res.status_code == 503
    assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# GET /api/songs
# ---------------------------------------------------------------------------


def test_api_songs_proxies_ml_app(http_client):
    """Test GET /api/songs proxies to ml-app and returns its response."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = [{"song_id": "s1", "title": "Test"}]
    with patch("app.http.get", return_value=mock_resp):
        res = http_client.get("/api/songs")
    assert res.status_code == 200
    assert res.get_json()[0]["song_id"] == "s1"


def test_api_songs_ml_unavailable(http_client):
    """Test GET /api/songs returns 503 when ml-app is unreachable."""
    with patch("app.http.get", side_effect=requests.exceptions.ConnectionError):
        res = http_client.get("/api/songs")
    assert res.status_code == 503
