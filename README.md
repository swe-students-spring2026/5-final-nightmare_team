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

- **web-app** — [`$landreani04/vibelist:web-app`](https://hub.docker.com/r/landreani04/vibelist)
- **ml-app** — [`$landreani04/vibelist:ml-app`](https://hub.docker.com/r/landreani04/vibelist)

## Prerequisites

You only need two things on any platform (macOS, Linux, Windows):

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Docker Compose v2 on Linux)
- [Git](https://git-scm.com/downloads)

A MongoDB Atlas connection string is also required — see [Environment Variables](#environment-variables).

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


## Run with Docker Compose

This is the easiest path and works the same on macOS, Linux, and Windows.

```bash
git clone https://github.com/swe-students-spring2026/5-final-nightmare_team.git
cd 5-final-nightmare_team
cp .env.example .env       # then edit .env with your real values
docker compose up --build
```

Go to local host port 5050:

- <http://localhost:5050>

To stop:

```bash
docker compose down
```

## Tests

Each subsystem has its own test suite with an enforced 80% coverage floor (the same threshold CI uses).

```bash
# ml-app
cd ml-app && pipenv run pytest tests/ --cov=. --cov-report=term-missing --cov-fail-under=80

# web-app
cd web-app && pipenv run pytest --cov=. --cov-report=term-missing --cov-fail-under=80
```

## License

See [LICENSE](./LICENSE).
