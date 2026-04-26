# ⚑ Strobe

**Free, open feature flag & A/B testing API.** No signup. No SDK. Just HTTP.

[![Tests](https://github.com/aarushbhutra/strobe/actions/workflows/test.yml/badge.svg)](https://github.com/aarushbhutra/strobe/actions/workflows/test.yml)

**Live API →** `https://strobeapi-production.up.railway.app`  
**Swagger UI →** [strobeapi-production.up.railway.app/docs](https://strobeapi-production.up.railway.app/docs)

---

## What is Strobe?

Strobe lets you control your app's behaviour at runtime without redeploying. Ship features to a percentage of users, run A/B tests, kill-switch broken functionality — all through a simple REST API.

- **No account required** — call the API directly
- **Any language** — plain HTTP, works everywhere
- **Consistent hashing** — same user always gets the same variant
- **Audit log** — every change is tracked
- **Auto-expiry** — flags unused for 90 days are cleaned up automatically

---

## Quick Start

### 1. Create a flag

```bash
curl -X POST https://strobeapi-production.up.railway.app/flags \
  -H "Content-Type: application/json" \
  -d '{
    "key": "new-checkout",
    "name": "New Checkout Flow",
    "enabled": true,
    "variants": [
      { "key": "control",   "name": "Old Checkout", "weight": 50 },
      { "key": "treatment", "name": "New Checkout", "weight": 50 }
    ]
  }'
```

### 2. Evaluate for a user

```bash
curl -X POST https://strobeapi-production.up.railway.app/evaluate/new-checkout \
  -H "Content-Type: application/json" \
  -d '{ "user_id": "user-123", "attributes": {} }'
```

```json
{
  "flag_key": "new-checkout",
  "enabled": true,
  "variant": "treatment",
  "reason": "ab_assignment",
  "payload": {}
}
```

The same `user_id` always returns the same variant — stable across requests, restarts, and deployments.

---

## Using it in your app

### Vanilla JS

```js
const { results } = await fetch('https://strobeapi-production.up.railway.app/evaluate/bulk', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    context: { user_id: 'user-123', attributes: { plan: 'pro' } },
    flag_keys: ['new-checkout', 'dark-mode', 'promo-banner'],
  }),
}).then(r => r.json());

if (results['new-checkout']?.variant === 'treatment') {
  showNewCheckout();
}
```

### React hook

```jsx
import { useEffect, useState } from 'react';

const API = 'https://strobeapi-production.up.railway.app';

export function useFlags(userId, flagKeys = []) {
  const [flags, setFlags] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/evaluate/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        context: { user_id: userId, attributes: {} },
        flag_keys: flagKeys,
      }),
    })
      .then(r => r.json())
      .then(d => setFlags(d.results))
      .finally(() => setLoading(false));
  }, [userId]);

  return { flags, loading };
}

// Usage
function App() {
  const { flags } = useFlags('user-123', ['new-checkout', 'dark-mode']);
  return flags['dark-mode']?.enabled ? <DarkApp /> : <LightApp />;
}
```

### Next.js (Server Component)

```js
async function getFlags(userId) {
  const res = await fetch('https://strobeapi-production.up.railway.app/evaluate/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      context: { user_id: userId },
      flag_keys: ['new-checkout'],
    }),
    next: { revalidate: 30 },
  });
  return (await res.json()).results;
}

export default async function Page() {
  const flags = await getFlags('user-123');
  return flags['new-checkout']?.enabled ? <NewCheckout /> : <OldCheckout />;
}
```

### Python

```python
import httpx

resp = httpx.post(
    "https://strobeapi-production.up.railway.app/evaluate/my-flag",
    json={"user_id": "user-123", "attributes": {"plan": "pro"}},
)
result = resp.json()

if result["enabled"] and result["variant"] == "treatment":
    run_new_feature()
```

---

## API Reference

### Flags

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/flags` | Create a flag |
| `GET` | `/flags` | List all flags |
| `GET` | `/flags/{key}` | Get a flag |
| `PATCH` | `/flags/{key}` | Update a flag |
| `PATCH` | `/flags/{key}/toggle` | Toggle enabled/disabled |
| `DELETE` | `/flags/{key}` | Delete a flag |
| `GET` | `/flags/{key}/history` | Audit log for a flag |

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/evaluate/{key}` | Evaluate one flag for a user |
| `POST` | `/evaluate/bulk` | Evaluate multiple flags at once |

### Evaluation result

```json
{
  "flag_key": "my-flag",
  "enabled": true,
  "variant": "treatment",
  "reason": "ab_assignment",
  "payload": {},
  "evaluated_at": "2026-04-26T10:00:00"
}
```

**Reasons:**

| Reason | Meaning |
|--------|---------|
| `disabled` | Flag is turned off |
| `rollout_excluded` | User outside rollout percentage |
| `targeting_rule` | Matched a targeting rule |
| `ab_assignment` | Assigned to a variant via consistent hash |
| `default` | Flag enabled, no variants defined |

---

## Targeting Rules

Route specific users to specific variants based on their attributes:

```bash
curl -X POST https://strobeapi-production.up.railway.app/flags \
  -H "Content-Type: application/json" \
  -d '{
    "key": "beta-dashboard",
    "name": "Beta Dashboard",
    "enabled": true,
    "variants": [
      { "key": "control",  "name": "Old Dashboard", "weight": 100 }
    ],
    "targeting_rules": [
      {
        "attribute": "plan",
        "operator": "in",
        "value": ["pro", "enterprise"],
        "variant": "control"
      }
    ]
  }'
```

**Operators:** `eq` `neq` `in` `not_in` `gt` `lt`

Pass attributes when evaluating:

```bash
curl -X POST https://strobeapi-production.up.railway.app/evaluate/beta-dashboard \
  -H "Content-Type: application/json" \
  -d '{ "user_id": "user-123", "attributes": { "plan": "pro" } }'
```

---

## Rollout

Gradually release to a percentage of users:

```bash
curl -X POST https://strobeapi-production.up.railway.app/flags \
  -H "Content-Type: application/json" \
  -d '{
    "key": "new-ui",
    "name": "New UI",
    "enabled": true,
    "rollout": { "percentage": 10 }
  }'
```

Start at 10%, increase over time. Users consistently stay in or out of the rollout.

---

## Rate Limits

| Endpoint group | Limit |
|----------------|-------|
| Writes (`POST`, `PATCH`, `DELETE` on `/flags`) | 10 / minute per IP |
| Reads (`GET /flags*`) | 60 / minute per IP |
| Evaluate (`POST /evaluate/*`) | 120 / minute per IP |

Exceeding a limit returns `429 Too Many Requests`.

---

## Limits & Fair Use

- **10,000 flags** maximum globally. Returns `503` when full (flags auto-expire after 90 days of inactivity).
- **Flag TTL** — any flag not updated/toggled in 90 days is automatically deleted by MongoDB.
- This is a shared public instance. Please don't abuse it.

---

## Self-Hosting

```bash
git clone https://github.com/aarushbhutra/strobe.git
cd strobe
cp .env.example .env
# Edit .env with your MongoDB URI
pip install -r requirements.txt
fastapi dev main.py
```

### With Docker

```bash
docker build -t strobe .
docker run -p 8000:8000 --env-file .env strobe
```

### Deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template)

1. Fork this repo
2. Create a new Railway project
3. Add the MongoDB plugin
4. Deploy — Railway injects `MONGO_URL` automatically

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` / `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB` | `strobe` | Database name |
| `MAX_FLAGS` | `10000` | Global flag cap |
| `FLAG_TTL_DAYS` | `90` | Days before unused flags auto-expire |
| `RATE_LIMIT_ENABLED` | `true` | Set `false` to disable rate limiting |
| `API_KEY_ENABLED` | `false` | Set `true` to require `X-Api-Key` header |
| `API_KEY` | — | Secret key (only used when `API_KEY_ENABLED=true`) |

### Optional API Key Auth

By default the API is fully open. To require auth:

```env
API_KEY_ENABLED=true
API_KEY=your-secret-key
```

Then pass the key in every request:

```bash
curl https://your-instance.railway.app/flags \
  -H "X-Api-Key: your-secret-key"
```

---

## Demo

See `example/index.html` — a fake SaaS landing page (CloudSync) that uses Strobe flags to control its own UI in real time:

- **`promo-banner`** — shows/hides a promotional strip
- **`beta-nav`** — adds a BETA tag to the nav
- **`hero-style`** — 50/50 A/B test: light vs dark hero
- **`cta-variant`** — 3-way A/B test on the CTA button copy
- **`new-pricing`** — rolls out a new pricing section

Hit "New User" in the debug panel to regenerate your user ID and see different variant assignments.

---

## Tech Stack

- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [Motor](https://motor.readthedocs.io/) — Async MongoDB driver
- [MongoDB Atlas / Railway](https://railway.app) — Database
- [slowapi](https://github.com/laurentS/slowapi) — Rate limiting
- [Pydantic v2](https://docs.pydantic.dev/) — Validation

---

## License

MIT
