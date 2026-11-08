# Kuku Promo Studio

An editorial workstation engineered to ingest timestamped microdrama screenplays, validate timeline integrity across overlapping audio/visual events, and discover evidence-grounded promo candidates (20–60s continuous clips) for social platforms (TikTok, Instagram Reels, YouTube Shorts).

---

## Milestone Status

- **Milestone 1 (Complete):** Local screenplay ingestion, deterministic parser (integer milliseconds, UTF-8/BOM/CRLF), timeline validation, database scaffolding (SQLAlchemy 2 / Alembic), and editorial script inspector interface.
- **Milestone 2 (Complete):** Real Gemini-powered promo candidate discovery for single episodes, provider abstraction layer, mechanical cut validation, editorial rubric evaluation, deduplication, ranked candidates interface, and CSV/JSON export.
- **Milestone 3 (Complete):** Resumable batch processing & Neon PostgreSQL persistence, dual connection configuration (unpooled for migrations, pooled for application), browser-session isolation, show-wide ranking, batch control (analyze all, pause, resume, retry), and UI state synchronization.

---

## Key Milestone 3 Persistence & Batch Capabilities

1. **Neon PostgreSQL Cloud Persistence:**
   - Multi-model schema via SQLAlchemy 2 and Alembic: `runs`, `episode_records`, `promo_candidates`.
   - Dual connection separation:
     - `DIRECT_URL` (direct unpooled) for DDL migrations (`alembic upgrade head`).
     - `DATABASE_URL` (connection pooler) with `NullPool` for responsive FastAPI queries.
   - Preserves complete parsed screenplay episodes, promo candidates, raw AI generation & assessment responses, token usage, and editorial diagnostics.

2. **HttpOnly Cookie Session Security & Origin Validation:**
   - Replaced localStorage identifiers with a server-issued cryptographically random 256-bit secret stored in an `HttpOnly` cookie (`kuku_session`, `SameSite=lax`, `Secure` in production).
   - Only the SHA-256 digest (`session_hash`) is stored in Neon PostgreSQL.
   - Origin and referer validation on all state-changing endpoints (`POST`, `PUT`, `DELETE`, `PATCH`) to prevent CSRF attacks.
   - Enforces strict session ownership across all run creation, listing, detail, analysis, pause, resume, retry, ranking, and export endpoints.

3. **Atomic Per-Episode Claims & Attempt Ownership:**
   - Dedicated short transaction uses `with_for_update()` to claim episodes with bounded 120s leases (`lease_token`, `attempt_number`).
   - Prevents concurrent duplicate analysis (`LeaseConflictError` / HTTP 409) and recovers abandoned `analyzing` states upon lease expiration.
   - AI generation and assessment calls execute completely **outside** database transactions.
   - Stale attempt verification on save rejects slow attempts if the lease expired or was claimed by another attempt (`StaleAttemptError`), preventing stale overwrites.

4. **React-Driven Batch Scheduling & Quota Pause:**
   - **Save Run:** Instantly persists ingested screenplay packs into a new database run.
   - **Client-Side Queue:** React orchestrates batch analysis by issuing separate, sequential per-episode requests (`POST /api/runs/{id}/episodes/{ep_id}/analyze`), avoiding monolithic server loops.
   - **Quota Exhaustion Pause:** On HTTP 429 quota exhaustion, React immediately halts the batch queue and displays an actionable alert banner.
   - **Pause & Resume:** Pauses execution at episode boundaries. Resuming queries run status and processes only `pending` episodes (skipping completed and failed).
   - **Explicit Retries:** Retrying failed episodes is an explicit user action.

5. **Provisional Show-Wide Ranking & Deterministic Tie-Breaker:**
   - Unassessed candidates (`overall_score is None`) are excluded from scored rankings (`show_rank = None`).
   - Scored candidates are ranked by a deterministic 5-key tie-breaker:
     `overall_score (DESC) -> duration_ms (DESC) -> episode_number (ASC) -> start_ms (ASC) -> id (ASC)`.
   - Incomplete run rankings are labeled `Provisional` with completed/total episode coverage metrics.
   - Show-wide CSV Shortlist and JSON Audit bundle exports.

---

## Key Milestone 2 Capabilities

