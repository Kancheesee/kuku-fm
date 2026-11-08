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

## 8. Implementation & Verification Matrix

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
| Multi-episode cross-cutting / stitching | Out of Scope (Milestone 4) | N/A | N/A |

---

## 9. Remaining Limitations

1. **Intra-Episode Continuous Cuts Only**: Promo candidates remain continuous event intervals within a single episode. Multi-scene montages and cross-episode stitched cuts are deferred to future milestones.
2. **Sequential Session Queue**: Batch processing schedules episodes sequentially per browser session; distributed parallel worker execution across multiple worker nodes is not yet implemented.
3. **Quota Window Reset**: When Gemini API quota is exhausted (HTTP 429), the system cleanly pauses; resuming requires user action after the quota window resets.

