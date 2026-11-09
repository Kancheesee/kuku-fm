# Architecture & Product Decisions

This document records the foundational architecture and editorial product decisions for **Kuku Promo Studio**. It clearly distinguishes **implemented behavior** (in codebase) from **verified behavior** (confirmed via automated tests or verified runs).

---

## 1. Product Boundaries & Scope

- **Core Goal**: Transform timestamped microdrama screenplays into ranked, continuous 20s–60s promotional video candidate cuts with transparent editorial rationale and source grounding.
- **Continuous Cuts Only**: Candidates are strictly contiguous event sequences within a single episode. Multi-scene stitching, cross-episode montages, and whole-pack orchestration are deferred to later milestones.
- **Strict Privacy**: Proprietary script text, dialogue excerpts, and confidential pack assets are strictly excluded from version control, error logs, and frontend bundles.

---

## 2. Ingestion & Parser Architecture

- **Decision**: Zero external AI or database dependencies required for ingestion and screenplay inspection.
- **Timestamp Precision**: All scene, camera, action, and dialogue cues are parsed into exact integer millisecond boundaries (`start_ms`, `end_ms`).
- **Archive Ingestion**: Ingestion safely processes standalone `.txt` scripts and `.zip` archives with zip bomb defenses (50MB decompressed limit, 500 member count limit) while ignoring OS metadata (`__MACOSX`, `.DS_Store`).
- **Status**:
  - *Implemented*: Ingestion API, CLI, and Zip unpacker.
  - *Verified*: Automated tests against single scripts, archive extractions, and the private 50-episode pack.

---

## 3. Two-Call Promo Discovery Pipeline

- **Decision**: Separate proposal generation from editorial assessment to prevent self-evaluating bias and enable deterministic mechanical validation in between.
  1. **Call 1 — Proposal Generation**: The model proposes candidate start and end event IDs along with draft rationale, based on screenplay action and dialogue cues.
  2. **Deterministic Code Validation**: Code strictly validates:
     - Candidate duration strictly between 20.0s and 60.0s.
     - Cut boundaries do not slice through active, spoken dialogue lines (`CUTS_DIALOGUE_START`, `CUTS_DIALOGUE_END`).
     - Stated opening hook event intersects the first 3.0s (`HOOK_OUTSIDE_OPENING_3S`).
     - Event IDs are valid and ordered.
  3. **Call 2 — Batched Model Assessment**: At most **one** batched assessment call evaluates all mechanically valid candidates for the episode.
     - Candidates are presented with their complete resolved event interval, explicitly annotated with `[0.0s - 3.0s OPENING HOOK WINDOW]`, `[BODY]`, and `[FINAL 5.0s CLIFFHANGER CUT WINDOW]`.
     - Background continuity notes and loglines are strictly excluded to enforce genuine standalone viewer comprehension.
- **Status**:
  - *Implemented*: `orchestrator.py`, `gemini_provider.py`, `prompts.py`, `validator.py`.
  - *Verified*: Mocked provider unit tests verify prompt exclusion, window tagging, and mechanical cut filtering.

---

## 4. Scoring, Ranking & Failure Fallback

- **Decision**: No hardcoded story-specific heuristic rules (no character names, church doors, wedding tropes, or revenge assumptions in code).
- **Code-Weighted Overall Ranking**:
  The assessment model grades four orthogonal 1–5 criteria. Code computes the overall score:
  $$\text{Overall Score} = 0.30 \times \text{Opening} + 0.25 \times \text{Clarity} + 0.20 \times \text{Stakes} + 0.25 \times \text{Ending}$$
- **Suppression of Overlapping Cuts**:
  Temporal Intersection-over-Union (IoU) is computed between accepted candidates. If $\text{IoU} \ge 0.60$, the lower-ranked candidate is suppressed to `suppressed_candidates` for audit transparency.
- **Assessment Failure Resilience**:
  If Call 2 fails (timeout, rate limit, quota, refusal), mechanically valid candidates are **never discarded** and heuristic scores are **never fabricated**. The candidate is preserved with `assessment_status = "unavailable"`, `rubric = null`, and flagged for manual review.
- **Status**:
  - *Implemented*: `ranker.py`, `PromoCard.tsx`, `PromoDetailDrawer.tsx`, `export.ts`.
  - *Verified*: Unit tests confirm weighted score calculation, IoU deduplication, and graceful fallback when assessment errors occur.

---

## 5. Configuration Fingerprint & Cache Identity

