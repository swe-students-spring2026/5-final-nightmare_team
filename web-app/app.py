"""Flask web application with MongoDB Atlas connection."""

import base64
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import requests as http
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or "dev-secret-key"

MONGO_URI = os.environ.get("MONGO_URI", "")
ML_APP_URL = os.environ.get("ML_APP_URL", "http://ml-app:8000")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get(
    "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5050/spotify/callback"
)

client = MongoClient(MONGO_URI)
db = client["webapp"]

users_col = db["users"]
songs_col = db["songs"]
events_col = db["events"]
playlists_col = db["playlists"]


AUTH_MESSAGE_MAP = {
    "logged_in": "Signed in successfully.",
    "registered": "Account created successfully. You are now signed in.",
    "logged_out": "Signed out successfully.",
    "missing_login_fields": "Enter both your email and password to sign in.",
    "missing_register_fields": (
        "Name, email, and password are all required to create an account."
    ),
    "invalid_credentials": (
        "That email and password combination does not match our records."
    ),
    "user_exists": "An account with that email already exists. Try signing in instead.",
    "weak_password": "Use a password with at least 8 characters.",
}


def normalize_email(value):
    return value.strip().lower()


def get_auth_message(code):
    return AUTH_MESSAGE_MAP.get(code)


def build_session_user(user_doc):
    return {
        "id": str(user_doc.get("_id", "")),
        "name": user_doc.get("name") or user_doc.get("email") or "Listener",
        "email": user_doc.get("email", ""),
    }


def _spotify_is_connected(user_id_str):
    """Return True if the user has a Spotify access token stored in MongoDB."""
    if not user_id_str:
        return False
    try:
        doc = users_col.find_one(
            {"_id": ObjectId(user_id_str)}, {"spotify_access_token": 1}
        )
        return bool(doc and doc.get("spotify_access_token"))
    except InvalidId:
        return False


def _get_valid_token(user_doc):
    """Return a valid Spotify access token, refreshing it if expired."""
    if time.time() < user_doc.get("spotify_token_expires_at", 0):
        return user_doc["spotify_access_token"]

    refresh_token = user_doc.get("spotify_refresh_token")
    if not refresh_token:
        return None

    credentials = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    try:
        resp = http.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {credentials}"},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=10,
        )
    except http.exceptions.RequestException:
        return None

    if resp.status_code != 200:
        return None

    token_data = resp.json()
    access_token = token_data["access_token"]
    expires_at = int(time.time()) + token_data.get("expires_in", 3600) - 60

    update_fields = {
        "spotify_access_token": access_token,
        "spotify_token_expires_at": expires_at,
    }
    if "refresh_token" in token_data:
        update_fields["spotify_refresh_token"] = token_data["refresh_token"]

    users_col.update_one({"_id": user_doc["_id"]}, {"$set": update_fields})
    return access_token


# ── Pages ──────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    user = session.get("auth_user")
    spotify_connected = _spotify_is_connected(user["id"] if user else "")
    return render_template("index.html", spotify_connected=spotify_connected)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")

        if not email or not password:
            return redirect(url_for("login", error="missing_login_fields", email=email))

        user_doc = users_col.find_one({"email": email})
        if not user_doc or not check_password_hash(
            user_doc.get("passwordHash", ""), password
        ):
            return redirect(url_for("login", error="invalid_credentials", email=email))

        session["auth_user"] = build_session_user(user_doc)
        return redirect(url_for("index"))

    return render_template(
        "login.html",
        auth_error=get_auth_message(request.args.get("error")),
        auth_success=get_auth_message(request.args.get("success")),
        current_user=session.get("auth_user"),
        login_email=request.args.get("email", ""),
    )


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = normalize_email(request.form.get("email", ""))
    password = request.form.get("password", "")

    if not name or not email or not password:
        return redirect(url_for("login", error="missing_register_fields"))

    if len(password) < 8:
        return redirect(url_for("login", error="weak_password"))

    if users_col.find_one({"email": email}):
        return redirect(url_for("login", error="user_exists", email=email))

    new_id = ObjectId()
    user_doc = {
        "_id": new_id,
        "user_id": str(new_id),
        "username": email,
        "name": name,
        "email": email,
        "passwordHash": generate_password_hash(password),
        "createdAt": datetime.now(timezone.utc),
    }
    users_col.insert_one(user_doc)
    session["auth_user"] = build_session_user(user_doc)
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("auth_user", None)
    return redirect(url_for("login", success="logged_out"))


@app.route("/health")
def health():
    # pylint: disable=invalid-name
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "connected"})
    except Exception as e:  # pylint: disable=broad-exception-caught
        return jsonify({"status": "error", "mongo": str(e)}), 500
    # pylint: enable=invalid-name


