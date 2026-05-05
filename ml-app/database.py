"""MongoDB database connection helpers for the music recommender."""

from __future__ import annotations

import os

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure

_client: MongoClient | None = None  # pylint: disable=invalid-name


def get_db() -> Database:
    """Return a handle to the webapp MongoDB database."""
    global _client  # pylint: disable=global-statement
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URI", ""))
    return _client["webapp"]


def _create_index_safe(collection, keys, **kwargs) -> None:
    """Create an index, dropping and recreating it if the definition has changed."""
    try:
        collection.create_index(keys, **kwargs)
    except OperationFailure:
        collection.drop_indexes()
        collection.create_index(keys, **kwargs)


def init_db() -> None:
    """Create indexes on the recommender collections."""
    db = get_db()
    _create_index_safe(db["users"], [("user_id", ASCENDING)], unique=True)
    _create_index_safe(db["songs"], [("song_id", ASCENDING)], unique=True)
    _create_index_safe(db["events"], [("user_id", ASCENDING), ("song_id", ASCENDING)])


def reset_db() -> None:
    """Drop and recreate the recommender collections."""
    db = get_db()
    db["users"].drop()
    db["songs"].drop()
    db["events"].drop()
    init_db()