1. **Pluggable AI Provider Interface (`app/services/ai/base.py`):**
   - Clean, provider-agnostic protocol (`AIProvider`) allowing Gemini to be replaced with other providers (Anthropic, OpenAI, local models) without changing downstream business logic.
   - Built on Google's official Python SDK (`google-genai`).
   - Uses structured JSON output with Pydantic response schema constraints.
   - Bounded timeouts (35s) and automatic exponential backoff retries for transient 429/503 errors.
   - Configurable model via `GEMINI_MODEL` (defaults to `gemini-3.5-flash-lite` for high availability and low latency).

2. **Deterministic Mechanical Cut Validation (`app/services/ai/validator.py`):**
   - Precise interval resolution: `start_ms` is the start event's start, `end_ms` is the end event's end, containing all overlapping screenplay events.
   - **Duration guard:** Enforces 20,000 ms to 60,000 ms limits.
   - **Dialogue cut protection:** Strictly rejects proposals that cut through active dialogue lines (prevents cutting actors off mid-speech).
   - **Hook verification:** Verifies that declared opening hook events intersect the opening 3-second window `[start_ms, start_ms + 3000ms]`.
   - **Cliffhanger verification:** Verifies that ending events occur near the cut boundary (within 6.0 seconds of the cut).
   - Rejections are tracked with machine-readable error codes (`DURATION_TOO_SHORT`, `CUTS_DIALOGUE_START`, `HOOK_OUTSIDE_OPENING_3S`, etc.) and preserved for audit.

3. **Editorial Rubric & Deduplication (`app/services/ai/ranker.py`):**
   - Anchored 1–5 ordinal scoring:
     - **Opening Hook Strength (30%)**
     - **Standalone Clarity (25%)**
     - **Escalation & Stakes (20%)**
     - **Unresolved Cut Timing (25%)**
   - Weighted overall score (1.0 to 5.0).
   - Temporal IoU deduplication: suppresses overlapping candidates (IoU &gt; 60%) to prevent near-duplicate proposals while retaining them in raw audit logs.

4. **Interactive Results Interface (`frontend/`):**
   - One-click **"Find Promos"** button for any selected episode.
   - Progress and error reporting (quota limits, missing credentials).
   - View tabs: **Ranked Shortlist**, **Rejected Proposals**, and **Suppressed Duplicates**.
   - Interactive timeline highlighting: selecting a promo highlights its complete interval in the screenplay, with distinct visual badges on opening 3s hook events and cliffhanger cut events.
   - Deep inspector drawer showing verbatim text, rubric scores, reasons, and mechanical checks.
   - **CSV Export:** Clean shortlist export for editorial teams.
   - **JSON Export:** Complete raw model audit bundle for transparency.

---

## Local Setup & Startup Commands

### 1. Environment & Database Configuration

Ensure your `.env` contains your Gemini API key and Neon PostgreSQL connection strings:

```bash
# .env
GEMINI_API_KEY=your_actual_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite

# Neon PostgreSQL connection strings
# Pooled connection endpoint for runtime application queries:
DATABASE_URL=postgresql+psycopg://<user>:<password>@<pooler-host>.neon.tech/neondb?sslmode=require
# Direct unpooled connection endpoint for Alembic migrations:
DIRECT_URL=postgresql+psycopg://<user>:<password>@<direct-host>.neon.tech/neondb?sslmode=require
```

*(Never commit or log your `.env` file).*

### 2. Apply Database Migrations

Apply pending Alembic migrations to your Neon database using `DIRECT_URL`:

```bash
source venv/bin/activate
alembic upgrade head
```

### 3. Backend Startup & Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run backend test suite (38 unit & persistence tests, 0 quota spent)
PYTHONPATH=backend pytest backend/tests

# Start FastAPI backend
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### 4. Frontend Startup & Tests

```bash
cd frontend

# Run frontend test suite (Vitest component & regression tests)
npm test -- --run

# Build check
npm run build

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Testing Saved Runs & Resume Locally

1. **Ingest a Script Pack:**
   - In the web app (`http://localhost:5173`), drop a script file or zip archive (e.g. `private_inputs/...zip`).
   - Click **"Inspect Scripts"** to view parsed episodes and timeline events.

2. **Save Run to Neon Database:**
   - Click the **"Save Run"** button in the top navigation bar.
   - The screenplay pack is stored in Neon PostgreSQL with status `created`, and each episode is created with status `pending`.

