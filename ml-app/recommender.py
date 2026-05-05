"""Item-based collaborative filtering recommender."""

from __future__ import annotations

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import POSITIVE_EVENT_TYPES


class RecommenderNotReadyError(RuntimeError):
    """Raised when the model is used before training."""


class NotEnoughDataError(ValueError):
    """Raised when there is insufficient data to train or recommend."""


class ItemBasedRecommender:
    """Item-based collaborative filter using cosine similarity."""

    def __init__(self) -> None:
        """Initialise an untrained recommender."""
        self.trained = False
        self.songs: pd.DataFrame = pd.DataFrame()
        self.events: pd.DataFrame = pd.DataFrame()
        self.user_song_matrix: pd.DataFrame = pd.DataFrame()
        self.song_similarity: pd.DataFrame = pd.DataFrame()

    def fit(self, events: pd.DataFrame, songs: pd.DataFrame) -> None:
        """Train the model on interaction events and song metadata."""
        if events.empty:
            raise NotEnoughDataError(
                "At least one event is required to train the model."
            )
        if songs.empty or songs["song_id"].nunique() < 2:
            raise NotEnoughDataError(
                "At least two songs are required to train the model."
            )

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
            raise NotEnoughDataError(
                "Need events across at least two songs to train the model."
            )

        similarity = cosine_similarity(matrix.T)
        self.song_similarity = pd.DataFrame(
            similarity,
            index=matrix.columns,
            columns=matrix.columns,
        )
        self.user_song_matrix = matrix
        self.events = events.copy()
        self.songs = songs.drop_duplicates(subset=["song_id"]).set_index(
            "song_id", drop=False
        )
        self.trained = True

    def recommend(self, user_id: str, k: int) -> list[dict[str, object]]:
        """Return the top-k recommended songs for a user."""
        self._ensure_ready()
        if user_id not in self.user_song_matrix.index:
            raise KeyError(f"Unknown user: {user_id}")

        user_events = self.events[self.events["user_id"] == user_id]
        positive_events = user_events[
            (user_events["weight"] > 0)
            & (user_events["event_type"].isin(POSITIVE_EVENT_TYPES))
        ]
        if positive_events.empty:
            raise NotEnoughDataError(
                "User does not have enough positive feedback for recommendations."
            )

        interacted_song_ids = set(user_events["song_id"])
        candidate_scores: dict[str, float] = {}

        for _, event in positive_events.iterrows():
            source_song_id = event["song_id"]
            if source_song_id not in self.song_similarity.index:
                continue

            similarities = self.song_similarity.loc[source_song_id]
            for candidate_song_id, similarity in similarities.items():
                if (
                    candidate_song_id in interacted_song_ids
                    or candidate_song_id == source_song_id
                ):
                    continue
                candidate_scores[candidate_song_id] = candidate_scores.get(
                    candidate_song_id, 0.0
                ) + float(event["weight"]) * float(similarity)

        ranked = sorted(
            candidate_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        positive_ranked = [(song_id, score) for song_id, score in ranked if score > 0]
        return [
            self._song_result(song_id, score) for song_id, score in positive_ranked[:k]
        ]

    def similar_songs(self, song_id: str, k: int) -> list[dict[str, object]]:
        """Return the top-k songs most similar to the given song."""
        self._ensure_ready()
        if song_id not in self.song_similarity.index:
            raise KeyError(f"Unknown song: {song_id}")

        similarities = self.song_similarity.loc[song_id].drop(
            labels=[song_id], errors="ignore"
        )
        ranked = similarities.sort_values(ascending=False).head(k)
        return [
            self._song_result(similar_song_id, float(score))
            for similar_song_id, score in ranked.items()
        ]

    def _song_result(self, song_id: str, score: float) -> dict[str, object]:
        """Build a result dict for a song with its similarity score."""
        song = self.songs.loc[song_id]
        return {
            "song_id": str(song["song_id"]),
            "title": str(song["title"]),
            "artist": str(song["artist"]),
            "genre": None if pd.isna(song["genre"]) else str(song["genre"]),
            "score": round(float(score), 4),
        }

    def _ensure_ready(self) -> None:
        """Raise if the model has not been trained yet."""
        if not self.trained:
            raise RecommenderNotReadyError("Model has not been trained yet.")


class ContentBasedRecommender:
    """Item-item similarity from TF-IDF tag vectors. Works with zero user events (cold-start)."""

    def __init__(self) -> None:
        self.trained = False
        self.songs: pd.DataFrame = pd.DataFrame()
        self.song_similarity: pd.DataFrame = pd.DataFrame()

    def fit(self, songs: pd.DataFrame) -> None:
        """Train the TF-IDF tag similarity matrix from songs."""
        has_tags = songs["tags"].notna() & (songs["tags"].str.strip() != "")
        songs_with_tags = songs[has_tags].drop_duplicates(subset=["song_id"])
        if len(songs_with_tags) < 2:
            raise NotEnoughDataError(
                "At least two songs with tags are required for content-based training."
            )

        vectorizer = TfidfVectorizer(
            tokenizer=lambda x: [t.strip().lower() for t in x.split("|") if t.strip()],
            token_pattern=None,
        )
        tag_matrix = vectorizer.fit_transform(songs_with_tags["tags"])
        similarity = cosine_similarity(tag_matrix)

        self.song_similarity = pd.DataFrame(
            similarity,
            index=songs_with_tags["song_id"].values,
            columns=songs_with_tags["song_id"].values,
        )
        self.songs = songs_with_tags.set_index("song_id", drop=False)
        self.trained = True

    def similar_songs(self, song_id: str, k: int) -> list[dict[str, object]]:
        """Return the top-k songs most similar to song_id by tag overlap."""
        self._ensure_ready()
        if song_id not in self.song_similarity.index:
            raise KeyError(f"Unknown song: {song_id}")

        similarities = self.song_similarity.loc[song_id].drop(
            labels=[song_id], errors="ignore"
        )
        ranked = similarities.sort_values(ascending=False).head(k)
        return [self._song_result(sid, float(score)) for sid, score in ranked.items()]

    def recommend_for_songs(
        self,
        seed_song_ids: list[str],
        seen_song_ids: set[str],
        k: int,
    ) -> list[dict[str, object]]:
        """Recommend songs similar to seed_song_ids, excluding seen_song_ids."""
        self._ensure_ready()
        candidate_scores: dict[str, float] = {}

        for source_song_id in seed_song_ids:
            if source_song_id not in self.song_similarity.index:
                continue
            for candidate_song_id, score in self.song_similarity.loc[
                source_song_id
            ].items():
                if (
                    candidate_song_id in seen_song_ids
                    or candidate_song_id == source_song_id
                ):
                    continue
                prev = candidate_scores.get(candidate_song_id, 0.0)
                candidate_scores[candidate_song_id] = prev + float(score)

        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        return [self._song_result(sid, score) for sid, score in ranked[:k] if score > 0]

    def _song_result(self, song_id: str, score: float) -> dict[str, object]:
        song = self.songs.loc[song_id]
        genre = song.get("genre", None)
        return {
            "song_id": str(song["song_id"]),
            "title": str(song["title"]),
            "artist": str(song["artist"]),
            "genre": None if (genre is None or pd.isna(genre)) else str(genre),
            "score": round(float(score), 4),
        }

    def _ensure_ready(self) -> None:
        if not self.trained:
            raise RecommenderNotReadyError(
                "Content-based model has not been trained yet."
            )


class HybridRecommender:
    """
    Tries item-based CF first; falls back to content-based (tag similarity) when CF
    lacks enough data for a user. Both models are updated via fit() / fit_content().
    """

    def __init__(self) -> None:
        self.cf = ItemBasedRecommender()
        self.cb = ContentBasedRecommender()
        self._events: pd.DataFrame = pd.DataFrame()

    @property
    def trained(self) -> bool:
        """Return True if at least one sub-model has been trained."""
        return self.cf.trained or self.cb.trained

    def fit_content(self, songs: pd.DataFrame) -> None:
        """Train only the content-based model (no events required)."""
        self.cb.fit(songs)

    def fit(self, events: pd.DataFrame, songs: pd.DataFrame) -> None:
        """Train CF model; auto-trains content-based if songs have tags."""
        self.cf.fit(events, songs)
        self._events = events.copy()

        if not songs.empty and "tags" in songs.columns:
            songs_with_tags = songs[
                songs["tags"].notna() & (songs["tags"].str.strip() != "")
            ]
            if len(songs_with_tags) >= 2:
                self.cb.fit(songs)

    def recommend(self, user_id: str, k: int) -> list[dict[str, object]]:
        """Return k recommendations for user_id, using CF then content-based fallback."""
        # Try CF first for users with interaction history
        if self.cf.trained and user_id in self.cf.user_song_matrix.index:
            try:
                results = self.cf.recommend(user_id, k)
                if results:
                    return results
            except NotEnoughDataError:
                pass

        # Fall back to content-based using the user's positive events as seeds
        if self.cb.trained and not self._events.empty:
            user_events = self._events[self._events["user_id"] == user_id]
            positive_events = user_events[
                (user_events["weight"] > 0)
                & user_events["event_type"].isin(POSITIVE_EVENT_TYPES)
            ]
            if not positive_events.empty:
                seed_ids = positive_events["song_id"].tolist()
                seen_ids = set(user_events["song_id"])
                results = self.cb.recommend_for_songs(seed_ids, seen_ids, k)
                if results:
                    return results

        raise NotEnoughDataError(
            "Not enough data for recommendations. Add more events or seed the lastfm dataset."
        )

    def similar_songs(self, song_id: str, k: int) -> list[dict[str, object]]:
        """Return k songs similar to song_id, preferring CF similarity over content-based."""
        # CF similarity takes priority when available
        if self.cf.trained and song_id in self.cf.song_similarity.index:
            results = self.cf.similar_songs(song_id, k)
            if results:
                return results

        if self.cb.trained and song_id in self.cb.song_similarity.index:
            return self.cb.similar_songs(song_id, k)

        raise KeyError(f"Unknown song: {song_id}")