- **Decision**: A source content hash alone does not identify an analysis run.
- **Canonical Cache Key**:
  $$\text{cache\_key} = \text{source\_hash} + \text{"\_\_"} + \text{parser\_version} + \text{"\_\_"} + \text{model} + \text{"\_\_p"} + \text{prompt\_version} + \text{"\_\_a"} + \text{assessment\_prompt\_version} + \text{"\_\_c"} + \text{max\_candidates}$$
  Any update to generation prompts, assessment prompts, parser logic, model identifier, or candidate limit produces a distinct key.
- **Status**:
  - *Implemented*: `orchestrator.py`.
  - *Verified*: Unit tests verify key differentiation across all parameters.

---

## 6. Frontend Concurrency & Identity Isolation

- **Decision**: Promo discovery results are stored in client state keyed strictly by episode `content_hash`.
- **In-Flight Episode Switching**: If a user initiates promo analysis on Episode 1 and navigates to Episode 2, completion of Episode 1 does not hijack the active view or overwrite Episode 2's display. Returning to Episode 1 renders its saved results.
- **Upload Replacement Epoch**: An `uploadEpochRef` invalidates all pending in-flight promises if the user resets or uploads a new script pack during an active request.
- **Card Hierarchy**: Promo card surfaces prioritize `Episode {num} • {filename}`. Technical content hashes are reserved for the detail drawer, diagnostic badges, and CSV/JSON exports.
- **Status**:
  - *Implemented*: `App.tsx`, `PromoCard.tsx`.
  - *Verified*: Automated browser component regression tests (`race_condition.test.tsx`) pass in Vitest.

---

## 7. Persistence, Security & Resumable Batch Processing (Milestone 3)

- **Dual-Connection Neon PostgreSQL Architecture**:
  - `DIRECT_URL`: Direct unpooled endpoint (`ep-dawn-hill-bdql779c.c-8.us-east-2.aws.neon.tech`) used exclusively for Alembic schema migrations (`001_initial_schema`, `002_milestone3_features`, `003_session_and_claims`).
  - `DATABASE_URL`: Connection-pooled endpoint (`ep-dawn-hill-bdql779c-pooler.c-8.us-east-2.aws.neon.tech`) used by the FastAPI runtime with SQLAlchemy 2, `psycopg` (v3), and `NullPool` to eliminate connection leaks in serverless/pooled environments.
  - Automatic URL normalization ensures all URLs use `postgresql+psycopg://`.
- **HttpOnly Cookie Session Security & Origin Validation**:
  - Replaced legacy `localStorage`/`X-Session-ID` with server-issued cryptographically random 256-bit session secret in an `HttpOnly` cookie (`kuku_session`, `SameSite=lax`, `Secure` in production).
  - Only the SHA-256 digest (`session_hash`) is stored in the database.
  - Request origin validation enforces CSRF protection on all state-changing endpoints (`POST`, `PUT`, `DELETE`, `PATCH`).
  - Strict session ownership is enforced across every run endpoint (`GET /api/runs`, `GET /api/runs/{id}`, `/analyze`, `/ranking`, `/export/*`). Requests without matching session receive 404 to prevent resource enumeration.
  - **Handling of Existing Development Runs**: Development runs created prior to migration `003_session_and_claims` retain their legacy `browser_session_id` and are neither exposed nor reassigned; they remain deprecated in the database.
- **Atomic Per-Episode Claims, Bounded Leases & Attempt Ownership**:
  - **Atomic Claim (Transaction 1)**: `claim_episode_for_analysis` uses `with_for_update()` to inspect episode state. Rejects duplicate concurrent analysis (`LeaseConflictError` / HTTP 409). Automatically recovers abandoned `analyzing` states if `lease_expires_at` is in the past. Assigns unique `lease_token` (UUID hex), `lease_expires_at` (120s lease window), and increments `attempt_number`.
  - **AI Isolation**: Gemini generation and assessment calls run completely **outside** database transactions.
  - **Atomic Save (Transaction 2)**: `save_episode_analysis_result` verifies `lease_token` and `attempt_number`. Late or superseded attempts are rejected (`StaleAttemptError` / HTTP 409), preventing slow workers from overwriting newer results.
- **Client-Side Batch Scheduling (React-Driven)**:
  - Batch scheduling is coordinated in React, which issues separate, sequential per-episode requests (`POST /api/runs/{id}/episodes/{ep_id}/analyze`).
  - No monolithic server-side loops or untracked background tasks.
  - **Pause**: Halts the client loop immediately at episode boundary; run transitions to `paused`.
  - **Resume**: Re-queries run status and schedules only `pending` episodes (skips completed and failed).
  - **Quota Pause**: On HTTP 429 quota exhaustion, React immediately halts the batch queue, triggers run pause, and displays an actionable alert banner.
  - **Explicit Retries**: Failed episodes require explicit user retry actions (`/episodes/{id}/retry`), preventing infinite retry loops.
