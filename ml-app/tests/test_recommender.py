"""Unit tests for ItemBasedRecommender."""

# pylint: disable=redefined-outer-name
import pandas as pd
import pytest
from recommender import (
    ItemBasedRecommender,
    NotEnoughDataError,
    RecommenderNotReadyError,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _events(*rows):
    return pd.DataFrame(rows, columns=["user_id", "song_id", "event_type", "weight"])


def _songs(*rows):
    return pd.DataFrame(rows, columns=["song_id", "title", "artist", "genre"])


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def events():
    """Four interaction events across two users and three songs."""
    return _events(
        ("u1", "s1", "like", 5.0),
        ("u1", "s2", "like", 5.0),
        ("u2", "s2", "like", 5.0),
        ("u2", "s3", "like", 5.0),
    )


@pytest.fixture
def songs():
    """Three songs spanning pop, rock, and indie genres."""
    return _songs(
        ("s1", "Song One", "Artist A", "pop"),
        ("s2", "Song Two", "Artist B", "rock"),
        ("s3", "Song Three", "Artist C", "indie"),
    )


@pytest.fixture
def trained(events, songs):
    """A fitted ItemBasedRecommender ready for recommendation tests."""
    r = ItemBasedRecommender()
    r.fit(events, songs)
    return r


# ── fit ───────────────────────────────────────────────────────────────────────


def test_fit_marks_trained(events, songs):
    """fit() should set trained=True."""
    r = ItemBasedRecommender()
    assert r.trained is False
    r.fit(events, songs)
    assert r.trained is True


def test_fit_empty_events_raises(songs):
    """fit() with no events should raise NotEnoughDataError."""
    r = ItemBasedRecommender()
    empty = pd.DataFrame(columns=["user_id", "song_id", "event_type", "weight"])
    with pytest.raises(NotEnoughDataError):
        r.fit(empty, songs)


def test_fit_single_song_raises():
    """fit() with only one unique song should raise NotEnoughDataError."""
    r = ItemBasedRecommender()
    ev = _events(("u1", "s1", "like", 5.0))
    sg = _songs(("s1", "Song One", "Artist A", "pop"))
    with pytest.raises(NotEnoughDataError):
        r.fit(ev, sg)


def test_fit_missing_columns_raises(songs):
    """fit() with events missing required columns should raise ValueError."""
    r = ItemBasedRecommender()
    bad = pd.DataFrame({"user_id": ["u1"], "song_id": ["s1"]})
    with pytest.raises(ValueError):
        r.fit(bad, songs)


def test_fit_stores_songs(events, songs):
    """fit() should index songs by song_id."""
    r = ItemBasedRecommender()
    r.fit(events, songs)
    assert "s1" in r.songs.index
    assert "s2" in r.songs.index


def test_fit_builds_similarity_matrix(events, songs):
    """fit() should produce a square song similarity matrix."""
    r = ItemBasedRecommender()
    r.fit(events, songs)
    assert r.song_similarity.shape[0] == r.song_similarity.shape[1]
    assert set(r.song_similarity.index) == {"s1", "s2", "s3"}


# ── recommend ─────────────────────────────────────────────────────────────────


def test_recommend_raises_when_not_trained():
    """recommend() before fit() should raise RecommenderNotReadyError."""
    with pytest.raises(RecommenderNotReadyError):
        ItemBasedRecommender().recommend("u1", 5)


def test_recommend_unknown_user_raises(trained):
    """recommend() for a user not in the matrix should raise KeyError."""
    with pytest.raises(KeyError):
        trained.recommend("nobody", 5)


def test_recommend_no_positive_events_raises(songs):
    """recommend() for a user with only negative events should raise NotEnoughDataError."""
    neg_events = _events(
        ("u1", "s1", "skip", -1.0),
        ("u1", "s2", "skip", -1.0),
        ("u2", "s2", "dislike", -5.0),
        ("u2", "s3", "skip", -1.0),
    )
    r = ItemBasedRecommender()
    r.fit(neg_events, songs)
    with pytest.raises(NotEnoughDataError):
        r.recommend("u1", 5)


def test_recommend_returns_dicts(trained):
    """recommend() should return a list of dicts with required keys."""
    results = trained.recommend("u1", 5)
    assert isinstance(results, list)
    for item in results:
        assert "song_id" in item
        assert "title" in item
        assert "artist" in item
        assert "score" in item


def test_recommend_excludes_interacted_songs(trained):
    """Songs the user already interacted with should not appear in recs."""
    results = trained.recommend("u1", 10)
    returned_ids = {r["song_id"] for r in results}
    assert "s1" not in returned_ids
    assert "s2" not in returned_ids


def test_recommend_respects_k(trained):
    """recommend() should return at most k items."""
    assert len(trained.recommend("u1", 1)) <= 1


def test_recommend_scores_are_positive(trained):
    """All returned recommendation scores should be positive."""
    for item in trained.recommend("u1", 10):
        assert item["score"] > 0


# ── similar_songs ─────────────────────────────────────────────────────────────


def test_similar_songs_raises_when_not_trained():
    """similar_songs() before fit() should raise RecommenderNotReadyError."""
    with pytest.raises(RecommenderNotReadyError):
        ItemBasedRecommender().similar_songs("s1", 5)


def test_similar_songs_unknown_song_raises(trained):
    """similar_songs() for a song not in the model should raise KeyError."""
    with pytest.raises(KeyError):
        trained.similar_songs("unknown", 5)


def test_similar_songs_returns_dicts(trained):
    """similar_songs() should return a list of dicts with required keys."""
    results = trained.similar_songs("s1", 5)
    assert isinstance(results, list)
    for item in results:
        assert "song_id" in item
        assert "score" in item


def test_similar_songs_excludes_self(trained):
    """The source song should never appear in its own similar-songs list."""
    assert all(r["song_id"] != "s1" for r in trained.similar_songs("s1", 10))


def test_similar_songs_respects_k(trained):
    """similar_songs() should return at most k items."""
    assert len(trained.similar_songs("s1", 1)) <= 1
