"""Tests for the Flask web application."""

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock

import pytest

from app import app as flask_app
from app import client as mongo_client


@pytest.fixture
def http_client():
    """Provide a Flask test client."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client


def test_index(http_client):
    """Test that the index route returns 200."""
    res = http_client.get("/")
    assert res.status_code == 200


def test_health_ok(http_client):
    """Test health endpoint when MongoDB is reachable."""
    mongo_client.admin.command = MagicMock(return_value={"ok": 1})
    res = http_client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_health_error(http_client):
    """Test health endpoint when MongoDB is unreachable."""
    mongo_client.admin.command = MagicMock(side_effect=Exception("unreachable"))
    res = http_client.get("/health")
    assert res.status_code == 500
    data = res.get_json()
    assert data["status"] == "error"
