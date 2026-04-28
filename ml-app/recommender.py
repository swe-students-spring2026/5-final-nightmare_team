from __future__ import annotations

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from app.models import POSITIVE_EVENT_TYPES


class RecommenderNotReadyError(RuntimeError):
    pass


class NotEnoughDataError(ValueError):
    pass


class ItemBasedRecommender:
    def __init__(self) -> None:
        self.trained = False
        self.songs: pd.DataFrame = pd.DataFrame()
        self.events: pd.DataFrame = pd.DataFrame()
        self.user_song_matrix: pd.DataFrame = pd.DataFrame()
        self.song_similarity: pd.DataFrame = pd.DataFrame()

    def fit(self, events: pd.DataFrame, songs: pd.DataFrame) -> None:
        if events.empty:
            raise NotEnoughDataError("At least one event is required to train the model.")
        if songs.empty or songs["song_id"].nunique() < 2:
            raise NotEnoughDataError("At least two songs are required to train the model.")

        required_event_columns = {"user_id", "song_id", "event_type", "weight"}
        if not required_event_columns.issubset(events.columns):
            raise ValueError("Events data is missing required columns.")

        matrix = events.pivot_table(
            index="user_id",
            columns="song_id",
            values="weight",
            aggfunc="sum",
            fill_value=0.0,
        )

        if matrix.shape[0] < 1 or matrix.shape[1] < 2:
            raise NotEnoughDataError("Need events across at least two songs to train the model.")

        similarity = cosine_similarity(matrix.T)
        self.song_similarity = pd.DataFrame(
            similarity,
            index=matrix.columns,
            columns=matrix.columns,
        )
        self.user_song_matrix = matrix
        self.events = events.copy()
        self.songs = songs.drop_duplicates(subset=["song_id"]).set_index("song_id", drop=False)
        self.trained = True

    def recommend(self, user_id: str, k: int) -> list[dict[str, object]]:
        self._ensure_ready()
        if user_id not in self.user_song_matrix.index:
            raise KeyError(f"Unknown user: {user_id}")

        user_events = self.events[self.events["user_id"] == user_id]
        positive_events = user_events[
            (user_events["weight"] > 0) & (user_events["event_type"].isin(POSITIVE_EVENT_TYPES))
        ]
        if positive_events.empty:
            raise NotEnoughDataError("User does not have enough positive feedback for recommendations.")

        interacted_song_ids = set(user_events["song_id"])
        candidate_scores: dict[str, float] = {}

        for _, event in positive_events.iterrows():
            source_song_id = event["song_id"]
            if source_song_id not in self.song_similarity.index:
                continue

            similarities = self.song_similarity.loc[source_song_id]
            for candidate_song_id, similarity in similarities.items():
                if candidate_song_id in interacted_song_ids or candidate_song_id == source_song_id:
                    continue
                candidate_scores[candidate_song_id] = candidate_scores.get(candidate_song_id, 0.0) + (
                    float(event["weight"]) * float(similarity)
                )

        ranked = sorted(
            candidate_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        positive_ranked = [(song_id, score) for song_id, score in ranked if score > 0]
        return [self._song_result(song_id, score) for song_id, score in positive_ranked[:k]]

    def similar_songs(self, song_id: str, k: int) -> list[dict[str, object]]:
        self._ensure_ready()
        if song_id not in self.song_similarity.index:
            raise KeyError(f"Unknown song: {song_id}")

        similarities = self.song_similarity.loc[song_id].drop(labels=[song_id], errors="ignore")
        ranked = similarities.sort_values(ascending=False).head(k)
        return [self._song_result(similar_song_id, float(score)) for similar_song_id, score in ranked.items()]

    def _song_result(self, song_id: str, score: float) -> dict[str, object]:
        song = self.songs.loc[song_id]
        return {
            "song_id": str(song["song_id"]),
            "title": str(song["title"]),
            "artist": str(song["artist"]),
            "genre": None if pd.isna(song["genre"]) else str(song["genre"]),
            "score": round(float(score), 4),
        }

    def _ensure_ready(self) -> None:
        if not self.trained:
            raise RecommenderNotReadyError("Model has not been trained yet.")
