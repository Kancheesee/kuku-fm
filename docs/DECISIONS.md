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

## 7. Implementation & Verification Matrix

| Feature / Subsystem | Implementation Status | Automated Mock Verification | Live API Verification |
|---|---|---|---|
| Screenplay ingestion & timestamping | Complete | Verified (pytest) | Verified (50-ep pack) |
| Mechanical cut validation (dialogue / duration / 3s hook) | Complete | Verified (pytest) | Verified (synthetic + real) |
| Prompt versioning & window annotation | Complete | Verified (pytest) | Live Ep 1 & Ep 2 (in progress) |
| Batched model assessment & code ranking | Complete | Verified (pytest) | Live Ep 1 & Ep 2 (in progress) |
| Assessment failure fallback | Complete | Verified (pytest) | Not triggered live |
| Client race condition & upload invalidation | Complete | Verified (Vitest) | N/A (Frontend logic) |
| Multi-episode cross-cutting / stitching | Out of Scope (Milestone 3+) | N/A | N/A |

