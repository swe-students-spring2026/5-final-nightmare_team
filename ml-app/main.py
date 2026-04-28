from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, status

from app import database
from app.models import EVENT_WEIGHTS, MOCK_SONGS
from app.recommender import ItemBasedRecommender, NotEnoughDataError
from app.schemas import (
    EventCreate,
    EventResponse,
    HealthResponse,
    RecommendationItem,
    RecommendationResponse,
    SimilarSongsResponse,
    SongCreate,
    SongResponse,
    TrainResponse,
    UserCreate,
    UserResponse,
)


recommender = ItemBasedRecommender()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    database.init_db()
    yield


app = FastAPI(
    title="Music Recommendation API",
    description="Collaborative-filtering song recommendation backend.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate) -> UserResponse:
    try:
        database.execute(
            "INSERT INTO users (user_id, name) VALUES (?, ?)",
            (user.user_id, user.name),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="User already exists.") from exc
    return UserResponse(**user.model_dump())


@app.post("/songs", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def create_song(song: SongCreate) -> SongResponse:
    try:
        database.execute(
            "INSERT INTO songs (song_id, title, artist, genre) VALUES (?, ?, ?, ?)",
            (song.song_id, song.title, song.artist, song.genre),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Song already exists.") from exc
    return SongResponse(**song.model_dump())


@app.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def record_event(event: EventCreate) -> EventResponse:
    if not _user_exists(event.user_id):
        raise HTTPException(status_code=404, detail="Unknown user.")
    if not _song_exists(event.song_id):
        raise HTTPException(status_code=404, detail="Unknown song.")

    weight = EVENT_WEIGHTS[event.event_type]
    cursor = database.execute(
        "INSERT INTO events (user_id, song_id, event_type, weight) VALUES (?, ?, ?, ?)",
        (event.user_id, event.song_id, event.event_type, weight),
    )
    return EventResponse(
        event_id=int(cursor.lastrowid),
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
        raise HTTPException(status_code=409, detail="Not enough unseen song data for recommendations.")

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
        raise HTTPException(status_code=409, detail="Not enough data to find similar songs.")

    return SimilarSongsResponse(
        song_id=song_id,
        source="model",
        similar=[RecommendationItem(**item) for item in similar],
    )


@app.post("/train", response_model=TrainResponse)
def train() -> TrainResponse:
    events = pd.DataFrame([dict(row) for row in database.fetch_all("SELECT * FROM events")])
    songs = pd.DataFrame([dict(row) for row in database.fetch_all("SELECT * FROM songs")])
    users = database.fetch_all("SELECT * FROM users")

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
    )


def _user_exists(user_id: str) -> bool:
    return database.fetch_one("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) is not None


def _song_exists(song_id: str) -> bool:
    return database.fetch_one("SELECT song_id FROM songs WHERE song_id = ?", (song_id,)) is not None


def _mock_items(k: int, exclude_song_id: str | None = None) -> list[RecommendationItem]:
    rows = database.fetch_all("SELECT song_id, title, artist, genre FROM songs ORDER BY song_id LIMIT ?", (k + 1,))
    items: list[RecommendationItem] = []

    for index, row in enumerate(rows):
        if row["song_id"] == exclude_song_id:
            continue
        items.append(
            RecommendationItem(
                song_id=row["song_id"],
                title=row["title"],
                artist=row["artist"],
                genre=row["genre"],
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
