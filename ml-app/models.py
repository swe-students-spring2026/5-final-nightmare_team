"""Domain models and constants for the music recommender."""

from __future__ import annotations

from dataclasses import dataclass

EVENT_WEIGHTS: dict[str, float] = {
    "play": 1.0,
    "skip": -1.0,
    "like": 5.0,
    "dislike": -5.0,
    "save": 4.0,
    "repeat": 3.0,
}


POSITIVE_EVENT_TYPES = {"play", "like", "save", "repeat"}


@dataclass(frozen=True)
class Song:
    """Immutable song record used for mock recommendations."""

    song_id: str
    title: str
    artist: str
    genre: str | None = None


MOCK_SONGS: list[Song] = [
    Song("sample-1", "Golden Hour Drive", "The Demo Tapes", "Indie Pop"),
    Song("sample-2", "Late Night Static", "Northline", "Electronic"),
    Song("sample-3", "Basement Sun", "Maya Rivers", "Alternative"),
    Song("sample-4", "Blue Vinyl", "The Weekday Club", "Rock"),
    Song("sample-5", "Coffee Shop Echo", "Lena Park", "Singer-Songwriter"),
]
