"""Configure sys.path and the 'app' module alias for ml-app tests.

main.py and recommender.py import via 'from app import ...' because the
Docker container mounts the ml-app directory as /app.  When running pytest
locally we recreate that alias so the tests work without Docker.
"""

import os
import sys
import types

_ML_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ML_APP_DIR not in sys.path:
    sys.path.insert(0, _ML_APP_DIR)

if "app" not in sys.modules:
    import database as _database  # noqa: E402
    import models as _models  # noqa: E402

    _pkg = types.ModuleType("app")
    _pkg.database = _database
    _pkg.models = _models
    sys.modules["app"] = _pkg
    sys.modules["app.database"] = _database
    sys.modules["app.models"] = _models

    import recommender as _recommender  # noqa: E402

    _pkg.recommender = _recommender
    sys.modules["app.recommender"] = _recommender
