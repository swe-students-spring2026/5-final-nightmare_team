"""Patch MongoClient before any test module imports app."""

from unittest.mock import MagicMock, patch

MONGO_PATCHER = patch("pymongo.MongoClient")
MOCK_MONGO = MONGO_PATCHER.start()
MOCK_MONGO.return_value = MagicMock()
