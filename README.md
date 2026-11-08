# Kuku Promo Studio

An editorial workstation engineered to ingest timestamped microdrama screenplays, validate timeline integrity across overlapping audio/visual events, and prepare evidence-grounded promo candidates (20–60s clips) for social platforms (TikTok, Instagram Reels, YouTube Shorts).

---

## Milestone 1: Ingestion, Timeline Verification & Editorial Inspection

This milestone implements the complete local ingestion pipeline, deterministic screenplay parsing engine, persistence scaffolding, and an editorial workspace interface.

> **Scope Note:** In Milestone 1, script ingestion and screenplay inspection operate completely without requiring a live PostgreSQL database connection or external AI API keys. AI candidate generation is intentionally disconnected until the next milestone.

---

## Key Features

1. **Deterministic Screenplay Parser:**
   - Full support for standard screenplays, UTF-8, and UTF-8 with BOM.
   - Preserves 1-indexed source line references and verbatim screenplay text.
   - Accurately parses event categories: **Camera**, **Action**, **Dialogue** (with character names and subtext/delivery notes), and **Sound FX**.
   - Handles multiline dialogue and descriptions with whitespace normalization.
   - Internal representation uses integer milliseconds (`start_ms`, `end_ms`, `duration_ms`), avoiding floating-point rounding inaccuracies.
   - Stable deterministic episode and event IDs (`SHA-256` content hashing + parser version).
   - Episode duration is calculated strictly from timeline bounds, never by summing concurrent events.

2. **Safe Archive & Ingestion Engine:**
   - Handles single `.txt` scripts, multi-file uploads, and nested `.zip` archives.
   - Protection against path traversal attacks (`../`), zip bombs, and corrupt/encrypted archives.
   - Automatically filters out macOS metadata (`__MACOSX`, `._*`) and non-script system files.
   - Identifies content duplicates and episode number collisions across batch files.

3. **Editorial Inspection Interface:**
   - Designed with an editorial workspace aesthetic: warm off-white background (`#fbfaf8`), charcoal text (`#1f2421`), and burnt-orange accent (`#c2410c`).
   - Drag-and-drop zone with full keyboard accessibility.
   - Aggregated metrics bar: episode count, total runtime, timed events count, and issue diagnostics.
   - Interactive screenplay timeline with scene boundaries, category filter pills, in-script search, and event jumping.
   - Dedicated event inspector drawer detailing exact source lines, timestamps, delivery notes, and validation diagnostics.
   - Future "Find Promos" action explicitly disabled with clear milestone messaging.

4. **Database & Persistence Scaffolding:**
   - SQLAlchemy 2.0 declarative models and initial Alembic migration (`001_initial_schema.py`) for `runs`, `episodes`, `promos`, and `model_calls`.
   - Optimized for Neon serverless PostgreSQL (pooled connection for FastAPI, unpooled direct connection for migrations, JSONB columns, request-scoped sessions).

---

## Repository Structure

```text
Kuku-kanchi/
├── backend/
│   ├── alembic/              # Database migration environment and version scripts
│   ├── alembic.ini           # Alembic configuration
│   ├── app/
│   │   ├── api/              # FastAPI endpoints (/api/health, /api/ingest/preview)
│   │   ├── db/               # SQLAlchemy models & serverless session management
│   │   ├── schemas/          # Pydantic v2 data models & validation contracts
│   │   ├── services/         # Parsing, timestamp logic, archive extraction & ingestion
│   │   └── main.py           # FastAPI application entry point & CORS configuration
│   ├── tests/                # Pytest test suite (18 unit tests)
│   ├── cli.py                # Standalone CLI for batch parsing and report generation
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/       # Workspace UI components (Header, Timeline, Drawer, etc.)
│   │   ├── lib/              # API client and timestamp utilities
│   │   ├── types/            # TypeScript contracts matching backend Pydantic models
│   │   ├── App.tsx           # Main workspace application
│   │   └── main.tsx          # React DOM entry point
│   ├── package.json          # Frontend dependencies (React 18, Vite, Tailwind CSS, Lucide)
│   ├── tailwind.config.js    # Custom editorial theme palette
│   └── vite.config.ts        # Vite config with API proxy
├── private_inputs/           # Confidential input pack (strictly gitignored)
├── private_outputs/          # Private validation dumps (strictly gitignored)
├── .env.example              # Sample environment variables
├── .gitignore                # Git ignore rules protecting proprietary data
└── README.md
```

