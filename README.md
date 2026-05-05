# VibeList

[![web-app CI/CD](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/web-app.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/web-app.yml)
[![ml-app CI/CD](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/ml-app.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/ml-app.yml)
[![lint-free](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/lint-free.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/lint-free.yml)
[![log github events](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/event-logger.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-nightmare_team/actions/workflows/event-logger.yml)

VibeList is a music recommendation web app. Sign in, tell it the vibe you're after, and it builds you a playlist. Like or dislike tracks as you listen and the recommender learns from your feedback to keep getting better.

## Just Want to Try It?

If you only want to **use** the app, you don't need to install anything. Open the live deployment in your browser, create an account, and start building playlists:

**<http://147.182.222.130:5050/>**

This instance runs the latest `main` on a Digital Ocean droplet and is redeployed automatically by CI/CD on every push.

The rest of this README is for **developers** who want to run, modify, or contribute to the project locally.

The system is split into three cooperating subsystems:

- **web-app** — A Flask web app that serves the UI, handles user accounts, and stores playlists. Talks to `ml-app` over HTTP for recommendations and to MongoDB for everything else.
- **ml-app** — A Flask service that holds the recommender. It stores users, songs, and feedback events in MongoDB, then trains an item-based collaborative-filtering model (cosine similarity over a user-song matrix using scikit-learn) to produce recommendations and find similar songs.
- **MongoDB Atlas** — Cloud-hosted MongoDB. Both services share the same `webapp` database.

## Team

- [Aleks Nuzhnyi](https://github.com/nuzhny25)
- [Luca Andreani](https://github.com/Landreani04)
- [Rohit Dayanand](https://github.com/RohitDayanand)
- [Lucas Bazoberry](https://github.com/lucasbazoberry)
- [Mikhail Bond](https://github.com/mikhailbond1)

## Container Images

Both custom subsystems are published to Docker Hub as tags on the same `vibelist` repository:

- **web-app** — [`$DOCKERHUB_USERNAME/vibelist:web-app`](https://hub.docker.com/r/_/vibelist) (replace `_` with the team's Docker Hub username, set in `.env`)
- **ml-app** — [`$DOCKERHUB_USERNAME/vibelist:ml-app`](https://hub.docker.com/r/_/vibelist)

Each push to `main` rebuilds both images via GitHub Actions and pushes both `:web-app`/`:ml-app` tags and an additional `:web-app-<sha>` / `:ml-app-<sha>` tag for traceability.

## Repository Layout

```text
.
├── docker-compose.yml          # orchestrates web-app + ml-app
├── .env.example                # template for required secrets
├── web-app/                    # Flask UI + user accounts + playlist storage
│   ├── Dockerfile
│   ├── Pipfile
│   ├── app.py
│   ├── templates/
│   ├── static/
│   └── tests/
├── ml-app/                     # Flask recommender service
│   ├── Dockerfile
│   ├── Pipfile
│   ├── main.py
│   ├── recommender.py
│   ├── seed.py                 # imports starter songs/users/events into Mongo
│   └── tests/
├── mongodb/
│   └── init/init.js            # collections & indexes for the webapp DB
└── .github/workflows/          # CI/CD pipelines
```

## Prerequisites

You only need two things on any platform (macOS, Linux, Windows):

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Docker Compose v2 on Linux)
- [Git](https://git-scm.com/downloads)

A MongoDB Atlas connection string is also required — see [Environment Variables](#environment-variables).

If you'd rather run the services directly on your machine instead of in containers, you'll also need Python 3.12 and `pipenv` (`pip install --user pipenv`).

## Environment Variables

The project reads its configuration from a `.env` file at the repository root. This file is **not** committed — copy the template and fill it in:

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable             | Required | Description                                                                                              |
| -------------------- | :------: | -------------------------------------------------------------------------------------------------------- |
| `MONGO_URI`          |    ✅    | MongoDB Atlas SRV connection string. Both services connect to the `webapp` database on this cluster.    |
| `FLASK_SECRET_KEY`   |    ✅    | Random string used by Flask to sign session cookies. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DOCKERHUB_USERNAME` |    ✅    | Your Docker Hub username. Used by `docker-compose.yml` to resolve the image tags.                       |

Example `.env` (with dummy values — do not commit a real one):

```dotenv
MONGO_URI=mongodb+srv://vibelist_user:CHANGE_ME@your-cluster.mongodb.net/webapp?retryWrites=true&w=majority
FLASK_SECRET_KEY=replace-with-a-long-random-hex-string
DOCKERHUB_USERNAME=your-dockerhub-username
```

> **Course admins:** the real `.env` (with the team's Atlas credentials and Flask secret) is delivered separately by the due date as required by the assignment instructions.

### MongoDB Atlas setup

1. Create a free cluster on [MongoDB Atlas](https://www.mongodb.com/atlas).
2. Create a database user and a password.
3. Under *Network Access*, allow your developer IP (and `0.0.0.0/0` for the Digital Ocean droplet, or the droplet's public IP).
4. Click *Connect → Drivers* and copy the SRV connection string into `MONGO_URI`. Make sure the path ends with `/webapp` so both services land in the same database.

### CI/CD secrets (GitHub Actions)

Maintainers also need to set the following repository secrets for the deploy pipelines:

| Secret               | Used by                  | Description                                                  |
| -------------------- | ------------------------ | ------------------------------------------------------------ |
| `DOCKERHUB_USERNAME` | both build-and-push jobs | Docker Hub login.                                            |
| `DOCKERHUB_TOKEN`    | both build-and-push jobs | Docker Hub access token (not your password).                 |
| `DO_HOST`            | both deploy jobs         | Digital Ocean droplet IP or hostname.                        |
| `DO_USER`            | both deploy jobs         | SSH user on the droplet.                                     |
| `DO_SSH_KEY`         | both deploy jobs         | Private SSH key authorized on the droplet.                   |
| `COMMIT_LOG_API`     | event-logger             | Endpoint URL used by the course's commit-stats logger.       |

The droplet must have a `/app/.env` file with the same `MONGO_URI` and `FLASK_SECRET_KEY` so the deployed containers can read them.

## Run with Docker Compose (recommended)

This is the easiest path and works the same on macOS, Linux, and Windows.

```bash
git clone https://github.com/swe-students-spring2026/5-final-nightmare_team.git
cd 5-final-nightmare_team
cp .env.example .env       # then edit .env with your real values
docker compose up --build
```

When both containers are healthy:

- Web app: <http://localhost:5050>
- ML API: <http://localhost:8000>
- ML health check: <http://localhost:8000/health>

To stop:

```bash
docker compose down
```

### Seeding starter data

The recommender needs songs and a few example events before it can produce real recommendations. Run the seed script **once**, after `docker compose up` is running, in a second terminal:

```bash
docker compose exec ml-app pipenv run python -m app.seed
```

This populates the `songs`, `users`, and `events` collections in MongoDB and trains the model. After it finishes, the app will return `"source": "model"` recommendations instead of `"source": "mock"`.

To force a retrain at any time:

```bash
curl -X POST http://localhost:8000/train
```

## Run Locally Without Docker

Useful when iterating on a single subsystem.

### ml-app

```bash
cd ml-app
pipenv install --dev
MONGO_URI="<your atlas string>" pipenv run python -m app.main
```

The service listens on <http://localhost:8000>. To seed:

```bash
MONGO_URI="<your atlas string>" pipenv run python -m app.seed
```

### web-app

In a second terminal:

```bash
cd web-app
pipenv install --dev
MONGO_URI="<your atlas string>" \
FLASK_SECRET_KEY="<your secret>" \
ML_APP_URL="http://localhost:8000" \
pipenv run python app.py
```

The UI is at <http://localhost:5000>.

> On Windows PowerShell, set environment variables with `$env:MONGO_URI="..."` instead of the inline `KEY=value command` form.

## Tests

Each subsystem has its own test suite with an enforced 80% coverage floor (the same threshold CI uses).

```bash
# ml-app
cd ml-app && pipenv run pytest tests/ --cov=. --cov-report=term-missing --cov-fail-under=80

# web-app
cd web-app && pipenv run pytest --cov=. --cov-report=term-missing --cov-fail-under=80
```

## CI/CD Pipelines

Each custom subsystem has its own GitHub Actions workflow that runs on every push and pull request to `main`:

- [`web-app.yml`](.github/workflows/web-app.yml) — lint (pylint + black) → test with coverage → build & push image to Docker Hub → deploy to Digital Ocean.
- [`ml-app.yml`](.github/workflows/ml-app.yml) — same pipeline against an ephemeral MongoDB service container.
- [`lint-free.yml`](.github/workflows/lint-free.yml) — repo-wide lint/format gate.
- [`event-logger.yml`](.github/workflows/event-logger.yml) — reports commit/PR stats to the course logging endpoint.

Build-and-push and deploy jobs only run on `push` events, not on pull requests.

## API Reference (ml-app)

A handful of endpoints exposed by `ml-app` directly. The web-app proxies most of them under `/api/*`.

| Method | Path                              | Purpose                                                |
| ------ | --------------------------------- | ------------------------------------------------------ |
| GET    | `/health`                         | Liveness check.                                        |
| POST   | `/users`                          | Create a user.                                         |
| POST   | `/songs`                          | Create a song.                                         |
| GET    | `/songs`                          | List all songs.                                        |
| POST   | `/events`                         | Record a `play`/`like`/`dislike`/`skip`/`save`/`repeat` event. |
| GET    | `/recommendations/<user_id>?k=10` | Top-k recommendations for a user.                      |
| GET    | `/songs/<song_id>/similar?k=10`   | Top-k songs similar to a given song.                   |
| POST   | `/train`                          | Rebuild the collaborative-filtering model.             |
| POST   | `/generate-playlist`              | Build a playlist from tags and/or seed songs.          |

Until the model has been trained on real data, recommendation responses are tagged `"source": "mock"` and return seeded sample songs so the UI keeps working. After training, responses switch to `"source": "model"`.

## Recommender, in Plain Language

1. Every user action (play, like, save, skip, dislike, repeat) is stored as a weighted event in MongoDB.
2. `POST /train` builds a user × song matrix from all stored events.
3. Cosine similarity between *song columns* tells us which songs behave similarly across users.
4. To recommend for a user, we look at songs they've responded to positively and surface unseen songs that are most similar to those.

Event weights:

| Event    | Weight |
| -------- | -----: |
| like     |     5  |
| save     |     4  |
| repeat   |     3  |
| play     |     1  |
| skip     |    -1  |
| dislike  |    -5  |

## License

See [LICENSE](./LICENSE).