3. **Batch Analysis & Pause:**
   - Click **"Analyze All"** in the top navigation bar.
   - React drives the batch queue by issuing separate per-episode requests sequentially.
   - Click **"Pause"** during batch execution. The in-flight episode completes cleanly, remaining episodes remain `pending`, and the run transitions to `paused`.

4. **Resume Batch Analysis & Quota Handling:**
   - Click **"Resume"** to restart the batch run. Processing picks up with the first `pending` episode, skipping all previously completed episodes.
   - If Gemini API quota is exhausted (HTTP 429), batch execution halts automatically and displays an actionable banner. Clicking Resume when quota resets continues the run.

5. **Browse Saved Runs:**
   - Click **"Saved Runs"** in the top header.
   - The modal lists all saved runs scoped to your `HttpOnly` session with completion status, episode counts, and timestamp.
   - Selecting any saved run instantly restores its full state and completed promo candidates.

6. **View Show-Wide Rankings & Export:**
   - Click the **"Show Top Promos"** tab to view candidates ranked across all completed episodes in the run.
   - Incomplete runs clearly display a **"Provisional"** badge with completed episode coverage.
   - Click **"CSV Shortlist"** or **"Raw Audit (JSON)"** to export show-wide candidate shortlists.

## Vercel Deployment Guide

### 1. Vercel Project Import Settings

When importing this repository into Vercel:

| Setting | Value | Notes |
|---|---|---|
| **Root Directory** | `./` (repository root) | Leave at root so both `frontend` and `api/` are included |
| **Framework Preset** | **Other** (or auto-detected Vite) | Configuration is managed by `vercel.json` |
| **Build Command** | `npm run build` | Runs `cd frontend && npm install && npm run build` |
| **Output Directory** | `frontend/dist` | Serves compiled React SPA assets |
| **Install Command** | `npm install` | Installs root orchestrator scripts |
| **Python Function** | Auto-detected at `api/index.py` | Runs via Vercel Serverless Python runtime |

### 2. Required Environment Variables

Configure these variables in your Vercel Project Settings (**Settings $\to$ Environment Variables**):

| Variable Name | Required Environment | Purpose |
|---|---|---|
| `DATABASE_URL` | Production & Preview | Neon PostgreSQL **connection-pooled** URL (`postgresql+psycopg://...-pooler...neon.tech/neondb?sslmode=require`) used by FastAPI runtime |
| `DIRECT_URL` | Local / CI migrations | Neon PostgreSQL **unpooled direct** URL used for Alembic DDL schema migrations (`alembic upgrade head`) |
| `GEMINI_API_KEY` | Production & Preview | Google Gemini API key for promo generation & batched assessment |
| `GEMINI_MODEL` | Production & Preview | Selected Gemini model identifier (e.g. `gemini-3.5-flash-lite`) |
| `ENVIRONMENT` | Production | Set to `production` (enforces `Secure` flag on `HttpOnly` session cookies) |
| `ALLOWED_ORIGINS` | Optional / Production | Comma-separated list of custom domains (e.g. `https://my-promo-studio.com`). Exact Vercel deployment URLs (`VERCEL_URL`, `VERCEL_PROJECT_PRODUCTION_URL`, `VERCEL_BRANCH_URL`) are derived automatically without wildcards. |

*(Never commit or expose secrets in version control).*

### 3. Database Migration Step

> [!IMPORTANT]
> Migrations are decoupled from application startup to protect serverless performance and prevent concurrent migration locks.

Run pending migrations explicitly against your Neon database before deploying:

```bash
# Run from repository root with DIRECT_URL configured in your environment
source venv/bin/activate
cd backend
alembic upgrade head
```

### 4. Deployment Limitations & Platform Guardrails

