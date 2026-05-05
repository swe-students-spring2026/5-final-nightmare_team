"""FastAPI application for the music recommendation service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app import database
from app.models import EVENT_WEIGHTS, MOCK_SONGS
from app.recommender import HybridRecommender, NotEnoughDataError
from app.seed import load_lastfm_songs
from app.schemas import (
    EventCreate,
    EventResponse,
    HealthResponse,
    LastFMSeedResponse,
    RecommendationItem,
    RecommendationResponse,
    SimilarSongsResponse,
    SongCreate,
    SongResponse,
    TrainResponse,
    UserCreate,
    UserResponse,
)

recommender = HybridRecommender()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialise the database on startup."""
    database.init_db()
    yield


app = FastAPI(
    title="Music Recommendation API",
    description="Hybrid collaborative-filtering + content-based song recommendation backend.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate) -> UserResponse:
    """Create a new user."""
    db = database.get_db()
    try:
        db["users"].insert_one({"user_id": user.user_id, "name": user.name})
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="User already exists.") from exc
    return UserResponse(**user.model_dump())


@app.post("/songs", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def create_song(song: SongCreate) -> SongResponse:
    """Create a new song."""
    db = database.get_db()
    try:
        db["songs"].insert_one(
            {
                "song_id": song.song_id,
                "title": song.title,
                "artist": song.artist,
                "genre": song.genre,
                "tags": song.tags,
            }
        )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Song already exists.") from exc
    return SongResponse(**song.model_dump())


@app.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def record_event(event: EventCreate) -> EventResponse:
    """Record a user-song interaction event."""
    if not _user_exists(event.user_id):
        raise HTTPException(status_code=404, detail="Unknown user.")
    if not _song_exists(event.song_id):
        raise HTTPException(status_code=404, detail="Unknown song.")

    db = database.get_db()
    weight = EVENT_WEIGHTS[event.event_type]
    result = db["events"].insert_one(
        {
            "user_id": event.user_id,
            "song_id": event.song_id,
            "event_type": event.event_type,
            "weight": weight,
        }
    )
    return EventResponse(
        event_id=str(result.inserted_id),
        user_id=event.user_id,
        song_id=event.song_id,
        event_type=event.event_type,
        weight=weight,
    )


@app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def get_recommendations(
    user_id: str,
    k: int = Query(default=10, ge=1, le=100),
) -> RecommendationResponse:
    """Return the top-k song recommendations for a user."""
    if not _user_exists(user_id):
        raise HTTPException(status_code=404, detail="Unknown user.")

    if not recommender.trained:
        return RecommendationResponse(
            user_id=user_id,
            source="mock",
            recommendations=_mock_items(k),
        )

    try:
        recommendations = recommender.recommend(user_id, k)
    except NotEnoughDataError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not recommendations:
        raise HTTPException(
            status_code=409,
            detail="Not enough unseen song data for recommendations.",
        )

    return RecommendationResponse(
        user_id=user_id,
        source="model",
        recommendations=[RecommendationItem(**item) for item in recommendations],
    )


@app.get("/songs/{song_id}/similar", response_model=SimilarSongsResponse)
def get_similar_songs(
    song_id: str,
    k: int = Query(default=10, ge=1, le=100),
) -> SimilarSongsResponse:
    """Return the top-k songs most similar to the given song."""
    if not _song_exists(song_id):
        raise HTTPException(status_code=404, detail="Unknown song.")

    if not recommender.trained:
        return SimilarSongsResponse(
            song_id=song_id,
            source="mock",
            similar=_mock_items(k, exclude_song_id=song_id),
        )

    try:
        similar = recommender.similar_songs(song_id, k)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not similar:
        raise HTTPException(
            status_code=409, detail="Not enough data to find similar songs."
        )

    return SimilarSongsResponse(
        song_id=song_id,
        source="model",
        similar=[RecommendationItem(**item) for item in similar],
    )


@app.post("/train", response_model=TrainResponse)
def train() -> TrainResponse:
    """Train the recommendation model on all stored events."""
    db = database.get_db()
    events = pd.DataFrame(list(db["events"].find({}, {"_id": 0})))
    songs = pd.DataFrame(list(db["songs"].find({}, {"_id": 0})))
    users = list(db["users"].find({}))

    try:
        recommender.fit(events, songs)
    except NotEnoughDataError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return TrainResponse(
        status="trained",
        source="model",
        users=len(users),
        songs=len(songs),
        events=len(events),
        content_trained=recommender.cb.trained,
    )


@app.post("/seed/lastfm", response_model=LastFMSeedResponse)
def seed_lastfm(
    limit: int = Query(default=2000, ge=100, le=10000),
) -> LastFMSeedResponse:
    """
    Populate the songs table from the bundled Last.fm dataset and immediately
    train the content-based (tag-similarity) model. No user events required.
    """
    inserted = load_lastfm_songs(limit=limit)

    db = database.get_db()
    songs = pd.DataFrame(list(db["songs"].find({}, {"_id": 0})))
    if not songs.empty and "tags" in songs.columns:
        try:
            recommender.fit_content(songs)
        except NotEnoughDataError:
            pass

    return LastFMSeedResponse(
        status="seeded",
        songs_inserted=inserted,
        content_trained=recommender.cb.trained,
    )


def _user_exists(user_id: str) -> bool:
    """Return True if the user exists in the database."""
    db = database.get_db()
    return db["users"].find_one({"user_id": user_id}) is not None


def _song_exists(song_id: str) -> bool:
    """Return True if the song exists in the database."""
    db = database.get_db()
    return db["songs"].find_one({"song_id": song_id}) is not None


def _mock_items(k: int, exclude_song_id: str | None = None) -> list[RecommendationItem]:
    """Return up to k mock recommendation items, optionally excluding a song."""
    db = database.get_db()
    rows = list(
        db["songs"]
        .find({}, {"_id": 0, "song_id": 1, "title": 1, "artist": 1, "genre": 1})
        .sort("song_id", 1)
        .limit(k + 1)
    )
    items: list[RecommendationItem] = []

    for index, row in enumerate(rows):
        if row["song_id"] == exclude_song_id:
            continue
        items.append(
            RecommendationItem(
                song_id=row["song_id"],
                title=row["title"],
                artist=row["artist"],
                genre=row.get("genre"),
                score=round(0.95 - (index * 0.04), 4),
            )
        )
        if len(items) >= k:
            return items

    for index, song in enumerate(MOCK_SONGS):
        if song.song_id == exclude_song_id:
            continue
        items.append(
            RecommendationItem(
                song_id=song.song_id,
                title=song.title,
                artist=song.artist,
                genre=song.genre,
                score=round(0.91 - (index * 0.03), 4),
            )
        )
        if len(items) >= k:
            break

    return items
