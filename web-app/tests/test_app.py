import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def client():
    with patch("pymongo.MongoClient") as mock_mongo:
        mock_mongo.return_value = MagicMock()
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c


def test_index(client):
    res = client.get("/")
    assert res.status_code == 200


def test_health_ok(client):
    from app import client as mongo_client
    mongo_client.admin.command = MagicMock(return_value={"ok": 1})
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_health_error(client):
    from app import client as mongo_client
    mongo_client.admin.command = MagicMock(side_effect=Exception("unreachable"))
    res = client.get("/health")
    assert res.status_code == 500
    data = res.get_json()
    assert data["status"] == "error"
