# Kuku Promo Studio

An editorial workstation engineered to ingest timestamped microdrama screenplays, validate timeline integrity across overlapping audio/visual events, and discover evidence-grounded promo candidates (20–60s continuous clips) for social platforms (TikTok, Instagram Reels, YouTube Shorts).

---

## Milestone Status

- **Milestone 1 (Complete):** Local screenplay ingestion, deterministic parser (integer milliseconds, UTF-8/BOM/CRLF), timeline validation, database scaffolding (SQLAlchemy 2 / Alembic), and editorial script inspector interface.
- **Milestone 2 (Complete):** Real Gemini-powered promo candidate discovery for single episodes, provider abstraction layer, mechanical cut validation, editorial rubric evaluation, deduplication, ranked candidates interface, and CSV/JSON export.

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

### 1. Environment Configuration

Ensure your `.env` contains your Gemini API key:

```bash
# .env
GEMINI_API_KEY=your_actual_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

*(Never commit or log your `.env` file).*

### 2. Backend Startup

```bash
# Activate virtual environment
source venv/bin/activate

# Run test suite (27 unit tests, 0 quota spent)
PYTHONPATH=backend pytest backend/tests

# Start FastAPI backend
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### 3. Frontend Startup

```bash
cd frontend

# Build check
npm run build

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## CLI Repeatable Evaluation

Run promo analysis directly from the command line on any episode:

```bash
# Analyze Episode 1 and save raw audit report
source venv/bin/activate
python backend/cli.py analyze "private_inputs/I Married a Broken Soldier. He was a Duke.zip" --episode 1 --out private_outputs/episode_001_promos.json

# Analyze Episode 25
python backend/cli.py analyze "private_inputs/I Married a Broken Soldier. He was a Duke.zip" --episode 25 --out private_outputs/episode_025_promos.json

# Analyze Episode 50
python backend/cli.py analyze "private_inputs/I Married a Broken Soldier. He was a Duke.zip" --episode 50 --out private_outputs/episode_050_promos.json
```

---

## Live Verification Results (Episodes 1, 25, 50)

| Episode | Duration | Model | Latency | Proposals | Accepted | Rejected | Highlights |
|---|---|---|---|---|---|---|---|
| **Episode 1** | 138.0s (95 events) | `gemini-3.5-flash-lite` | 5,288 ms | 3 | **3** | 0 | 3 distinct 43–47s arcs covering the initial altar betrayal, family abandonment, and Juliana's transformation into vengeance. |
| **Episode 25** | 168.0s (95 events) | `gemini-3.5-flash-lite` | 3,341 ms | 2 | **2** | 0 | 2 distinct clips: Juliana revealing Lady Catherine's whipping (37.2s) and the discovery of the arsenic poisoning plot (41.8s). |
| **Episode 50** | 80.0s (40 events) | `gemini-3.5-flash-lite` | 3,308 ms | 2 | **1** | **1** | Top candidate accepted: Catherine and Father Thomas's extortion confrontation (40.7s, score 4.5/5.0). One proposal rejected by code validator. |

### Observed Model Mistake & Validator Catch
In Episode 50, the model proposed a clip titled *"Caught in the Act"* covering the final twist where Agnes discovers the illicit affair. However, the scene interval for this shock discovery was only **9.50 seconds**, which violates the mandatory 20.0s microdrama platform minimum.
- **Validator Action:** The validator rejected this proposal with code `DURATION_TOO_SHORT`, preventing an invalid cut from reaching editors while preserving the full diagnostic in the audit JSON.

---

## Test Suite Coverage

All 27 automated unit tests run against synthetic mocks with **0 API quota spent**:
- Timestamp conversions & fractional math.
- Screenplay format parsing (UTF-8, BOM, CRLF, multiline text, speaker/subtext parsing).
- Safe archive decompression, path traversal security, and macOS metadata filtering.
- Boundary validation: reversed times, out-of-scene bounds, unknown IDs.
- Mid-sentence dialogue cut detection.
- Hook window verification (first 3s) & cliffhanger cut verification.
- Temporal IoU deduplication and candidate ranking.
- Missing credentials and quota error handling.
- Fast, typed FastAPI endpoint verification.
