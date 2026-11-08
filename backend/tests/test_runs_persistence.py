import hashlib
from datetime import datetime, timedelta, timezone
import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.db import models
from app.main import app
from app.schemas.models import Episode
from app.schemas.promo import CandidateAssessmentItem, RawCandidateProposal
from app.services.ai.base import (
    AIProvider,
    AIQuotaExceededError,
    AssessmentResult,
    GenerationResult,
)
from app.services import runs_service
from app.services.runs_service import LeaseConflictError, StaleAttemptError

# Isolated in-memory SQLite engine for deterministic mocked unit tests
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def override_get_db():
    session = TestSessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class MockAIProvider(AIProvider):
    def __init__(self, score: float = 4.5):
        self.score = score

    def generate_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        return GenerationResult(
            raw_response_text='{"candidates": []}',
            parsed_candidates=[
                RawCandidateProposal(
                    editorial_title="Betrayal Cut",
                    start_event_id="e1",
                    end_event_id="e2",
                    hook_explanation="Visual hook",
                    hook_event_ids=["e1"],
                    cliffhanger_explanation="Cliffhanger",
                    cliffhanger_event_ids=["e2"],
                    unresolved_question="What next?",
                    rationale="High tension",
                    standalone_assessment="Clear",
                    editorial_risks=[],
                )
            ],
            model_identifier="mock-model",
            prompt_version="2.2.0",
            token_usage={"total_tokens": 100},
            latency_ms=150,
        )

    def assess_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        return AssessmentResult(
            raw_response_text='{"assessments": []}',
            assessments=[
                CandidateAssessmentItem(
                    candidate_index=1,
                    opening_strength=5,
                    opening_reason="Great hook",
                    standalone_clarity=4,
                    clarity_reason="Clear",
                    escalation_stakes=4,
                    stakes_reason="Stakes",
                    unresolved_ending=5,
                    ending_reason="Cut peak",
                    grounded_unresolved_question="What next?",
                )
            ],
            model_identifier="mock-model",
            prompt_version="assessment_v1.0.0",
            token_usage={"total_tokens": 120},
            latency_ms=200,
        )


class QuotaFailingProvider(AIProvider):
    def generate_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        raise AIQuotaExceededError("Resource exhausted: daily rate limit reached")

    def assess_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        raise AIQuotaExceededError("Resource exhausted: daily rate limit reached")


def make_synthetic_episodes():
    return [
        {
            "id": "ep_1",
            "episode_number": 1,
            "filename": "ep1.txt",
            "content_hash": "hash_ep1",
            "duration_ms": 30000,
            "logline": "Ep 1 logline",
            "scenes": [{"id": "s1", "scene_label": "SCENE 01", "heading": "INT. ROOM", "start_ms": 0, "end_ms": 30000, "line_start": 1, "line_end": 5}],
            "events": [
                {"id": "e1", "scene_id": "s1", "category": "action", "original_label": "**ACTION:**", "start_ms": 0, "end_ms": 4000, "text": "Action", "line_start": 2, "line_end": 2},
                {"id": "e2", "scene_id": "s1", "category": "dialogue", "speaker": "JULIANA", "original_label": "**JULIANA:**", "start_ms": 4000, "end_ms": 30000, "text": '"Goodbye."', "line_start": 3, "line_end": 4},
            ],
            "warnings": [],
            "parser_version": "1.0.0",
        },
        {
            "id": "ep_2",
            "episode_number": 2,
            "filename": "ep2.txt",
            "content_hash": "hash_ep2",
            "duration_ms": 32000,
            "logline": "Ep 2 logline",
            "scenes": [{"id": "s2", "scene_label": "SCENE 01", "heading": "INT. HALL", "start_ms": 0, "end_ms": 32000, "line_start": 1, "line_end": 5}],
            "events": [
                {"id": "e1", "scene_id": "s2", "category": "action", "original_label": "**ACTION:**", "start_ms": 0, "end_ms": 3000, "text": "Action 2", "line_start": 2, "line_end": 2},
                {"id": "e2", "scene_id": "s2", "category": "dialogue", "speaker": "GERALD", "original_label": "**GERALD:**", "start_ms": 3000, "end_ms": 32000, "text": '"Never."', "line_start": 3, "line_end": 4},
            ],
            "warnings": [],
            "parser_version": "1.0.0",
        },
    ]