@app.route("/settings")
def settings():
    user = session.get("auth_user")
    spotify_connected = _spotify_is_connected(user["id"] if user else "")

    connect_message = None
    if request.args.get("spotify_success"):
        connect_message = {"type": "success", "text": "Spotify connected successfully!"}
    elif request.args.get("spotify_error") == "access_denied":
        connect_message = {"type": "error", "text": "Spotify connection was cancelled."}
    elif request.args.get("spotify_error"):
        connect_message = {
            "type": "error",
            "text": "Spotify connection failed. Please try again.",
        }

    return render_template(
        "settings.html",
        spotify_connected=spotify_connected,
        spotify_connect_message=connect_message,
    )


# ── Spotify OAuth ──────────────────────────────────────────────────────────────


@app.route("/spotify/login")
def spotify_login():
    if not session.get("auth_user"):
        return redirect(url_for("login"))
    state = secrets.token_urlsafe(16)
    session["spotify_oauth_state"] = state
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": "playlist-modify-public playlist-modify-private",
        "state": state,
    }
    return redirect(f"https://accounts.spotify.com/authorize?{urlencode(params)}")


@app.route("/spotify/callback")
def spotify_callback():
    if request.args.get("error"):
        return redirect(url_for("settings", spotify_error="access_denied"))

    code = request.args.get("code", "")
    state = request.args.get("state", "")

    if not state or state != session.pop("spotify_oauth_state", None):
        return redirect(url_for("settings", spotify_error="state_mismatch"))

    user = session.get("auth_user")
    if not user:
        return redirect(url_for("login"))

    credentials = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    try:
        token_resp = http.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {credentials}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
            timeout=10,
        )
    except http.exceptions.RequestException:
        return redirect(url_for("settings", spotify_error="token_exchange_failed"))

    if token_resp.status_code != 200:
        return redirect(url_for("settings", spotify_error="token_exchange_failed"))

    token_data = token_resp.json()
    expires_at = int(time.time()) + token_data.get("expires_in", 3600) - 60
    print(f"[spotify] callback granted scopes: {token_data.get('scope')}")

    try:
        users_col.update_one(
            {"_id": ObjectId(user["id"])},
            {
                "$set": {
                    "spotify_access_token": token_data["access_token"],
                    "spotify_refresh_token": token_data.get("refresh_token", ""),
                    "spotify_token_expires_at": expires_at,
                }
            },
        )
    except InvalidId:
        return redirect(url_for("settings", spotify_error="session_error"))

    return redirect(url_for("settings", spotify_success="1"))


@app.route("/spotify/disconnect", methods=["POST"])
def spotify_disconnect():
    user = session.get("auth_user")
    if not user:
        return jsonify({"ok": False, "message": "Not logged in"}), 401
    try:
        users_col.update_one(
            {"_id": ObjectId(user["id"])},
            {
                "$unset": {
                    "spotify_access_token": "",
                    "spotify_refresh_token": "",
                    "spotify_token_expires_at": "",
                }
            },
        )
    except InvalidId:
        pass
    return jsonify({"ok": True})


@app.route("/api/spotify/status")
def spotify_status():
    user = session.get("auth_user")
    return jsonify({"connected": _spotify_is_connected(user["id"] if user else "")})


# ── Spotify playlist save ──────────────────────────────────────────────────────


