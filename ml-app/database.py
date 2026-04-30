"""SQLite database connection and query helpers for the music recommender."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = "music_recommender.db"


def get_db_path() -> str:
    """Return the database file path from env or the default."""
    return os.getenv("MUSIC_RECOMMENDER_DB", DEFAULT_DB_PATH)


def get_connection() -> sqlite3.Connection:
    """Open and return a SQLite connection with foreign keys enabled."""
    db_path = get_db_path()
    parent = Path(db_path).parent
    if str(parent) != ".":
        parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create all tables if they do not already exist."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT
            );

            CREATE TABLE IF NOT EXISTS songs (
                song_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                genre TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                song_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                weight REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (song_id) REFERENCES songs(song_id)
            );
            """
        )


def reset_db() -> None:
    """Drop all tables and recreate them."""
    with get_connection() as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS events;
            DROP TABLE IF EXISTS songs;
            DROP TABLE IF EXISTS users;
            """
        )
    init_db()


def execute(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    """Execute a write query and return the cursor."""
    with get_connection() as connection:
        cursor = connection.execute(query, params)
        connection.commit()
        return cursor


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    """Return the first row of a query result, or None."""
    with get_connection() as connection:
        return connection.execute(query, params).fetchone()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    """Return all rows of a query result."""
    with get_connection() as connection:
        return connection.execute(query, params).fetchall()
