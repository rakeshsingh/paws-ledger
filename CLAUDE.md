# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

PawsLedger is a pet microchip registry and recovery platform with tiered subscriptions (Free, Verified, Guardian). Owners register pets by microchip ID, manage vaccination records, share access via time-limited tokens, enable lost-pet identification through NFC/QR tags, and subscribe via Stripe for premium features (bidirectional messaging, GPS recovery, care guides, document storage, ownership transfer). Production domain: pawsledger.com.

## Agents

This project uses specialized agents defined in `agents/`. When working on features, adopt the appropriate agent persona based on the task:

| Agent | When to Use | Definition |
|-------|-------------|------------|
| **Manager** | Orchestrating multi-step features, sequencing work, making go/no-go decisions | `agents/manager.md` |
| **Planner** | Decomposing a feature into ordered tasks, identifying affected files, mapping to spec ACs | `agents/planner.md` |
| **Builder** | Writing implementation code (models, API, UI, services) | `agents/builder.md` |
| **Reviewer** | Auditing code for security, correctness, spec compliance | `agents/reviewer.md` |
| **Tester** | Writing and running test suites, identifying coverage gaps | `agents/tester.md` |
| **UX Tester** | Validating UI workflows end-to-end from three personas after major changes | `agents/ux-tester.md` |

### Standard Feature Workflow

```
Request → Manager (intake & delegate)
       → Planner (decompose into tasks with AC mapping)
       → Builder (implement in dependency order)
       → Reviewer (audit security, correctness, spec compliance)
       → Tester (write tests, verify ACs)
       → UX Tester (validate UI workflows from all 3 personas)
       → Manager (gate completion: all tests pass, UX validated, no Critical/High findings)
```

### How to Invoke an Agent

When asked to implement a feature, use the **Manager** flow:
1. Read the relevant spec (`docs/spec/business_requirements_v1_*.md`)
2. Act as **Planner** to decompose into tasks
3. Act as **Builder** to implement each task
4. Act as **Reviewer** to self-audit the code
5. Act as **Tester** to write and run tests
6. Act as **UX Tester** to validate affected UI workflows from all three personas

When asked to do a specific sub-task:
- "Plan this feature" → Use `agents/planner.md` persona
- "Build this" / "Implement this" → Use `agents/builder.md` persona
- "Review this code" → Use `agents/reviewer.md` persona
- "Write tests for this" → Use `agents/tester.md` persona
- "Test the UI" / "Validate workflows" → Use `agents/ux-tester.md` persona

### Completion Criteria (Definition of Done)

A feature is complete when:
- All acceptance criteria from the spec are implemented
- All tests pass (`pytest` exits 0)
- No Critical or High severity review findings remain
- Tier gating enforced (premium features locked for free users)
- Ownership checks prevent IDOR on all mutation endpoints
- Ledger events record state changes for audit trail
- No PII exposed in public views or logs
- Backward compatibility maintained

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

# Run by name pattern
pytest -k "test_nudge"

# Seed the database with sample data
python seed_db.py

# Run database migration (adds new columns/tables to existing DB)
python migrate.py

