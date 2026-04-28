from __future__ import annotations

from app import database
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
    database.reset_db()

    for user_id, name in USERS:
        database.execute(
            "INSERT INTO users (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )

    for song_id, title, artist, genre in SONGS:
        database.execute(
            "INSERT INTO songs (song_id, title, artist, genre) VALUES (?, ?, ?, ?)",
            (song_id, title, artist, genre),
        )

    for user_id, song_id, event_type in EVENTS:
        database.execute(
            "INSERT INTO events (user_id, song_id, event_type, weight) VALUES (?, ?, ?, ?)",
            (user_id, song_id, event_type, EVENT_WEIGHTS[event_type]),
        )


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(USERS)} users, {len(SONGS)} songs, and {len(EVENTS)} events.")
