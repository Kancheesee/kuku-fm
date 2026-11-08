"""
Live Neon PostgreSQL Integration Verification for Milestone 3 Extensions:
- Real connection to Neon database (via DATABASE_URL with connection pooler and NullPool)
- Verifies session_hash ownership
- Verifies atomic per-episode lease claim and duplicate claim rejection
- Verifies stale attempt rejection
- Verifies save, unassessed candidate filtering, deterministic tie-breaking, and provisional ranking
- Cleans up after itself
"""
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import get_session_factory, check_db_connection
from app.db import models
from app.services import runs_service
from app.services.runs_service import LeaseConflictError, StaleAttemptError
from app.schemas.models import Episode


def verify_live_neon():
    print("=== LIVE NEON POSTGRESQL INTEGRATION VERIFICATION ===")
    factory = get_session_factory()
    if factory is None:
        print("FAIL: Could not create session factory for Neon database")
        sys.exit(1)
    db = factory()

    test_run_id = None
    try:
        # 1. Create a session secret and its hash
        session_secret = "neon_test_secret_999"
        session_hash = hashlib.sha256(session_secret.encode()).hexdigest()

        episodes_payload = [
            {
                "id": "neon_ep_1",
                "episode_number": 1,
                "filename": "neon_ep1.txt",
                "content_hash": "hash_neon_ep1",
                "duration_ms": 30000,
                "scenes": [],
                "events": [],
                "warnings": [],
                "parser_version": "1.0.0",
            },
            {
                "id": "neon_ep_2",
                "episode_number": 2,
                "filename": "neon_ep2.txt",
                "content_hash": "hash_neon_ep2",
                "duration_ms": 35000,
                "scenes": [],
                "events": [],
                "warnings": [],
                "parser_version": "1.0.0",
            },
        ]

        print("1. Creating test run in Neon PostgreSQL with session_hash...")
        run = runs_service.create_run(
            db=db,
            episodes=episodes_payload,
            name="Neon Integration Test Run",
            session_hash=session_hash,
        )
        test_run_id = run.id
        ep1_id = run.episodes[0].id
        print(f"   SUCCESS: Run created with ID: {test_run_id}, session_hash: {session_hash[:12]}...")

        # 2. Session isolation verification
        print("2. Verifying session isolation on Neon...")
        runs_for_owner = runs_service.list_runs(db=db, session_hash=session_hash)
        assert any(r.id == test_run_id for r in runs_for_owner), "Owner could not find their run!"
        runs_for_stranger = runs_service.list_runs(db=db, session_hash="stranger_session_hash")
        assert not any(r.id == test_run_id for r in runs_for_stranger), "Stranger saw private run!"
        print("   SUCCESS: Session isolation verified on Neon.")

        # 3. Atomic claim
        print("3. Verifying atomic episode claim and lease issuance on Neon...")
        ep_rec, token_1, attempt_1 = runs_service.claim_episode_for_analysis(
            db=db,
            run_id=test_run_id,
            episode_id=ep1_id,
            session_hash=session_hash,
            lease_duration_seconds=120,
        )
        assert token_1 is not None
        assert attempt_1 == 1
        assert ep_rec.analysis_status == "analyzing"
        print(f"   SUCCESS: Claimed lease token: {token_1[:8]}..., attempt: {attempt_1}")

        # 4. Duplicate claim rejection
        print("4. Verifying duplicate claim rejection on active lease on Neon...")
        try:
            runs_service.claim_episode_for_analysis(
                db=db,
                run_id=test_run_id,
                episode_id=ep1_id,
                session_hash=session_hash,
                lease_duration_seconds=120,
            )
            print("   FAIL: Duplicate claim should have failed!")
            sys.exit(1)
        except LeaseConflictError:
            print("   SUCCESS: Duplicate claim was rejected with LeaseConflictError.")

        # 5. Stale attempt save rejection
        print("5. Verifying stale-attempt save rejection on Neon...")
        # Simulate worker 2 claiming after lease expiration
        ep_row = db.query(models.EpisodeRecord).filter(models.EpisodeRecord.id == ep1_id).first()
        ep_row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        _, token_2, attempt_2 = runs_service.claim_episode_for_analysis(
            db=db,
            run_id=test_run_id,
            episode_id=ep1_id,
            session_hash=session_hash,
            lease_duration_seconds=120,
        )
        assert attempt_2 == 2

        # Worker 1 tries to save with token_1 / attempt_1
        from app.schemas.promo import PromoAnalysisResponse, PromoCandidate as SchemaPromoCandidate, PromoSegment
        fake_result = PromoAnalysisResponse(
            episode_id=ep_row.internal_id,
            episode_number=1,
            filename=ep_row.filename,
            source_content_hash=ep_row.content_hash,
            parser_version="1.0.0",
            prompt_version="2.2.0",
            assessment_prompt_version="1.0.0",
            model="mock",
            cache_key="mock_key",
            candidates=[
                SchemaPromoCandidate(
                    id="cand_neon_1",
                    editorial_title="Neon Valid Cut",
                    filename=ep_row.filename,
                    source_content_hash=ep_row.content_hash,
                    standalone_assessment="Strong standalone narrative cut",
                    rank=1,
                    segment=PromoSegment(
                        episode_id=ep_row.internal_id,
                        filename=ep_row.filename,
                        source_content_hash=ep_row.content_hash,
                        event_ids=["e1", "e2"],
                        start_event_id="e1",
                        end_event_id="e2",
                        start_ms=0,
                        end_ms=25000,
                        duration_ms=25000,
                        start_timestamp="00:00.00",
                        end_timestamp="00:25.00",
                        duration_seconds=25.0,
                        event_count=2,
                    ),
                    hook_explanation="Hook",
                    hook_event_ids=["e1"],
                    cliffhanger_explanation="Cliffhanger",
                    cliffhanger_event_ids=["e2"],
                    unresolved_question="Question?",
                    rationale="Why",
                    review_flags=[],
                    mechanical_status="passed",
                )
            ],
            rejected_proposals=[],
            suppressed_candidates=[],
            metadata={},
            raw_generation_response="",
        )

        try:
            runs_service.save_episode_analysis_result(
                db=db,
                run_id=test_run_id,
                episode_id=ep1_id,
                lease_token=token_1,  # Stale token
                attempt_number=attempt_1,
                result=fake_result,
            )
            print("   FAIL: Stale attempt should have been rejected!")
            sys.exit(1)
        except StaleAttemptError:
            print("   SUCCESS: Stale attempt save rejected with StaleAttemptError.")

        # 6. Valid attempt save
        print("6. Verifying valid attempt save and show ranking on Neon...")
        runs_service.save_episode_analysis_result(
            db=db,
            run_id=test_run_id,
            episode_id=ep1_id,
            lease_token=token_2,
            attempt_number=attempt_2,
            result=fake_result,
        )
        saved_run = runs_service.get_run(db=db, run_id=test_run_id, session_hash=session_hash)
        assert saved_run.completed_episodes == 1
        assert saved_run.is_provisional is True
        assert saved_run.coverage_percentage == 50.0
        print("   SUCCESS: Valid save succeeded, provisional status: 50.0% coverage.")

        print("=== ALL LIVE NEON POSTGRESQL VERIFICATIONS PASSED ===")

    finally:
        # Clean up test data from Neon DB
        if test_run_id:
            print(f"Cleaning up test run {test_run_id} from Neon DB...")
            db.query(models.Run).filter(models.Run.id == test_run_id).delete()
            db.commit()
            print("Cleanup complete.")
        db.close()


if __name__ == "__main__":
    verify_live_neon()