@app.route("/api/spotify/save-playlist", methods=["POST"])
def spotify_save_playlist():
    user = session.get("auth_user")
    if not user:
        return jsonify({"ok": False, "message": "Not logged in"}), 401

    data = request.get_json(silent=True)
    if (
        not data
        or not isinstance(data.get("tracks"), list)
        or not data.get("playlist_name")
    ):
        return jsonify({"ok": False, "message": "Invalid payload"}), 400

    try:
        user_doc = users_col.find_one({"_id": ObjectId(user["id"])})
    except InvalidId:
        return jsonify({"ok": False, "message": "Session error"}), 400

    if not user_doc or not user_doc.get("spotify_access_token"):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Spotify not connected. Connect in Settings first.",
                }
            ),
            403,
        )

    access_token = _get_valid_token(user_doc)
    if not access_token:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Spotify token expired — reconnect in Settings.",
                }
            ),
            403,
        )

    auth_header = {"Authorization": f"Bearer {access_token}"}
    json_header = {**auth_header, "Content-Type": "application/json"}

    # Create the playlist (POST /v1/me/playlists works for the authenticated user)
    playlist_name = data["playlist_name"][:100]
    try:
        create_resp = http.post(
            "https://api.spotify.com/v1/me/playlists",
            headers=json_header,
            json={
                "name": playlist_name,
                "public": True,
                "description": "Generated by VibeList",
            },
            timeout=10,
        )
    except http.exceptions.RequestException as exc:
        print(f"[spotify] create playlist request failed: {exc}")
        return jsonify({"ok": False, "message": "Could not reach Spotify API."}), 502

    if create_resp.status_code not in (200, 201):
        print(
            f"[spotify] create playlist returned {create_resp.status_code}: {create_resp.text}"
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "message": f"Failed to create playlist ({create_resp.status_code}): {create_resp.text}",
                }
            ),
            502,
        )

    playlist_data = create_resp.json()
    playlist_id = playlist_data["id"]
    playlist_url = playlist_data["external_urls"]["spotify"]
    print(f"[spotify] playlist created: id={repr(playlist_id)} url={playlist_url}")

    # Search Spotify for each track's URI
    uris = []
    for track in data["tracks"]:
        title = track.get("title", "") if isinstance(track, dict) else ""
        artist = track.get("artist", "") if isinstance(track, dict) else ""
        if not title:
            continue
        query = f"track:{title} artist:{artist}" if artist else f"track:{title}"
        try:
            search_resp = http.get(
                "https://api.spotify.com/v1/search",
                headers=auth_header,
                params={"q": query, "type": "track", "limit": 1},
                timeout=10,
            )
            if search_resp.status_code == 200:
                items = search_resp.json().get("tracks", {}).get("items", [])
                if items:
                    uris.append(items[0]["uri"])
            else:
                print(
                    f"[spotify] search failed {search_resp.status_code} for '{query}': {search_resp.text}"
                )
        except http.exceptions.RequestException as exc:
            print(f"[spotify] search request failed for '{query}': {exc}")

    print(f"[spotify] search complete: {len(uris)}/{len(data['tracks'])} URIs found")

    # Verify token identity vs playlist owner before adding tracks
    me_resp = http.get("https://api.spotify.com/v1/me", headers=auth_header, timeout=10)
    pl_resp = http.get(
        f"https://api.spotify.com/v1/playlists/{playlist_id}",
        headers=auth_header,
        timeout=10,
    )
    if me_resp.status_code == 200 and pl_resp.status_code == 200:
        me_id = me_resp.json().get("id")
        pl_json = pl_resp.json()
        owner_id = pl_json.get("owner", {}).get("id")
        print(
            f"[spotify] token user={me_id!r}  playlist owner={owner_id!r}  match={me_id == owner_id}"
        )
        print(
            f"[spotify] playlist public={pl_json.get('public')}  collaborative={pl_json.get('collaborative')}"
        )
    else:
        print(
            f"[spotify] verify failed: /me={me_resp.status_code} /playlists={pl_resp.status_code}"
        )

    # Add URIs in batches of 100 (Spotify API limit)
    print(f"[spotify] adding {len(uris)} URIs, sample: {uris[:2]}")
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        try:
            add_resp = http.post(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
                headers=auth_header,
                params={"uris": ",".join(batch)},
                timeout=10,
            )
            if add_resp.status_code not in (200, 201):
                print(
                    f"[spotify] add tracks returned {add_resp.status_code}: {add_resp.text}"
                )
            else:
                print(f"[spotify] added batch of {len(batch)} tracks OK")
        except http.exceptions.RequestException as exc:
            print(f"[spotify] add tracks request failed: {exc}")

    return (
        jsonify(
            {
                "ok": True,
                "url": playlist_url,
                "found": len(uris),
                "total": len(data["tracks"]),
            }
        ),
        201,
    )


# ── ML recommendations proxy ───────────────────────────────────────────────────


@app.route("/api/recommendations/<user_id>")
def get_recommendations(user_id):
    k = request.args.get("k", 10)
    try:
        resp = http.get(
            f"{ML_APP_URL}/recommendations/{user_id}",
            params={"k": k},
            timeout=5,
        )
        return jsonify(resp.json()), resp.status_code
    except http.exceptions.RequestException as exc:
        return (
            jsonify(
                {"error": "Recommendation service unavailable", "detail": str(exc)}
            ),
            503,
        )


@app.route("/api/playlists", methods=["POST"])
def save_playlist():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("tracks"), list):
        return jsonify({"ok": False, "message": "Invalid payload"}), 400

    doc = {
        "user_id": data.get("user_id") or None,
        "tracks": data["tracks"],
        "savedAt": data.get("savedAt", datetime.now(timezone.utc).isoformat()),
        "createdAt": datetime.now(timezone.utc),
    }
    result = playlists_col.insert_one(doc)

    user_id = data.get("user_id")
    if user_id:
        for track in data["tracks"]:
            song_id = track.get("song_id") if isinstance(track, dict) else None
            if song_id:
                try:
                    http.post(
                        f"{ML_APP_URL}/events",
                        json={
                            "user_id": user_id,
                            "song_id": song_id,
                            "event_type": "save",
                        },
                        timeout=3,
                    )
                except http.exceptions.RequestException:
                    pass

    return jsonify({"ok": True, "id": str(result.inserted_id)}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
