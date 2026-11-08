import io
from starlette.testclient import TestClient

from api.index import app
from app.schemas.models import Episode
from app.schemas.promo import CandidateAssessmentItem, RawCandidateProposal
from app.services.ai.base import (
    AIProvider,
    AIQuotaExceededError,
    AssessmentResult,
    GenerationResult,
)
from app.services.ai.orchestrator import analyze_episode_for_promos

client = TestClient(app)


class AssessmentFailingProvider(AIProvider):
    """Provider that succeeds generation but fails assessment with a generic error."""
    def generate_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        return GenerationResult(
            raw_response_text='{"candidates": []}',
            parsed_candidates=[
                RawCandidateProposal(
                    editorial_title="Valid Cut",
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
        raise RuntimeError("Transient assessment model refusal or timeout")


class AssessmentQuotaFailingProvider(AIProvider):
    """Provider that succeeds generation but fails assessment with a Quota error."""
    def generate_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        return GenerationResult(
            raw_response_text='{"candidates": []}',
            parsed_candidates=[
                RawCandidateProposal(
                    editorial_title="Valid Cut",
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
        raise AIQuotaExceededError("Quota exhausted during assessment call")


def make_test_episode() -> Episode:
    return Episode(
        id="ep_test",
        episode_number=1,
        filename="test.txt",
        duration_ms=30000,
        scenes=[
            {
                "id": "s1",
                "scene_label": "SCENE 01",
                "heading": "INT. ROOM",
                "start_ms": 0,
                "end_ms": 30000,
                "line_start": 1,
                "line_end": 5,
            }
        ],
        events=[
            {
                "id": "e1",
                "scene_id": "s1",
                "category": "action",
                "original_label": "**ACTION:**",
                "start_ms": 0,
                "end_ms": 4000,
                "text": "Action",
                "line_start": 2,
                "line_end": 2,
            },
            {
                "id": "e2",
                "scene_id": "s1",
                "category": "dialogue",
                "speaker": "JULIANA",
                "original_label": "**JULIANA:**",
                "start_ms": 4000,
                "end_ms": 30000,
                "text": '"Goodbye."',
                "line_start": 3,
                "line_end": 4,
            },
        ],
        warnings=[],
        content_hash="test_hash_123",
        parser_version="1.0.0",
    )


def test_vercel_entrypoint_and_health():
    """Verify api/index.py exposes the FastAPI app and /api/health responds."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_vercel_preview_origin_allowed(monkeypatch):
    """Verify that trusted project preview URLs derived from Vercel env vars are accepted."""
    monkeypatch.setenv("VERCEL_BRANCH_URL", "kuku-promo-studio-git-feat-team.vercel.app")
    response = client.post(
        "/api/runs",
        json={"name": "Preview Test Run", "episodes": []},
        headers={"Origin": "https://kuku-promo-studio-git-feat-team.vercel.app"},
    )
    # Origin check passed; fails on validation (0 episodes) with 400, NOT 403 Forbidden
    assert response.status_code == 400
    assert "0 episodes" in response.json()["detail"]


def test_untrusted_vercel_origin_blocked():
    """Verify that untrusted third-party *.vercel.app origins are rejected with 403."""
    response = client.post(
        "/api/runs",
        json={"name": "Attacker Run", "episodes": []},
        headers={"Origin": "https://malicious-other-app.vercel.app"},
    )
    assert response.status_code == 403
    assert "Cross-origin request rejected" in response.json()["detail"]


def test_malicious_origin_blocked():
    """Verify that untrusted foreign origins are rejected with 403."""
    response = client.post(
        "/api/runs",
        json={"name": "Attacker Run", "episodes": []},
        headers={"Origin": "https://malicious-phishing-site.com"},
    )
    assert response.status_code == 403
    assert "Cross-origin request rejected" in response.json()["detail"]


def test_ingest_payload_limit_enforcement():
    """Verify uploads exceeding 4.4 MB guard return 413 Request Entity Too Large."""
    # Create dummy 4.6 MB file
    oversized_content = b"A" * (4_500_000)
    files = [("files", ("huge.txt", io.BytesIO(oversized_content), "text/plain"))]
    response = client.post("/api/ingest/preview", files=files)
    assert response.status_code == 413
    assert "exceeds the 4.5MB Vercel serverless limit" in response.json()["detail"]


def test_preserve_candidates_on_assessment_failure():
    """Verify mechanically valid candidates are preserved when Call 2 (assessment) fails generically."""
    provider = AssessmentFailingProvider()
    episode = make_test_episode()

    res = analyze_episode_for_promos(episode=episode, provider=provider)
    assert len(res.candidates) == 1
    candidate = res.candidates[0]
    assert candidate.editorial_title == "Valid Cut"
    assert candidate.assessment_status == "unavailable"
    assert candidate.rubric is None
    assert "assessment_error" in res.metadata
    assert "Transient assessment model refusal" in res.metadata["assessment_error"]


def test_propagate_quota_error_during_assessment():
    """Verify AIQuotaExceededError in assessment carries partial_result with generated candidates."""
    provider = AssessmentQuotaFailingProvider()
    episode = make_test_episode()

    import pytest
    with pytest.raises(AIQuotaExceededError) as exc_info:
        analyze_episode_for_promos(episode=episode, provider=provider)

    err = exc_info.value
    assert err.partial_result is not None
    assert len(err.partial_result.candidates) == 1
    assert err.partial_result.candidates[0].editorial_title == "Valid Cut"
    assert err.partial_result.candidates[0].assessment_status == "unavailable"
    assert err.partial_result.candidates[0].rubric is None


def test_assessment_quota_exhaustion_persists_candidates_and_retry_resumes():
    """
    Verify requirement 4:
    1. When Call 2 (assessment) hits quota, generation candidates are persisted to the DB
       before raising AIQuotaExceededError (which returns 429 to pause the batch).
    2. Explicit retry resumes assessment directly on existing candidates without repeating generation.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.session import Base
    from app.db import models
    from app.services import runs_service
    import pytest

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Create run with 1 episode
        ep = make_test_episode()
        ep_dict = {
            "id": "ep_1",
            "episode_number": 1,
            "filename": "ep1.txt",
            "content_hash": ep.content_hash,
            "duration_ms": ep.duration_ms,
            "scenes": [s.model_dump() for s in ep.scenes],
            "events": [ev.model_dump() for ev in ep.events],
            "warnings": [],
        }
        run = runs_service.create_run(db=db, episodes=[ep_dict], name="Quota Persistence Run")
        ep_rec_id = run.episodes[0].id

        # 1. First attempt fails at assessment due to quota
        quota_provider = AssessmentQuotaFailingProvider()
        with pytest.raises(AIQuotaExceededError):
            runs_service.analyze_episode(
                db=db,
                run_id=run.id,
                episode_id=ep_rec_id,
                provider=quota_provider,
            )

        # Verify DB state: episode failed, but candidate & generation result PERSISTED!
        db.expire_all()
        ep_record = db.query(models.EpisodeRecord).filter_by(id=ep_rec_id).first()
        assert ep_record.analysis_status == "failed"
        assert "Quota exhausted" in ep_record.error_message or "Quota exceeded" in ep_record.error_message
        assert ep_record.analysis_result_json is not None
        assert len(ep_record.analysis_result_json["candidates"]) == 1

        db_candidates = db.query(models.PromoCandidate).filter_by(episode_id=ep_rec_id).all()
        assert len(db_candidates) == 1
        assert db_candidates[0].overall_score is None  # Unassessed candidate kept outside scored ranking

        # 2. Retry with a provider where quota has reset: resumes assessment!
        class SuccessfulAssessmentProvider(AIProvider):
            def generate_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
                raise AssertionError("generate_candidates should NOT be called on resumed assessment retry!")

            def assess_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
                return AssessmentResult(
                    raw_response_text='{"assessments": []}',
                    assessments=[
                        CandidateAssessmentItem(
                            candidate_index=1,
                            opening_strength=5,
                            standalone_clarity=4,
                            escalation_stakes=4,
                            unresolved_ending=5,
                            overall_score=4.5,
                            opening_reason="Great hook",
                            clarity_reason="Clear premise",
                            stakes_reason="High stakes",
                            ending_reason="Unresolved cliffhanger",
                            grounded_unresolved_question="Will Juliana escape?",
                        )
                    ],
                    model_identifier="mock-model",
                    prompt_version="2.2.0",
                    token_usage={"total_tokens": 150},
                    latency_ms=120,
                )

        resumed_res = runs_service.retry_episode(
            db=db,
            run_id=run.id,
            episode_id=ep_rec_id,
            provider=SuccessfulAssessmentProvider(),
        )

        assert resumed_res.candidates[0].assessment_status == "assessed"
        assert resumed_res.candidates[0].rubric.overall_score == 4.55

        db.expire_all()
        ep_record = db.query(models.EpisodeRecord).filter_by(id=ep_rec_id).first()
        assert ep_record.analysis_status == "completed"
        assert ep_record.retry_count == 1
    finally:
        db.close()


def test_pipeline_deadline_skips_assessment_when_budget_low(monkeypatch):
    """Verify that when remaining pipeline time is below safety margin, Call 2 is skipped gracefully."""
    provider = AssessmentFailingProvider()
    episode = make_test_episode()

    # Simulate that generation took 70 seconds out of 90s deadline, leaving only 20s (< 30s min budget)
    start_time = 1000.0
    times = [start_time, start_time + 70.0, start_time + 70.0, start_time + 70.0]

    def mock_time():
        if times:
            return times.pop(0)
        return start_time + 70.0

    monkeypatch.setattr("app.services.ai.orchestrator.time.time", mock_time)

    res = analyze_episode_for_promos(episode=episode, provider=provider)
    assert len(res.candidates) == 1
    assert res.candidates[0].assessment_status == "unavailable"
    assert "deadline threshold reached" in res.metadata["assessment_error"]


def test_vercel_rewrites_exclude_assets_and_api():
    """Verify vercel.json rewrites exclude static assets and api paths from SPA fallback."""
    import json
    import re

    with open("vercel.json", "r") as f:
        config = json.load(f)

    rewrites = config["rewrites"]
    api_rewrite = next(r for r in rewrites if r["destination"] == "/api/index.py")
    spa_rewrite = next(r for r in rewrites if r["destination"] == "/index.html")

    assert api_rewrite["source"] == "/api/(.*)"

    # Verify SPA fallback regex does not match /assets/ or /api/
    # Pattern: /((?!api|assets|favicon\.ico).*)
    spa_pattern = re.compile(r"^" + spa_rewrite["source"].replace("(.*)", ".*") + r"$")

    # Client navigation routes SHOULD rewrite to /index.html
    assert spa_pattern.match("/")
    assert spa_pattern.match("/runs/run-123")
    assert spa_pattern.match("/preview")

    # Static assets and api routes should NOT rewrite to /index.html
    assert not spa_pattern.match("/api/health")
    assert not spa_pattern.match("/assets/index-abc.js")
    assert not spa_pattern.match("/favicon.ico")