---

## Prerequisites

- **Python:** 3.11+ (Python 3.13 tested)
- **Node.js:** v18+ (Node v23 tested) & `npm`

---

## Local Setup & Startup

### 1. Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Start the FastAPI server
uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`. Swagger documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

In a new terminal window:

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Inspecting Scripts Without Neon or AI APIs

The `/api/ingest/preview` endpoint and the UI inspector work entirely in-memory:
1. Open `http://localhost:5173`.
2. Drag and drop any `.txt` screenplay file or a `.zip` archive (such as the 50-episode pack).
3. Click **"Inspect scripts"**.
4. The application previews all episodes, scenes, timed events, speaker metadata, and timeline validation issues without writing to a database or invoking AI models.

---

## Running Tests

Run the full pytest suite:

```bash
source venv/bin/activate
PYTHONPATH=backend pytest backend/tests
```

### Test Coverage Highlights:
- **Timestamp parsing:** fractional seconds, minute boundaries, and hour limits.
- **Encoding & formatting:** UTF-8 BOM, CRLF vs LF line endings, multiline dialogue.
- **Screenplay rules:** character delivery parsing, concurrent camera/action overlap legitimacy.
- **Validation guards:** reversed timestamps, out-of-scene bounds, unknown technical labels.
- **Archive safety:** nested directories, macOS metadata (`__MACOSX`, `._*`) filtering, directory traversal protection (`../`), decompression limits.
- **Batch integrity:** duplicate content hashing and duplicate episode number collision warnings.

---

## Full-Pack Validation via CLI

A standalone CLI command is included to validate screenplay batches directly from the terminal and export structured validation reports:

```bash
# Validate a zip archive or directory of scripts and generate a JSON report
source venv/bin/activate
python backend/cli.py "private_inputs/I Married a Broken Soldier. He was a Duke.zip" --report private_outputs/validation_report.json
```

### Full-Pack (50 Episodes) Validation Results:
- **Episodes Parsed:** 50 / 50 (100% success rate).
- **Total Scenes:** 100 scenes.
- **Total Timed Events:** 3,727 events (1,754 camera shots, 372 action descriptions, 1,487 dialogue lines, 114 sound effects).
- **Total Source Runtime:** 102.71 minutes (6,162,620 milliseconds).
- **Ignored Archive Artifacts:** 52 members (51 `__MACOSX` metadata entries + 1 folder entry).
- **Timeline Diagnostics Detected:** Exactly 1 genuine timeline discrepancy found in the original source data:
  - `episode-022`: Event end (`00:42.80`) in Scene 01 exceeds Scene 01's declared end time (`00:42.50`) by 300ms. The parser surfaced this diagnostic without dropping or corrupting the event.

---

## Database Migrations (When Database Is Configured)

When connecting to Neon PostgreSQL:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configure `DATABASE_URL` (pooled connection) and `DIRECT_URL` (direct migration connection).
3. Run Alembic migrations:
   ```bash
   cd backend
   alembic upgrade head
   ```

---

## Confidential Data Handling

To protect proprietary screenplay intellectual property:
- Both `private_inputs/` and `private_outputs/` are gitignored.
- `*.zip`, `*.pdf`, and `*.dump` files are gitignored by default.
- Terminal logs and API error responses never output verbatim script dumps.
- All committed tests use synthetic, non-confidential screenplay fixtures.

---

## Known Limitations & Next Milestone

- **AI Candidate Generation:** Disconnected for Milestone 1. The workspace displays structured screenplay evidence and disabled UI actions for promo generation.
- **Persistence:** Ingestion preview runs in-memory. Database save actions will be wired during Milestone 2 when promo candidate generation and run tracking are persisted.
- **Next Milestone Focus:**
  - AI Promo Candidate Generation adapter (swappable LLM provider interface for Gemini / OpenAI / Anthropic).
  - Algorithmic scoring of 3-second opening hooks, cliffhangers, and narrative coherence.
  - Multi-segment editorial assembly across 20–60 second target promo durations.