# Docker (production config uses Cloudflare Tunnel)
docker compose up --build
```

## Architecture

**Stack**: FastAPI + NiceGUI (server-rendered reactive UI) + SQLModel (SQLAlchemy + Pydantic) + SQLite (WAL mode).

**Entry point**: `app/main.py` — creates the FastAPI app, mounts NiceGUI via `ui.run_with()`, and registers API routes + middleware.

**Key layers**:

- `app/api/v1/` — REST API. `routes.py` aggregates sub-routers (auth, pets, owner, nudge, subscription, verified). `common.py` holds shared singleton services and `get_current_user` auth dependency.
- `app/ui/` — NiceGUI pages. `pages.py` is the initializer that calls each page module's `init_*_page()` function. `dashboard_shell.py` provides the shared authenticated layout wrapper. `pet_profile/` is a subpackage (`_page.py`, `helpers.py`, `nudge.py`).
- `app/seo_pages.py` — Pre-rendered HTML routes for public content pages (about, faq, pricing, etc.) using Jinja2 templates in `app/templates/`.
- `app/services/` — External service clients:
  - `integrations.py` — DogAPI, AAHA lookup (mock), PDF generation, email (Resend), Google OAuth, chip manufacturer ID
  - `stripe_service.py` — Stripe customer/subscription lifecycle
  - `r2_storage.py` — Cloudflare R2 file storage (with local filesystem fallback for dev)
- `app/models.py` — SQLModel tables: User, Pet, LedgerEvent, Vaccination, SharedAccess, PetTag, NudgeSession, Subscription, OwnershipTransfer, VaccinationAlert, TagScan, VaccinationDocument.
- `app/data/` — Vaccination schedule JSON data.
- `app/database.py` — Engine setup with SQLite WAL pragmas.

**Note**: Care instructions are stored as flat fields on the `Pet` model (not a separate `CareInstruction` table).

**Auth flow**: Google OAuth (Authlib) → signed `paws_user_id` cookie (itsdangerous URLSafeSerializer) → NiceGUI pages call `try_restore_session()` to hydrate `app.storage.user`.

**Subscription tiers**:
- **Free**: Basic registry, one-way nudge (email only), QR/NFC tags
- **Verified** ($1/month or $9.99/year): Bidirectional messaging, GPS sharing, care guides, 1 doc upload, vaccination alerts (view only), verified badge, ownership transfer, pet photo upload
- **Guardian** ($4.99/month or $49.99/year): Up to 100 docs, automated alert delivery (email/SMS), heartbeat monitoring, signed PDFs, lost pet broadcast, emergency vet authorization

**Environment**: `APP_ENV` (beta/prod) controls which `.env.{env}` file is loaded. `STORAGE_SECRET` is required in prod.

## Spec Documents (Source of Truth)

| Document | Contents |
|----------|----------|
| `docs/spec/business_requirements_v1.md` | Phase 0 core requirements |
| `docs/spec/business_requirements_v1_free_tier.md` | Free tier nudge system |
| `docs/spec/business_requirements_v1_verified_tier.md` | Verified tier features (US-V01 through US-V13) |
| `docs/spec/business_requirements_v1_guardian_tier.md` | Guardian tier features (US-G01 through US-G06) |
| `docs/spec/technical_requirements_v1.md` | Architecture and data models |
| `docs/spec/ux_requirements_v1.md` | UI/UX flow requirements |
| `docs/spec/deployment_requirements_v1.md` | Infrastructure and deployment |

## Common Tasks → Entry Points

| Task | Files to modify |
|------|----------------|
| Add a new API endpoint | `app/api/v1/<domain>.py` (or new sub-router), register in `app/api/v1/routes.py` |
| Add a new UI page | Create module in `app/ui/`, add `init_*_page()` function, register in `app/ui/pages.py` |
| Add/change a model field | `app/models.py` — then run `python migrate.py` for existing DBs |
| Add/change vaccine data | Edit JSON in `app/data/` |
| Change auth logic | `app/api/v1/common.py` (`get_current_user`), `app/api/v1/auth.py` |
| Change external integrations | `app/services/integrations.py` |
| Add Stripe logic | `app/services/stripe_service.py`, `app/api/v1/subscription.py` |
| Add R2 storage logic | `app/services/r2_storage.py` |
| Gate a feature by tier | Use `get_user_tier()` from `app/api/v1/subscription.py` or `_require_verified()` from `app/api/v1/verified.py` |
| Add shared UI constants | `app/ui/common.py` |
| Change theme/styling | `app/ui/static/global.css` (design tokens) |
| Add a test | Mirror source path: `tests/api/`, `tests/services/`, `tests/models/` |

## Testing

Tests live in a structure mirroring the source:

```
tests/
├── conftest.py          # Shared fixtures: session, client, test_user, test_pet, mock_google_auth
├── api/
│   ├── test_auth.py     # Auth callback, login, cookie security
│   ├── test_nudge.py    # Nudge system: send, rate limit, reply, history
│   ├── test_owner.py    # Owner profile CRUD, validation
│   ├── test_pets.py     # Chip lookup, QR scan, vaccinations, shared access
│   ├── test_tags.py     # Tag CRUD, tag resolution (QR/NFC scan)
│   ├── test_subscription.py  # Stripe subscription flows
│   └── test_verified.py      # Verified tier features (transfer, care, alerts, upload)
├── models/
│   └── test_models.py   # Model constraints, relationships, data loader
└── services/
    └── test_integrations.py  # Hash, PDF, manufacturer lookup, breed API
```

Tests use an in-memory SQLite database (`conftest.py` overrides `get_session`). The `client` fixture provides a `TestClient` against the FastAPI app. Auth is simulated via `client.cookies.set("paws_user_id", serializer.dumps(str(user.id)))`.

## Deployment

**Production**: Hetzner VPS → Cloudflare Tunnel → Nginx (8081) → Gunicorn+Uvicorn (8080) → FastAPI+NiceGUI. SSL terminates at Cloudflare. Only SSH exposed.

**Services**: Stripe (payments), Cloudflare R2 (file storage), Resend (email), Google OAuth (auth).

**Deploy updates**:
```bash
ssh root@<vps-ip>
sudo su - paws && cd ~/paws-ledger
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python migrate.py
exit
sudo systemctl restart pawsledger
```