- **Show-Wide Candidate Ranking & Provisional Coverage**:
  - Unassessed candidates (`overall_score is None`) are strictly excluded from scored rankings (`show_rank = None`).
  - Scored candidates are ranked by a deterministic 5-key tie-breaker:
    $$\text{overall\_score (DESC)} \to \text{duration\_ms (DESC)} \to \text{episode\_number (ASC)} \to \text{start\_ms (ASC)} \to \text{id (ASC)}$$
  - Incomplete run rankings are labeled `Provisional` with completed/total episode coverage metrics.
- **Status**:
  - *Implemented*: `backend/app/db/`, `backend/app/api/runs.py`, `backend/app/core/session.py`, `backend/app/services/runs_service.py`, `frontend/src/App.tsx`, `frontend/src/components/ShowWideRankingView.tsx`.
  - *Verified*:
    - Alembic migration `003_session_and_claims` applied to live Neon DB.
    - Live Neon PostgreSQL integration test (`verify_neon_integration.py`): verified session isolation, atomic lease claim, duplicate claim rejection, stale attempt rejection, and provisional ranking against live Neon DB.
    - All 41 backend pytest tests pass.
    - All frontend Vitest tests pass.
    - Frontend production build (`npm run build`) compiles cleanly with 0 errors.

---

## 8. Vercel Production Deployment Architecture

