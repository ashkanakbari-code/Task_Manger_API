# Task Manager API

A REST API for managing tasks, built with **FastAPI**, **SQLAlchemy**, and **SQLite**, with **Redis** caching for fast reads. The whole project runs with one command using **Docker Compose**. Tasks are stored in a real database, so they persist between restarts.

I built this as a practice project to learn backend development: database models, request validation, dependency injection, proper HTTP status codes, caching, and containers.

## Features

- Create, read, update, and delete tasks (full CRUD)
- Filter tasks by completion status
- Partial updates: change only the fields you send
- Request validation with Pydantic (for example, a task title can't be empty)
- Correct HTTP status codes: `201` on create, `204` on delete, `404` for missing tasks, `422` for invalid data
- **Redis caching** of the task list with automatic invalidation on every change
- **Graceful fallback:** if Redis is down, the API logs a warning and reads from the database
- **Docker Compose** setup: API and Redis start together, and data persists in a volume
- Interactive API documentation, generated automatically

## Tech Stack

- [FastAPI](https://fastapi.tiangolo.com/): web framework
- [SQLAlchemy 2.x](https://www.sqlalchemy.org/): ORM for database access
- [Pydantic](https://docs.pydantic.dev/): data validation and response schemas
- [SQLite](https://www.sqlite.org/): database
- [Redis](https://redis.io/): in-memory cache
- [Uvicorn](https://www.uvicorn.org/): ASGI server
- [Docker](https://www.docker.com/) and Docker Compose: containers

## Project Structure

```
task_api/
├── main.py              # FastAPI app and route definitions
├── database.py          # Database engine, session factory, get_db dependency
├── models.py            # SQLAlchemy table definitions
├── schemas.py           # Pydantic models for requests and responses
├── redis_client.py      # Redis connection
├── Dockerfile           # Builds the API image
├── docker-compose.yml   # Runs the API and Redis together
├── .dockerignore
├── requirements.txt
└── README.md
```

How the pieces fit together:

```
Request → Pydantic schema (validation) → route → Redis cache (hit? return)
                                                      ↓ miss
                                          SQLAlchemy session → SQLite
                                                      ↓
Response ← Pydantic schema (output shape) ← result (also saved in Redis)
```

## How Caching Works

`GET /tasks` is cached in Redis for 60 seconds.

1. The route builds a cache key from the filter: `tasks:all`, `tasks:done:true`, or `tasks:done:false`.
2. If the key exists in Redis, the cached list is returned without touching the database.
3. If not, the tasks are read from SQLite, saved in Redis with a 60-second time to live (TTL), and returned.
4. Every create, update, or delete clears all three cache keys right after the database commit, so users never see stale data.
5. If Redis is unavailable, the cache calls fail safely, a warning is logged, and the API keeps working from the database.

## Getting Started

### Option 1: Run with Docker (recommended)

You only need [Docker](https://docs.docker.com/engine/install/) with Docker Compose. You don't need Python or Redis installed.

```bash
git clone https://github.com/ashkanakbari-code/task-manager-api.git
cd task-manager-api
docker compose up --build
```

Then open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Compose starts two containers:

- `api`: the FastAPI app, on port 8000
- `redis`: the Redis cache, reachable only by the API over the internal network

The SQLite database is stored in a Docker volume (`task_data`), so your tasks survive restarts.

Useful commands:

```bash
docker compose up -d              # start in the background
docker compose logs -f api        # follow the API logs
docker compose down               # stop and remove the containers (data is kept)
docker compose down -v            # also delete the volume (wipes the database)
```

Inspect the cache:

```bash
docker compose exec redis redis-cli keys "tasks:*"
docker compose exec redis redis-cli ttl tasks:all
```

### Option 2: Run locally without Docker

**Prerequisites:** Python 3.10 or newer, and a running Redis server on `localhost:6379`.

```bash
redis-cli ping    # should print PONG
```

If Redis isn't running, start it (the service name may be `redis` or `valkey` depending on your Linux distribution):

```bash
sudo systemctl start redis
```

Then:

```bash
git clone https://github.com/ashkanakbari-code/task-manager-api.git
cd task-manager-api

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
uvicorn main:app --reload
```

The database file `tasks.db` is created automatically on first run. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

<!-- Add a screenshot of the /docs page here:
![API docs](screenshots/docs.png)
-->

## Configuration

Settings are read from environment variables, with defaults that work for local development:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis host (set to `redis` in Docker Compose) |
| `REDIS_PORT` | `6379` | Redis port |
| `DATABASE_URL` | `sqlite:///./tasks.db` | Database URL (set to `sqlite:////data/tasks.db` in Docker Compose) |

## API Endpoints

| Method | Endpoint | Description | Success | Errors |
|--------|----------|-------------|---------|--------|
| `POST` | `/tasks` | Create a task | `201` | `422` |
| `GET` | `/tasks` | List all tasks (optional `?done=true/false`), cached | `200` | |
| `GET` | `/tasks/{task_id}` | Get one task | `200` | `404` |
| `PUT` | `/tasks/{task_id}` | Update a task (only the fields you send) | `200` | `404`, `422` |
| `DELETE` | `/tasks/{task_id}` | Delete a task | `204` | `404` |

### Task fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Generated by the database |
| `title` | string | Required, 1 to 100 characters |
| `description` | string or null | Optional, up to 500 characters |
| `done` | boolean | Defaults to `false` |

### Example requests

**Create a task**

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn SQLAlchemy", "description": "Finish the practice"}'
```

Response (`201 Created`):

```json
{
  "id": 1,
  "title": "Learn SQLAlchemy",
  "description": "Finish the practice",
  "done": false
}
```

**Mark a task as done**

```bash
curl -X PUT http://127.0.0.1:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"done": true}'
```

**List only finished tasks**

```bash
curl "http://127.0.0.1:8000/tasks?done=true"
```

**Delete a task**

```bash
curl -X DELETE http://127.0.0.1:8000/tasks/1
```
