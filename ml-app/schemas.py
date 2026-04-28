from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EventType = Literal["play", "skip", "like", "dislike", "save", "repeat"]


class HealthResponse(BaseModel):
    status: str


class UserCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str | None = None


class UserResponse(BaseModel):
    user_id: str
    name: str | None = None


class SongCreate(BaseModel):
    song_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    artist: str = Field(..., min_length=1)
    genre: str | None = None


class SongResponse(BaseModel):
    song_id: str
    title: str
    artist: str
    genre: str | None = None


class EventCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    song_id: str = Field(..., min_length=1)
    event_type: EventType


class EventResponse(BaseModel):
    event_id: int
    user_id: str
    song_id: str
    event_type: EventType
    weight: float


class RecommendationItem(BaseModel):
    song_id: str
    title: str
    artist: str
    genre: str | None = None
    score: float


class RecommendationResponse(BaseModel):
    user_id: str
    source: Literal["mock", "model"]
    recommendations: list[RecommendationItem]


class SimilarSongsResponse(BaseModel):
    song_id: str
    source: Literal["mock", "model"]
    similar: list[RecommendationItem]


class TrainResponse(BaseModel):
    status: str
    source: Literal["model"]
    users: int
    songs: int
    events: int
