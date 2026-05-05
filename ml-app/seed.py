"""Seed script to populate the database with sample data."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from pymongo.errors import PyMongoError

from app.database import get_db, reset_db
from app.models import EVENT_WEIGHTS

USERS = [
    ("u1", "Avery"),
    ("u2", "Jordan"),
    ("u3", "Casey"),
    ("u4", "Riley"),
]


SONGS = [
    ("s1", "Midnight City", "M83", "Electronic"),
    ("s2", "Electric Feel", "MGMT", "Indie Pop"),
    ("s3", "The Less I Know The Better", "Tame Impala", "Psychedelic Pop"),
    ("s4", "Dreams", "Fleetwood Mac", "Rock"),
    ("s5", "Redbone", "Childish Gambino", "R&B"),
    ("s6", "Dog Days Are Over", "Florence + The Machine", "Alternative"),
    ("s7", "Instant Crush", "Daft Punk", "Electronic"),
    ("s8", "Somebody Else", "The 1975", "Synth Pop"),
]


EVENTS = [
    ("u1", "s1", "like"),
    ("u1", "s2", "save"),
    ("u1", "s3", "repeat"),
    ("u1", "s5", "skip"),
    ("u2", "s1", "save"),
    ("u2", "s2", "like"),
    ("u2", "s7", "repeat"),
    ("u2", "s8", "play"),
    ("u3", "s3", "like"),
    ("u3", "s4", "save"),
    ("u3", "s6", "repeat"),
    ("u3", "s5", "dislike"),
    ("u4", "s1", "play"),
    ("u4", "s4", "like"),
    ("u4", "s6", "save"),
    ("u4", "s8", "repeat"),
]


def seed() -> None:
    """Reset the database and insert sample users, songs, and events."""
    reset_db()
    db = get_db()

    for user_id, name in USERS:
        db["users"].insert_one({"user_id": user_id, "name": name})

    for song_id, title, artist, genre in SONGS:
        db["songs"].insert_one(
            {
                "song_id": song_id,
                "title": title,
                "artist": artist,
                "genre": genre,
                "tags": None,
            }
        )

    for user_id, song_id, event_type in EVENTS:
        db["events"].insert_one(
            {
                "user_id": user_id,
                "song_id": song_id,
                "event_type": event_type,
                "weight": EVENT_WEIGHTS[event_type],
            }
        )


def _make_song_id(artist: str, track_name: str) -> str:
    raw = f"{artist.lower()}::{track_name.lower()}"
    return "lfm-" + hashlib.md5(raw.encode()).hexdigest()[:12]


def load_lastfm_songs(limit: int = 2000, csv_path: str | None = None) -> int:
    """
    Load top-`limit` songs from the Last.fm dataset into the songs table.

    Rows are ranked by tag_count descending (more tags = more well-known tracks),
    then avg_rank ascending (lower rank value = higher chart position).
    Returns the number of new rows inserted.
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent / "lastfm_tracks.csv")

    df = pd.read_csv(csv_path, dtype=str)
    df = df[df["tags"].notna() & (df["tags"].str.strip() != "")].copy()
    df["tag_count"] = pd.to_numeric(df["tag_count"], errors="coerce").fillna(0)
    df["avg_rank"] = pd.to_numeric(df["avg_rank"], errors="coerce").fillna(999)
    df = df.sort_values(["tag_count", "avg_rank"], ascending=[False, True]).head(limit)

    inserted = 0
    for _, row in df.iterrows():
        song_id = _make_song_id(str(row["artist"]), str(row["track_name"]))
        title = str(row["track_name"])
        artist = str(row["artist"])
        tags = str(row["tags"])
        genre = tags.split("|")[0].strip() if tags else None

        try:
            db = get_db()
            existing = db["songs"].find_one({"song_id": song_id})
            if existing is None:
                db["songs"].insert_one(
                    {
                        "song_id": song_id,
                        "title": title,
                        "artist": artist,
                        "genre": genre,
                        "tags": tags,
                    }
                )
                inserted += 1
        except PyMongoError:
            pass

    return inserted


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(USERS)} users, {len(SONGS)} songs, and {len(EVENTS)} events.")