- **Single-Origin Deployment Arrangement**:
  - The entire application is deployed to Vercel as a single project using root [`vercel.json`](file:///Users/yashrajsingh/Desktop/Kuku-kanchi/vercel.json) configuration:
    - Frontend build: `cd frontend && npm install && npm run build` outputting static assets to `frontend/dist`.
    - Backend API entrypoint: Serverless Python function at [`api/index.py`](file:///Users/yashrajsingh/Desktop/Kuku-kanchi/api/index.py) importing `app` from `backend/app/main.py`.
    - Rewrites: `/api/(.*)` routes to `/api/index.py`; `/((?!api|assets|favicon\.ico).*)` routes to `/index.html` for client-side React SPA routing. Static assets under `/assets/` and `/favicon.ico` are excluded from the SPA fallback to prevent JavaScript/CSS requests from swallowing HTML.
  - **HttpOnly Cookie Preservation**: Because frontend and backend are served under the exact same browser origin, `kuku_session` HttpOnly cookies are automatically sent and received on all `/api` calls without third-party cookie restrictions or cross-domain issues.
- **Worst-Case Duration, Pipeline Deadline Budget & Lease Duration**:
  - **SDK Retry Behavior**: Google GenAI SDK internal retries are explicitly restricted to `attempts=1` (`types.HttpRetryOptions(attempts=1)`) with `timeout=25000` ms, preventing undocumented multi-retry loops.
  - **Worst-Case Duration Calculation**:
    - Call 1 (Generation): Attempt 1 (25s) + backoff (2s) + Attempt 2 (25s) = 52.0s.
    - Call 2 (Assessment): Attempt 1 (25s) + backoff (2s) + Attempt 2 (25s) = 52.0s.
    - Database work (lease claim, result persistence, show-wide ranking): ~1.0s.
    - Unconstrained worst-case total: $52.0 + 52.0 + 1.0 = 105.0\text{ seconds}$.
  - **Overall Pipeline Deadline (90s)**:
    - `PIPELINE_DEADLINE_SECONDS = 90.0` with `ASSESSMENT_MIN_BUDGET_SECONDS = 30.0`.
    - If elapsed generation time exceeds 60s, Call 2 is skipped gracefully: mechanically valid candidates are preserved with `assessment_status = "unavailable"` and `assessment_error = "Assessment skipped: pipeline deadline threshold reached to guarantee completion within Vercel function timeout"`.
    - The serverless function always terminates cleanly within 90–95s, well before Vercel's `maxDuration: 120` limit.
  - **Episode Lease Duration (180s)**:
    - `lease_duration_seconds` is set to 180 seconds (3 minutes), giving a comfortable 90-second safety margin beyond the 90s pipeline deadline. Active worker attempts never expire while still executing.
- **Payload Size Measurements & Frontend Validation**:
  - **50-Episode Pack Upload (.zip)**: 220.8 KB (226,133 bytes).
  - **`IngestPreviewResponse` JSON**: 2.36 MB (2,475,139 bytes for 50 episodes with all scenes, timestamped events, and diagnostics). Strictly below Vercel's 4.5 MB platform limit (52.5% utilization).
  - **Saved-Run Reload (`RunDetailResponse`)**: 77.15 KB (78,999 bytes for 50 episodes and 50 show-wide candidates).
  - **Full Audit Export JSON**: 257.67 KB (263,858 bytes for 50 episodes and 150 candidates).
  - **Frontend Request Size Check**: Client-side check in `handleFilesSelected` instantly alerts users if selected files exceed 4.4 MB before initiating network transmission, while backend `MAX_UPLOAD_BYTES` enforces the server-side barrier.
- **Assessment Quota Exhaustion & Resumed Retry**:
  - When Call 2 encounters `AIQuotaExceededError`:
    1. Valid generated candidate proposals and raw generation response are packaged into a partial `PromoAnalysisResponse`.
    2. The candidates are persisted to the Neon database (`analysis_result_json`, `PromoCandidate` records with `overall_score = None`).
    3. The episode is marked `failed` with the quota error and the lease is released.
    4. `AIQuotaExceededError` is re-raised, returning HTTP 429 to the frontend.
    5. The React batch scheduler halts immediately and displays the paused banner.
  - **Retry Behavior**:
    - When the user explicitly clicks "Retry", `retry_episode` checks for existing valid generation output.
    - If candidates already exist, **it resumes assessment directly (Call 2)**, eliminating redundant generation calls, saving tokens, and minimizing latency.
    - If no generation output exists (e.g., Call 1 failed), full discovery (generation + assessment) is executed.
- **Exact Project Origin Validation (No Wildcards)**:
  - Any wildcard allowance for `*.vercel.app` is completely removed.
  - Trusted origins are derived strictly from:
    1. Local development origins (`http://localhost:5173`, `http://localhost:8000`, etc.).
    2. Explicitly configured domains in `ALLOWED_ORIGINS` / `CORS_ORIGINS`.
    3. Exact project deployment hosts from trusted Vercel environment variables: `VERCEL_URL`, `VERCEL_PROJECT_PRODUCTION_URL`, `VERCEL_BRANCH_URL`.
    4. Exact same-origin requests (`candidate_origin == request_origin`).
  - Untrusted third-party `*.vercel.app` domains are rejected with HTTP 403.
  - `Secure` cookies are enforced whenever `request.url.scheme == "https"` or `x-forwarded-proto == "https"`, ensuring HTTPS previews and production both receive secure cookies.
- **Decoupled Database Migrations**:
  - Migrations are never executed during application startup or within serverless execution lifecycles.
  - Migrations must be run explicitly prior to or during CI deployment via `alembic upgrade head` using `DIRECT_URL`.
- **Bundle Exclusion**:
  - [`.vercelignore`](file:///Users/yashrajsingh/Desktop/Kuku-kanchi/.vercelignore) strictly excludes private screenplays (`private_inputs/`, `private_outputs/`), secrets (`.env*`), virtual environments (`venv/`), test directories, and local caches.
- **Status**:
  - *Implemented*: `vercel.json`, `api/index.py`, `package.json`, `requirements.txt`, `.vercelignore`, `backend/app/core/session.py`, `backend/app/services/ai/orchestrator.py`, `backend/app/services/runs_service.py`, `frontend/src/App.tsx`.
  - *Verified*:
    - All 51 backend pytest tests pass (including Vercel entrypoint, preview origin, quota persistence, pipeline deadline, and payload size guard tests).
    - All frontend Vitest tests pass.
    - Frontend production build (`npm run build`) compiles cleanly in 1.55s with 0 errors.

---

## 9. Implementation & Verification Matrix

| Feature / Subsystem | Implementation Status | Automated Mock Verification | Live DB / Live API Verification |
|---|---|---|---|
| Screenplay ingestion & timestamping | Complete | Verified (pytest) | Verified (50-ep pack) |
| Mechanical cut validation (dialogue / duration / 3s hook) | Complete | Verified (pytest) | Verified (synthetic + real) |
| Prompt versioning & window annotation | Complete | Verified (pytest) | Verified (Ep 1 & Ep 2 cached runs) |
| Batched model assessment & code ranking | Complete | Verified (pytest) | Verified (Ep 1 & Ep 2 cached runs) |
| Assessment failure fallback | Complete | Verified (pytest) | Verified (graceful degradation) |
| Client race condition & upload invalidation | Complete | Verified (Vitest) | Verified (Vitest) |
| HttpOnly cookie session isolation & CSRF origin validation | Complete | Verified (pytest) | Verified on live Neon DB |
| Atomic per-episode claims, lease expiry & attempt ownership | Complete | Verified (pytest) | Verified on live Neon DB |
| Stale attempt rejection (no late overwrite) | Complete | Verified (pytest) | Verified on live Neon DB |
| React per-episode batch scheduling & quota exhaustion pause | Complete | Verified (Vitest + pytest) | Verified in React App |
| Provisional show-wide ranking with 5-key tie-breaker | Complete | Verified (pytest) | Verified on live Neon DB |
| Vercel exact deployment origin validation (no wildcards) | Complete | Verified (pytest 10/10) | Verified locally |
| Worst-case duration calculation & 90s pipeline deadline | Complete | Verified (pytest) | Verified locally |
| Quota candidate persistence & resumed retry assessment | Complete | Verified (pytest) | Verified on live DB |
| Static asset exclusion in SPA rewrites & /api/health reachability | Complete | Verified (pytest) | Verified locally |
| Serverless 4.5MB payload & 180s lease guards | Complete | Verified (pytest) | Verified locally |
| One-click multi-episode batch discovery & auto-open show ranking | Complete | Verified (Vitest 5/5) | Verified in React App |
| Multi-episode cross-cutting / stitching | Out of Scope (Milestone 4) | N/A | N/A |

---

## 10. Default Multi-Episode Reviewer Workflow (Problem 1 Alignment)

- **One-Click Primary Action**:
  - When a multi-episode pack (`total_episodes > 1`) is uploaded, **Analyze All Episodes ({N})** becomes the prominent, primary action button in the studio header.
  - Single-episode "Find Promos" remains accessible as a secondary action for targeted inspection.
  - "Save Run" is automatically orchestrated as step 1 of batch analysis, eliminating friction.
- **Safe Chained Persistence & Stale State Defense**:
  - If the upload is unsaved, clicking "Analyze All Episodes" calls `createSavedRun` first.
  - The returned run ID is passed explicitly to `runBatchScheduler(runId)`, eliminating closures over stale React state.
  - If run creation fails, the batch queue never starts, an error banner is displayed, and the uploaded scripts and timeline events remain fully intact.
- **Non-Intrusive Auto-Opening of Show Ranking**:
  - Upon batch completion, the UI automatically switches the view to `show-ranking` and selects the #1 ranked candidate for inspection in the detail drawer.
  - If the user deliberately navigated away to inspect an episode timeline during batch processing (`userNavigatedDuringBatchRef = true`), the UI respects the reviewer's active context and does not forcibly switch views.
- **Finished Runs Empty State & Provisional Indicator**:
  - Completed runs with 0 scored candidates render a clear empty state explaining that no promo candidates met the threshold.
  - Runs with pending episodes display the `Provisional` badge with completed/total episode coverage metrics.
- **Ranked Candidate Cards**:
  - Cards prominently show: global show rank (`#{rank}`), episode origin (`Episode {num} • {filename}`), timing coordinates (`{start} – {end}` and duration), opening hook summary, cliffhanger cut summary, editorial rationale (`candidate.rationale`), grounded unresolved question, and rubric scores.
- **Status**:
  - *Implemented*: `frontend/src/App.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/components/PromoCard.tsx`, `frontend/src/components/ShowWideRankingView.tsx`.
  - *Verified*:
    - Automated Vitest regression suite (`frontend/src/test/batch_entry.test.tsx` and `race_condition.test.tsx`) — all 5 tests pass.
    - Production build (`npm run build`) compiles cleanly in 1.51s with 0 TypeScript errors.

---

## 11. Remaining Limitations & Deployment Constraints

1. **Intra-Episode Continuous Cuts Only**: Promo candidates remain continuous event intervals within a single episode. Multi-scene montages and cross-episode stitched cuts are deferred to future milestones.
2. **Serverless Payload Hard Ceiling (4.5 MB)**: Uploads or raw JSON exports exceeding 4.5 MB will be rejected with HTTP 413. For script packs larger than 4.5 MB, client-side direct S3/Blob storage uploads would be required.
3. **Serverless Function Duration (120s)**: While single episodes finish in 5–15 seconds, worst-case network retries are capped at 120s.
4. **Neon Connection Pooling**: FastAPI runtime must use connection-pooled `DATABASE_URL` with `NullPool` to prevent pool exhaustion in ephemeral serverless lambdas. Alembic migrations must use `DIRECT_URL`.
5. **Quota Window Reset**: When Gemini API quota is exhausted (HTTP 429), batch execution halts automatically; resuming requires user action after quota reset.