1. **4.5 MB Serverless Payload Limit**: Vercel serverless functions reject request or response bodies exceeding 4.5 MB with HTTP 413. The application enforces a 4.4 MB safeguard on `/api/ingest/preview` and `/api/runs/{id}/export/json`, along with an instant client-side check in `handleFilesSelected`. Measured sizes: 50-episode `.zip` upload is 220.8 KB, full preview response is 2.36 MB, saved run reload is 77 KB, and full JSON audit export is 258 KB.
2. **120s Function Execution Budget & 90s Pipeline Deadline**: Serverless functions are configured with `maxDuration: 120`. GenAI SDK retries are bounded to `attempts=1`. Worst-case generation-plus-assessment execution is capped by an enforced 90s pipeline deadline with a 30s safety margin before Call 2. Episode leases are set to 180s (3 minutes), guaranteeing that active attempts never expire while running.
3. **Assessment Quota Persistence & Resumed Retry**: If Gemini API quota is exhausted during assessment (Call 2), valid generated candidates are safely persisted to Neon DB before returning HTTP 429 to pause the batch queue. On explicit retry, the engine resumes assessment directly on the preserved candidates, saving API calls, tokens, and latency.
4. **Exact Project Origin Validation (No Wildcards)**: All `*.vercel.app` wildcard allowances have been eliminated. State-changing requests are validated strictly against exact derived Vercel project deployment origins, configured domains, and same-origin calls.
5. **Database Connection Pooling**: Ephemeral serverless lambdas must connect via `DATABASE_URL` (Neon Pooler) with `NullPool` to avoid exhausting connection limits.
6. **Intra-Episode Continuous Clips**: Promo candidates are continuous intervals within single episodes. Cross-episode montages are deferred to future milestones.

### 5. Deployed Smoke-Test Sequence

Verify the live deployment on Vercel using this 6-step test sequence:

1. **Ingest & Inspect**: Navigate to your deployed Vercel URL (`https://your-app.vercel.app`). Upload a script pack (`.txt` or `.zip`). Verify parsed episode cards appear in the sidebar.
2. **Save Run**: Click **"Save Run"**. Verify a Run ID badge appears in the header and all episodes are marked `pending`.
3. **Per-Episode Analysis**: Click **"Find Promos"** on Episode 1. Verify candidate cards appear with duration (20–60s), hook badges, cliffhanger cues, and editorial rubrics.
4. **Refresh & Resume**: Refresh the browser page (`F5`). Click **"Saved Runs"** in the header. Select your run and click **"Resume Run"**. Verify the run and all previously analyzed candidates reload instantly from Neon DB.
5. **Session Isolation**: Open an Incognito/Private window. Visit `https://your-app.vercel.app` and click **"Saved Runs"**. Verify no saved runs from your previous browser session are visible (cross-session isolation).
6. **Export**: In your original window, click **"Show Top Promos"**, then click **"CSV Shortlist"** and **"Raw Audit (JSON)"**. Verify both files download and contain complete candidate data.

---

## Test Suite Coverage

- **51 Backend Pytest Tests (`PYTHONPATH=backend:. pytest backend/tests`)**:
  - Timestamp conversions & fractional math.
  - Screenplay format parsing (UTF-8, BOM, CRLF, multiline text, speaker/subtext parsing).
  - Safe archive decompression, path traversal security, and macOS metadata filtering.
  - Boundary validation: reversed times, out-of-scene bounds, unknown IDs.
  - Mid-sentence dialogue cut detection.
  - Hook window verification (first 3s) & cliffhanger cut verification.
  - Temporal IoU deduplication and candidate ranking.
  - Missing credentials and quota error handling.
  - Dual-call AI pipeline with batched rubric assessment.
  - Session security: HttpOnly cookie secret, SHA-256 server hash, origin validation for state-changing requests, and strict ownership isolation.
  - Atomic per-episode claims, 180s bounded lease expiry, duplicate claim rejection, and stale-attempt save rejection.
  - Quota pause error handling, unassessed candidate filtering, deterministic 5-key tie-breaker, and provisional ranking metadata.
  - Vercel readiness: entrypoint export, exact project preview origin allowance, untrusted origin rejection, 4.4MB payload guards, quota candidate persistence, resumed assessment retry, 90s pipeline deadline safety margin, and SPA static asset rewrites.
- **Live Neon PostgreSQL Integration Suite (`python backend/tests/verify_neon_integration.py`)**:
  - Verified live against Neon cloud database: run creation with session hash, cross-session isolation, atomic claim/lease issuance, duplicate claim conflict rejection, stale attempt rejection, valid attempt persistence, provisional coverage calculation, and automated cleanup.
- **2 Frontend Tests (`vitest run`)**:
  - In-flight promo response isolation across episode switches.
  - Upload replacement invalidation during active analysis.
