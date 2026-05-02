"""Pydantic request/response schemas for the music recommendation API."""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal["play", "skip", "like", "dislike", "save", "repeat"]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class UserCreate(BaseModel):
    """Payload for creating a user."""

    user_id: str = Field(..., min_length=1)
    name: str | None = None


class UserResponse(BaseModel):
    """Response after creating or fetching a user."""

    user_id: str
    name: str | None = None


class SongCreate(BaseModel):
    """Payload for creating a song."""

    song_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    artist: str = Field(..., min_length=1)
    genre: str | None = None


class SongResponse(BaseModel):
    """Response after creating or fetching a song."""

    song_id: str
    title: str
    artist: str
    genre: str | None = None


class EventCreate(BaseModel):
    """Payload for recording a user-song interaction event."""

    user_id: str = Field(..., min_length=1)
    song_id: str = Field(..., min_length=1)
    event_type: EventType


class EventResponse(BaseModel):
    """Response after recording an event."""

    event_id: str
    user_id: str
    song_id: str
    event_type: EventType
    weight: float


class RecommendationItem(BaseModel):
    """A single recommended song with its score."""

    song_id: str
    title: str
    artist: str
    genre: str | None = None
    score: float


class RecommendationResponse(BaseModel):
    """Response for a user recommendation request."""

    user_id: str
    source: Literal["mock", "model"]
    recommendations: list[RecommendationItem]


class SimilarSongsResponse(BaseModel):
    """Response for a similar songs request."""

    song_id: str
    source: Literal["mock", "model"]
    similar: list[RecommendationItem]


class TrainResponse(BaseModel):
    """Response after training the recommendation model."""

    status: str
    source: Literal["model"]
    users: int
    songs: int
    events: int
