# Strobe — Feature Flag & A/B Testing API

Free, publicly available feature flag and A/B testing service. No auth required.

## Stack

- **Runtime**: Python 3.11, FastAPI, Uvicorn
- **Database**: MongoDB via Motor (async driver)
- **Hosting**: Railway (Dockerfile deploy)
- **DB hosting**: Railway MongoDB plugin (env: `MONGO_URI` or `MONGO_URL`)

## Project structure

```
main.py               FastAPI app, lifespan (DB connect/disconnect), CORS, rate limiting
config.py             Settings via pydantic-settings, reads from .env / Railway env vars
api/
  flags.py            CRUD endpoints for feature flags (/flags)
  evaluate.py         Evaluation endpoints (/evaluate)
  limiter.py          Global slowapi Limiter instance (shared across routers)
db/
  database.py         Module-level singletons: client, db, flags repo, audit repo
  repository.py       FlagRepository + AuditRepository (Motor queries)
engine/
  evaluator.py        Pure evaluation logic — no DB, no side effects
models/
  flag.py             FeatureFlag, FlagCreate, FlagUpdate, FlagSummary, AuditLog, Variant, TargetingRule
  evaluation.py       EvaluationContext, EvaluationResult, BulkEvaluationRequest/Response
tests/
  test_api.py         Integration tests (TestClient + real MongoDB)
  test_database.py    Lifespan + DB connection tests
  test_evaluator.py   Pure unit tests for FlagEvaluator (no DB)
  test_models.py      Pure unit tests for Pydantic model validation (no DB)
```

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `MONGO_URI` / `MONGO_URL` | `mongodb://localhost:27017` | Railway sets `MONGO_URL` |
| `MONGO_DB` | `strobe` | Database name |
| `MAX_FLAGS` | `10000` | Global cap — 503 when exceeded |
| `FLAG_TTL_DAYS` | `90` | Flags auto-deleted after N days of inactivity (TTL index on `updated_at`) |

## Rate limits (slowapi, per IP)

| Endpoint group | Limit |
|---|---|
| Writes (`POST /flags`, `PATCH`, `DELETE`) | 10/minute |
| Reads (`GET /flags*`) | 60/minute |
| Evaluate (`POST /evaluate/*`) | 120/minute |

Rate limit exceeded returns HTTP 429.

## Abuse prevention

- **Global flag cap**: `MAX_FLAGS` (default 10k). Returns 503 when hit. Message tells users flags auto-expire.
- **TTL index**: MongoDB TTL index on `updated_at`. Flags not touched in `FLAG_TTL_DAYS` days are auto-deleted by MongoDB. Resets on any update/toggle.
- **Rate limiting**: slowapi middleware on all endpoints.

## Flag evaluation logic (`engine/evaluator.py`)

Order of precedence:
1. Flag disabled → `reason: disabled`
2. Targeting rules (first match wins) → `reason: targeting_rule`
3. Rollout gate (consistent hash of user_id) → `reason: rollout_excluded` if outside %
4. Variant assignment (weighted consistent hash) → `reason: ab_assignment`
5. No variants → `reason: default`

Hashing is deterministic: same `flag_key + user_id` always produces same result.

## Running locally

```bash
# Install deps
pip install -r requirements.txt

# Start (reads .env automatically)
fastapi dev main.py

# Or production mode
fastapi run main.py
```

## Running tests

```bash
# Requires local MongoDB on 27017 (or set MONGO_URI env var)
pytest
```

CI runs tests against a MongoDB service container (see `.github/workflows/test.yml`).

## Railway deploy

Deploys via Dockerfile. Railway injects `MONGO_URL` automatically when MongoDB plugin is added. `config.py` accepts both `MONGO_URI` and `MONGO_URL` as aliases.

`railway.json` uses `DOCKERFILE` builder with `ON_FAILURE` restart policy.

## Key design decisions

- **No auth** — intentionally public and free. Abuse is controlled via rate limits + global cap + TTL.
- **Consistent hashing** — SHA-256 ensures same user always gets same variant. Stable across restarts.
- **Motor** — fully async MongoDB driver; all DB calls are `await`ed.
- **Annotated style** — all FastAPI query/path params use `Annotated[type, Query(...)]` per FastAPI best practices.
- **TTL on `updated_at`** — any write (create, update, toggle) resets the expiry timer. Truly unused flags die.
