# ML App

Flask service for VibeList music recommendations. It stores users, songs, and interaction events in MongoDB, then trains an item-based collaborative filtering model with pandas and scikit-learn.

The service is intentionally small: the web app calls it over HTTP, MongoDB stores the data, and the in-process recommender is retrained from stored events when `/train` is called.

## Runtime Model

The Docker image copies this directory to `/service/app`, then starts:

```bash
python -m app.main
```

That container layout is why the Python files import modules with `from app import ...`. Local tests recreate that `app` alias in `tests/conftest.py`.

## Data Stores

The service uses the `webapp` MongoDB database from `MONGO_URI`.

Collections:

| Collection | Purpose | Important fields |
| --- | --- | --- |
| `users` | App users | `user_id`, `name` |
| `songs` | Song catalog | `song_id`, `title`, `artist`, `genre`, `mood`, `era`, `energy` |
| `events` | User-song feedback | `user_id`, `song_id`, `event_type`, `weight` |

Indexes are created lazily before the first request:

- unique sparse index on `users.user_id`
- unique index on `songs.song_id`
- compound index on `events.user_id` and `events.song_id`

## Recommendation Flow

1. Create or seed users and songs.
2. Record feedback events with `/events`.
3. Call `/train` to rebuild the collaborative filtering model from all stored events.
4. Call `/recommendations/<user_id>` or `/songs/<song_id>/similar`.

If the model has not been trained, or trained recommendations cannot produce results, recommendation endpoints return `source: "mock"` with fallback songs. After training succeeds and model results exist, they return `source: "model"`.

Feedback weights:

| Event type | Weight | Recommendation signal |
| --- | ---: | --- |
| `play` | `1.0` | positive |
| `skip` | `-1.0` | negative |
| `like` | `5.0` | positive |
| `dislike` | `-5.0` | negative |
| `save` | `4.0` | positive |
| `repeat` | `3.0` | positive |

The model builds a user-song matrix from event weights, computes cosine similarity between song columns, and recommends unseen songs similar to songs the user interacted with positively.

## Run With Docker Compose

From the repository root:

```bash
docker compose up --build ml-app
```

Required environment:

```bash
MONGO_URI=mongodb+srv://...
DOCKERHUB_USERNAME=your-dockerhub-user
```

The service listens on port `8000` in the container and is published as `http://localhost:8000` by `docker-compose.yml`.

Health check:

```bash
curl http://localhost:8000/health
```

## Seed Data

The seed script resets the `users`, `songs`, and `events` collections, creates indexes, then inserts sample users, songs, and interactions.

Inside the running container:

```bash
docker compose exec ml-app pipenv run python -m app.seed
```

After seeding, train the model:

```bash
curl -X POST http://localhost:8000/train
```

## API

### `GET /health`

Returns service status.

```json
{
  "status": "ok"
}
```

### `POST /users`

Creates a user.

Request:

```json
{
  "user_id": "u1",
  "name": "Avery"
}
```

Responses:

- `201` with the created user
- `400` when `user_id` is missing
- `409` when the user already exists

### `POST /songs`

Creates a song.

Request:

```json
{
  "song_id": "s001",
  "title": "One More Time",
  "artist": "Daft Punk",
  "genre": "Electronic",
  "mood": ["happy", "energetic", "party"],
  "era": "00s",
  "energy": "high"
}
```

Responses:

- `201` with the created song
- `400` when `song_id`, `title`, or `artist` is missing
- `409` when the song already exists

### `GET /songs`

Returns all songs in MongoDB.

### `POST /events`

Records a user-song interaction.

Request:

```json
{
  "user_id": "u1",
  "song_id": "s001",
  "event_type": "like"
}
```

Responses:

- `201` with the event id and numeric weight
- `400` when required fields are missing or `event_type` is unsupported
- `404` when the user or song does not exist

### `POST /train`

Trains the recommender from all stored events and songs.

Successful response:

```json
{
  "status": "trained",
  "source": "model",
  "users": 4,
  "songs": 80,
  "events": 24
}
```

Returns `409` when there are not enough events or songs to train. The model needs at least one event and events across at least two songs.

### `GET /recommendations/<user_id>?k=10`

Returns top recommendations for a known user.

Example response:

```json
{
  "user_id": "u1",
  "source": "model",
  "recommendations": [
    {
      "song_id": "s009",
      "title": "The Less I Know the Better",
      "artist": "Tame Impala",
      "genre": "Indie",
      "score": 0.7071
    }
  ]
}
```

Returns `404` when the user does not exist.

### `GET /songs/<song_id>/similar?k=10`

Returns songs most similar to a known song.

Example response:

```json
{
  "song_id": "s001",
  "source": "model",
  "similar": [
    {
      "song_id": "s002",
      "title": "Get Lucky",
      "artist": "Daft Punk",
      "genre": "Electronic",
      "score": 0.8165
    }
  ]
}
```

Returns:

- `404` when the song does not exist
- `409` when there is not enough trained data to find similar songs

### `POST /generate-playlist`

Generates a playlist from tags, seed song text, or random catalog order.

Request:

```json
{
  "tags": ["electronic", "party"],
  "seed_songs": ["Daft Punk"],
  "size": 20
}
```

Notes:

- `tags` are matched against `genre`, `mood`, `era`, and `energy`.
- `seed_songs` are matched against title and artist text.
- `size` is clamped between `5` and `50`.
- `source` is one of `tags`, `seeds`, `mixed`, or `random`.

Example response:

```json
{
  "tracks": [
    {
      "song_id": "s001",
      "title": "One More Time",
      "artist": "Daft Punk",
      "genre": "Electronic",
      "mood": ["happy", "energetic", "party"],
      "era": "00s",
      "score": 7.231
    }
  ],
  "source": "mixed",
  "size": 20
}
```

## Tests

Install dependencies with Pipenv from this directory:

```bash
cd ml-app
pipenv install --dev
```

Run the ML app tests:

```bash
pipenv run pytest
```

The tests mock MongoDB and do not require a live `MONGO_URI`.

## Troubleshooting

`POST /train` returns `409`: add at least two songs and enough feedback events, then retry `/train`.

Recommendations return `source: "mock"`: train the model, make sure the user exists, and make sure that user has positive events such as `like`, `save`, `repeat`, or `play`.

`POST /events` returns `404`: create the user and song before recording feedback.

Import errors when running Python files directly from `ml-app`: use Docker Compose for the app runtime, or run tests through pytest so `tests/conftest.py` creates the same module alias used by the container.
