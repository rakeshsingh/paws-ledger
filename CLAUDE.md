# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

PawsLedger is a pet microchip registry and recovery platform. Owners register pets by microchip ID, manage vaccination records, share access via time-limited tokens, and enable lost-pet identification through NFC/QR tags. Production domain: pawsledger.com.

## Commands

```bash
# Run locally (starts FastAPI + NiceGUI on 0.0.0.0:8080)
uvicorn app.main:fastapi_app --host 0.0.0.0 --port 8080 --reload

# Or:
python -m app.main

# Run tests
pytest

# Run a single test file
pytest tests/api/test_pets.py

# Seed the database with sample data
python seed_db.py

# Docker (production config uses Cloudflare Tunnel)
docker compose up --build
```

## Architecture

**Stack**: FastAPI + NiceGUI (server-rendered reactive UI) + SQLModel (SQLAlchemy + Pydantic) + SQLite (WAL mode).

**Entry point**: `app/main.py` — creates the FastAPI app, mounts NiceGUI via `ui.run_with()`, and registers API routes + middleware.

**Key layers**:

- `app/api/v1/` — REST API. `routes.py` aggregates sub-routers (auth, pets, owner). `common.py` holds shared singleton services (GoogleAuth, AAHA client, email, PDF, hash, serializer) and `get_current_user` auth dependency.
- `app/ui/` — NiceGUI pages. `pages.py` is the initializer that calls each page module's `init_*_page()` function. Each page module (e.g., `pet_profile.py`, `owner_dashboard.py`) defines one route.
- `app/services/integrations.py` — external service clients: DogAPI (breeds), AAHA microchip lookup (mock), PDF generation, email via Resend, Google OAuth, and microchip manufacturer identification from ISO prefixes.
- `app/models.py` — SQLModel tables: User, Pet, LedgerEvent, Vaccination, SharedAccess, PetTag.
- `app/data/` — Vaccination schedule data. JSON files (`canine_vaccinations.json`, `feline_vaccinations.json`) loaded by `__init__.py` which exposes query functions.
- `app/database.py` — engine setup with SQLite WAL pragmas for concurrent access.

**Auth flow**: Google OAuth (Authlib) → signed `paws_user_id` cookie (itsdangerous URLSafeSerializer) → NiceGUI pages read cookie to identify user. Top-level `/auth/callback` route exists alongside `/api/v1/auth/callback` to match Google's registered redirect URI.

**Environment**: `APP_ENV` (beta/prod) controls which `.env.{env}` file is loaded. `STORAGE_SECRET` is required in prod (enforced at startup).

## Common Tasks → Entry Points

| Task | Files to modify |
|------|----------------|
| Add a new API endpoint | `app/api/v1/pets.py` (or new sub-router), register in `app/api/v1/routes.py` |
| Add a new UI page | Create module in `app/ui/`, add `init_*_page()` function, register in `app/ui/pages.py` |
| Add/change a model field | `app/models.py` — SQLModel auto-creates on next startup |
| Add/change vaccine data | Edit JSON in `app/data/canine_vaccinations.json` or `feline_vaccinations.json` |
| Change auth logic | `app/api/v1/common.py` (`get_current_user`), `app/api/v1/auth.py` |
| Change external integrations | `app/services/integrations.py` |
| Add shared UI constants | `app/ui/common.py` |
| Add a test | Mirror source path: `tests/api/`, `tests/services/`, `tests/models/` |

## Testing

Tests live in a structure mirroring the source:

```
tests/
├── conftest.py          # Shared fixtures: session, client, test_user, test_pet, mock_google_auth
├── api/
│   ├── test_auth.py     # Auth callback, login, cookie security
│   ├── test_owner.py    # Owner profile CRUD, validation
│   ├── test_pets.py     # Chip lookup, QR scan, vaccinations, shared access
│   └── test_tags.py     # Tag CRUD, tag resolution (QR/NFC scan)
├── models/
│   └── test_models.py   # Model constraints, relationships, data loader
└── services/
    └── test_integrations.py  # Hash, PDF, manufacturer lookup, breed API
```

Tests use an in-memory SQLite database (`conftest.py` overrides `get_session`). The `client` fixture provides a `TestClient` against the FastAPI app. `test_user` and `test_pet` fixtures create standard entities.

## Deployment

Docker Compose runs the app container (port 8080, internal only) and a `cloudflared` tunnel container that exposes it to the internet. The app sits behind Cloudflare → Nginx → Gunicorn. SSL terminates at Cloudflare; internal connections are HTTP.