def test_cookie_session_isolation_and_ownership():
    """Verify HttpOnly cookie secret is issued, hashed, and enforces run ownership."""
    client_a = TestClient(app)
    episodes = make_synthetic_episodes()

    # 1. Client A creates a run
    resp_a = client_a.post(
        "/api/runs",
        json={"name": "Client A Run", "episodes": episodes},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp_a.status_code == 201
    run_a = resp_a.json()
    run_a_id = run_a["id"]
    assert "kuku_session" in client_a.cookies

    # 2. Client A can retrieve their run
    get_a = client_a.get(f"/api/runs/{run_a_id}")
    assert get_a.status_code == 200
    assert get_a.json()["id"] == run_a_id

    # 3. Client A lists runs -> sees their run
    list_a = client_a.get("/api/runs")
    assert list_a.status_code == 200
    assert any(r["id"] == run_a_id for r in list_a.json())

    # 4. Client B with a different session
    client_b = TestClient(app)
    # Ping session to get a distinct cookie
    client_b.get("/api/session")
    assert client_b.cookies.get("kuku_session") != client_a.cookies.get("kuku_session")

    # Client B cannot see Client A's run in list
    list_b = client_b.get("/api/runs")
    assert list_b.status_code == 200
    assert not any(r["id"] == run_a_id for r in list_b.json())

    # Client B cannot get, analyze, or export Client A's run (returns 404 to avoid disclosure)
    assert client_b.get(f"/api/runs/{run_a_id}").status_code == 404
    assert client_b.get(f"/api/runs/{run_a_id}/ranking").status_code == 404
    assert client_b.get(f"/api/runs/{run_a_id}/export/csv").status_code == 404
    assert client_b.get(f"/api/runs/{run_a_id}/export/json").status_code == 404


def test_origin_validation_for_state_changing_requests():
    """Verify cross-origin requests from untrusted origins are blocked with 403."""
    episodes = make_synthetic_episodes()

    # Disallowed origin is rejected with 403
    resp_blocked = client.post(
        "/api/runs",
        json={"name": "Attacker Run", "episodes": episodes},
        headers={"Origin": "http://evil-attacker.com"},
    )
    assert resp_blocked.status_code == 403

    # Allowed origin succeeds
    resp_allowed = client.post(
        "/api/runs",
        json={"name": "Legit Run", "episodes": episodes},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp_allowed.status_code == 201


def test_atomic_duplicate_claim_rejection():
    """Verify that a second concurrent attempt to claim an actively leased episode is rejected."""
    episodes = make_synthetic_episodes()
    db = TestSessionFactory()
    try:
        session_secret = "secret_claim_test_123"
        session_hash = hashlib.sha256(session_secret.encode()).hexdigest()
        run = runs_service.create_run(db=db, episodes=episodes, name="Claim Test", session_hash=session_hash)
        ep1_id = run.episodes[0].id

        # Worker 1 claims episode with 120s lease
        ep_rec, token_1, attempt_1 = runs_service.claim_episode_for_analysis(
            db=db,
            run_id=run.id,
            episode_id=ep1_id,
            session_hash=session_hash,
            lease_duration_seconds=120,
        )
        assert token_1 is not None
        assert attempt_1 == 1
        assert ep_rec.analysis_status == "analyzing"

        # Worker 2 immediately tries to claim the same episode while lease is active
        with pytest.raises(LeaseConflictError) as exc_info:
            runs_service.claim_episode_for_analysis(
                db=db,
                run_id=run.id,
                episode_id=ep1_id,
                session_hash=session_hash,
                lease_duration_seconds=120,
            )
        assert "locked by active lease" in str(exc_info.value)

    finally:
        db.close()


def test_expired_lease_claim_recovery():
    """Verify that an abandoned/expired lease is safely recovered by a new claim."""
    episodes = make_synthetic_episodes()
    db = TestSessionFactory()
    try:
        session_secret = "secret_expired_test_123"
        session_hash = hashlib.sha256(session_secret.encode()).hexdigest()
        run = runs_service.create_run(db=db, episodes=episodes, name="Expired Lease Test", session_hash=session_hash)
        ep1_id = run.episodes[0].id

        # Simulate Worker 1 crashing and leaving an expired lease in the past
        ep_rec = db.query(models.EpisodeRecord).filter(models.EpisodeRecord.id == ep1_id).first()
        ep_rec.analysis_status = "analyzing"
        ep_rec.lease_token = "old_stale_token"
        ep_rec.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        ep_rec.attempt_number = 1
        db.commit()

        # Worker 2 attempts to claim: should succeed and recover abandoned state
        recovered_ep, new_token, new_attempt = runs_service.claim_episode_for_analysis(
            db=db,
            run_id=run.id,
            episode_id=ep1_id,
            session_hash=session_hash,
            lease_duration_seconds=120,
        )
        assert new_token != "old_stale_token"
        assert new_attempt == 2
        assert recovered_ep.analysis_status == "analyzing"
        assert runs_service.ensure_utc(recovered_ep.lease_expires_at) > datetime.now(timezone.utc)

    finally:
        db.close()


def test_stale_attempt_save_rejection():
    """Verify late attempts cannot overwrite newer attempts or expired leases."""
    episodes = make_synthetic_episodes()
    db = TestSessionFactory()
    try:
        session_secret = "secret_stale_test_123"
        session_hash = hashlib.sha256(session_secret.encode()).hexdigest()
        run = runs_service.create_run(db=db, episodes=episodes, name="Stale Save Test", session_hash=session_hash)
        ep1_id = run.episodes[0].id

        # Worker 1 claims episode (attempt 1)
        _, token_1, attempt_1 = runs_service.claim_episode_for_analysis(
            db=db,
            run_id=run.id,
            episode_id=ep1_id,
            session_hash=session_hash,
            lease_duration_seconds=1,
        )

        # Worker 1 runs slow... Worker 2 claims episode after expiration (attempt 2)
        ep_rec = db.query(models.EpisodeRecord).filter(models.EpisodeRecord.id == ep1_id).first()
        ep_rec.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()

        _, token_2, attempt_2 = runs_service.claim_episode_for_analysis(
            db=db,
            run_id=run.id,
            episode_id=ep1_id,
            session_hash=session_hash,
            lease_duration_seconds=120,
        )
        assert attempt_2 == 2

        # Now Worker 1 finishes late and tries to write result for attempt 1
        mock_provider = MockAIProvider()
        mock_res = runs_service.analyze_episode_for_promos(
            episode=Episode(
                id="ep_1",
                episode_number=1,
                filename="ep1.txt",
                duration_ms=30000,
                scenes=[],
                events=[],
                warnings=[],
                content_hash="hash_ep1",
                parser_version="1.0.0",
            ),
            provider=mock_provider,
        )

        with pytest.raises(StaleAttemptError) as exc_info:
            runs_service.save_episode_analysis_result(
                db=db,
                run_id=run.id,
                episode_id=ep1_id,
                lease_token=token_1,  # Stale token
                attempt_number=attempt_1,
                result=mock_res,
            )
        assert "Stale attempt 1 rejected" in str(exc_info.value)

    finally:
        db.close()


def test_quota_pause_error_handling():
    """Verify quota exhaustion stops processing, returns HTTP 429, and supports pause/resume."""
    episodes = make_synthetic_episodes()
    db = TestSessionFactory()
    try:
        session_secret = "secret_quota_test"
        session_hash = hashlib.sha256(session_secret.encode()).hexdigest()
        run = runs_service.create_run(db=db, episodes=episodes, name="Quota Test", session_hash=session_hash)
        ep1_id = run.episodes[0].id

        # Analyze with quota failing provider
        quota_provider = QuotaFailingProvider()
        with pytest.raises(AIQuotaExceededError):
            runs_service.analyze_episode(
                db=db,
                run_id=run.id,
                episode_id=ep1_id,
                session_hash=session_hash,
                provider=quota_provider,
            )

        # Episode status transitions to failed with error message
        reloaded = runs_service.get_run(db=db, run_id=run.id, session_hash=session_hash)
        assert reloaded.episodes[0].analysis_status == "failed"
        assert "Resource exhausted" in (reloaded.episodes[0].error_message or "")

        # Pause run
        paused = runs_service.pause_run(db=db, run_id=run.id, session_hash=session_hash)
        assert paused.status == "paused"

        # Resume run
        resumed = runs_service.resume_run(db=db, run_id=run.id, session_hash=session_hash)
        assert resumed.status == "running"

    finally:
        db.close()


def test_unassessed_candidates_excluded_from_scored_ranking_and_provisional_label():
    """Verify unassessed candidates are excluded from scored rankings and rankings are marked provisional."""
    episodes = make_synthetic_episodes()
    db = TestSessionFactory()
    try:
        session_secret = "secret_ranking_test"
        session_hash = hashlib.sha256(session_secret.encode()).hexdigest()
        run = runs_service.create_run(db=db, episodes=episodes, name="Ranking Test", session_hash=session_hash)
        ep1_id = run.episodes[0].id

        # Analyze Episode 1
        mock_provider = MockAIProvider(score=4.6)
        runs_service.analyze_episode(
            db=db,
            run_id=run.id,
            episode_id=ep1_id,
            session_hash=session_hash,
            provider=mock_provider,
        )

        # Manually add an unassessed candidate to DB
        unassessed_promo = models.PromoCandidate(
            id="unassessed_cand_1",
            run_id=run.id,
            episode_id=ep1_id,
            rank=99,
            editorial_title="Unassessed Cut",
            overall_score=None,  # No score!
            duration_ms=25000,
            hook_description="Hook",
            cliffhanger_description="End",
            why_it_works="Why",
            candidate_data_json={"id": "unassessed_cand_1", "editorial_title": "Unassessed Cut"},
            status="suggested",
        )
        db.add(unassessed_promo)
        db.commit()

        # Fetch show-wide ranking
        ranking = runs_service.get_show_wide_ranking(db=db, run_id=run.id, session_hash=session_hash)

        # 1. Provisional check: only 1 of 2 episodes completed
        assert ranking.is_provisional is True
        assert ranking.completed_episodes == 1
        assert ranking.total_episodes == 2
        assert ranking.coverage_percentage == 50.0

        # 2. Unassessed candidates count
        assert ranking.unassessed_candidates_count == 1

        # 3. Only the assessed candidate is present in scored rankings
        assert ranking.total_candidates == 1
        assert ranking.candidates[0].editorial_title == "Betrayal Cut"
        assert ranking.candidates[0].rank == 1

    finally:
        db.close()


def test_export_ranking_csv_and_json_enforces_session():
    """Verify export endpoints enforce session ownership and format outputs."""
    client_sess = TestClient(app)
    episodes = make_synthetic_episodes()
    resp = client_sess.post(
        "/api/runs",
        json={"name": "Export Test Run", "episodes": episodes},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 201
    run_id = resp.json()["id"]

    # Export JSON with matching session
    json_resp = client_sess.get(f"/api/runs/{run_id}/export/json")
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers["content-type"]
    assert json_resp.json()["id"] == run_id

    # Export CSV with matching session
    csv_resp = client_sess.get(f"/api/runs/{run_id}/export/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    lines = csv_resp.text.strip().split("\r\n")
    assert "Show Rank,Episode Rank,Title" in lines[0]

    # Another client without session cookie gets 404
    client_intruder = TestClient(app)
    assert client_intruder.get(f"/api/runs/{run_id}/export/json").status_code == 404
    assert client_intruder.get(f"/api/runs/{run_id}/export/csv").status_code == 404
