import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db import models
from app.schemas.models import Episode, Event, ParsingIssue, Scene
from app.schemas.promo import PromoAnalysisResponse, PromoCandidate as SchemaPromoCandidate
from app.schemas.runs import (
    EpisodeRecordResponse,
    RunDetailResponse,
    RunSummaryResponse,
    ShowWideRankingResponse,
)
from app.services.ai.base import AIProvider, AIQuotaExceededError
from app.services.ai.orchestrator import analyze_episode_for_promos

logger = logging.getLogger(__name__)


class LeaseConflictError(Exception):
    """Raised when an episode is currently leased by an active attempt."""
    pass


class StaleAttemptError(Exception):
    """Raised when a late attempt tries to write results for a lease that expired or was superseded."""
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_run(
    db: Session,
    episodes: List[Dict[str, Any]],
    name: Optional[str] = None,
    session_hash: Optional[str] = None,
    browser_session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> RunDetailResponse:
    """Create and persist a new screenplay run and its episode records."""
    run_id = str(uuid.uuid4())
    run_name = name or f"Run {datetime.now(timezone.utc).strftime('%b %d, %H:%M')}"
    meta = metadata or {}
    meta["total_episodes"] = len(episodes)

    db_run = models.Run(
        id=run_id,
        name=run_name,
        status="ready",
        session_hash=session_hash,
        browser_session_id=browser_session_id,
        metadata_json=meta,
    )
    db.add(db_run)

    for ep_dict in episodes:
        ep_id = str(uuid.uuid4())
        internal_id = ep_dict.get("id") or f"ep_{ep_dict.get('episode_number', 0)}"
        ep_record = models.EpisodeRecord(
            id=ep_id,
            run_id=run_id,
            internal_id=internal_id,
            episode_number=ep_dict.get("episode_number"),
            filename=ep_dict.get("filename", "unknown.txt"),
            content_hash=ep_dict.get("content_hash", ""),
            duration_ms=ep_dict.get("duration_ms", 0),
            logline=ep_dict.get("logline"),
            continuity_notes=ep_dict.get("continuity_notes"),
            scenes_json=ep_dict.get("scenes", []),
            events_json=ep_dict.get("events", []),
            warnings_json=ep_dict.get("warnings", []),
            parser_version=ep_dict.get("parser_version", "1.0.0"),
            analysis_status="pending",
            retry_count=0,
            attempt_number=0,
        )
        db.add(ep_record)

    db.commit()
    db.refresh(db_run)
    return get_run(db, run_id, session_hash=session_hash)


def list_runs(db: Session, session_hash: Optional[str] = None) -> List[RunSummaryResponse]:
    """List runs, strictly filtered by session_hash to enforce session ownership."""
    if not session_hash:
        return []

    query = (
        db.query(models.Run)
        .filter(models.Run.session_hash == session_hash)
        .order_by(desc(models.Run.created_at))
        .limit(50)
    )
    runs = query.all()

    results = []
    for r in runs:
        total_ep = len(r.episodes)
        completed_ep = sum(1 for e in r.episodes if e.analysis_status == "completed")
        failed_ep = sum(1 for e in r.episodes if e.analysis_status == "failed")
        promos_count = len(r.promos)

        results.append(
            RunSummaryResponse(
                id=r.id,
                name=r.name,
                status=r.status,
                browser_session_id=r.browser_session_id,
                session_hash=r.session_hash,
                created_at=r.created_at.isoformat() if r.created_at else "",
                updated_at=r.updated_at.isoformat() if r.updated_at else "",
                total_episodes=total_ep,
                completed_episodes=completed_ep,
                failed_episodes=failed_ep,
                promos_count=promos_count,
                metadata=r.metadata_json or {},
            )
        )
    return results


def get_run(db: Session, run_id: str, session_hash: Optional[str] = None) -> Optional[RunDetailResponse]:
    """Retrieve full run details including episode records and show rankings."""
    query = db.query(models.Run).filter(models.Run.id == run_id)
    if session_hash:
        query = query.filter(models.Run.session_hash == session_hash)
    db_run = query.first()
    if not db_run:
        return None

    episodes_res = []
    for ep in db_run.episodes:
        parsed_result = None
        if ep.analysis_result_json:
            try:
                parsed_result = PromoAnalysisResponse.model_validate(ep.analysis_result_json)
            except Exception as e:
                logger.warning(f"Error parsing saved analysis result for episode {ep.id}: {e}")

        episodes_res.append(
            EpisodeRecordResponse(
                id=ep.id,
                run_id=ep.run_id,
                internal_id=ep.internal_id,
                episode_number=ep.episode_number,
                filename=ep.filename,
                content_hash=ep.content_hash,
                duration_ms=ep.duration_ms,
                analysis_status=ep.analysis_status,
                analysis_result=parsed_result,
                error_message=ep.error_message,
                retry_count=ep.retry_count,
                lease_token=ep.lease_token,
                lease_expires_at=ep.lease_expires_at.isoformat() if ep.lease_expires_at else None,
                attempt_number=ep.attempt_number or 0,
                scenes_count=len(ep.scenes_json or []),
                events_count=len(ep.events_json or []),
                warnings_count=len(ep.warnings_json or []),
            )
        )

    # Assessed show-wide promo candidates (scored only)
    show_candidates = []
    db_promos = (
        db.query(models.PromoCandidate)
        .filter(models.PromoCandidate.run_id == run_id, models.PromoCandidate.show_rank != None)  # noqa: E711
        .order_by(models.PromoCandidate.show_rank.asc())
        .all()
    )
    for p in db_promos:
        if p.candidate_data_json:
            try:
                cand = SchemaPromoCandidate.model_validate(p.candidate_data_json)
                cand.rank = p.show_rank or cand.rank
                show_candidates.append(cand)
            except Exception:
                pass

    total_ep = len(db_run.episodes)
    completed_ep = sum(1 for e in db_run.episodes if e.analysis_status == "completed")
    failed_ep = sum(1 for e in db_run.episodes if e.analysis_status == "failed")
    is_provisional = completed_ep < total_ep
    coverage_pct = round((completed_ep / total_ep) * 100.0, 1) if total_ep > 0 else 0.0

    return RunDetailResponse(
        id=db_run.id,
        name=db_run.name,
        status=db_run.status,
        browser_session_id=db_run.browser_session_id,
        session_hash=db_run.session_hash,
        created_at=db_run.created_at.isoformat() if db_run.created_at else "",
        updated_at=db_run.updated_at.isoformat() if db_run.updated_at else "",
        total_episodes=total_ep,
        completed_episodes=completed_ep,
        failed_episodes=failed_ep,
        is_provisional=is_provisional,
        coverage_percentage=coverage_pct,
        episodes=episodes_res,
        show_ranking=show_candidates,
        metadata=db_run.metadata_json or {},
    )


def recompute_show_wide_rankings(db: Session, run_id: str) -> None:
    """
    Rank all accepted promo candidates across all episodes in the run.
    - Excludes unassessed candidates (where overall_score is None) from scored rankings.
    - Uses deterministic multi-key tie-breaker:
      1. overall_score DESC
      2. duration_ms DESC
      3. episode_number ASC
      4. start_ms ASC
      5. candidate_id ASC
    """
    promos = db.query(models.PromoCandidate).filter(models.PromoCandidate.run_id == run_id).all()
    if not promos:
        return

    assessed: List[models.PromoCandidate] = []
    for p in promos:
        if p.overall_score is not None:
            assessed.append(p)
        else:
            # Unassessed candidate: keep outside scored ranking
            p.show_rank = None
            if p.candidate_data_json and isinstance(p.candidate_data_json, dict):
                p.candidate_data_json["show_rank"] = None

    def promo_sort_key(p: models.PromoCandidate):
        score = p.overall_score if p.overall_score is not None else 0.0
        dur = p.duration_ms or 0
        ep_num = 999999
        start_ms = 0
        if p.episode and p.episode.episode_number is not None:
            ep_num = p.episode.episode_number
        if p.candidate_data_json and isinstance(p.candidate_data_json, dict):
            seg = p.candidate_data_json.get("segment", {})
            start_ms = seg.get("start_ms", 0)
        # We sort with tuple: negative for desc, positive for asc
        return (-score, -dur, ep_num, start_ms, str(p.id))

    assessed.sort(key=promo_sort_key)

    for idx, p in enumerate(assessed, start=1):
        p.show_rank = idx
        if p.candidate_data_json and isinstance(p.candidate_data_json, dict):
            p.candidate_data_json["show_rank"] = idx

    db.commit()


def claim_episode_for_analysis(
    db: Session,
    run_id: str,
    episode_id: str,
    session_hash: Optional[str] = None,
    lease_duration_seconds: int = 120,
) -> Tuple[models.EpisodeRecord, str, int]:
    """
    Atomically claim an episode for analysis within a bounded lease.
    - Prevents concurrent duplicate analysis.
    - Recovers abandoned analyzing states when lease has expired.
    - Runs in a short, dedicated database transaction.
    """
    # Enforce run ownership
    run_query = db.query(models.Run).filter(models.Run.id == run_id)
    if session_hash:
        run_query = run_query.filter(models.Run.session_hash == session_hash)
    run = run_query.first()
    if not run:
        raise ValueError(f"Run {run_id} not found or unauthorized")

    # Atomic row-lock on EpisodeRecord
    ep = (
        db.query(models.EpisodeRecord)
        .filter(models.EpisodeRecord.run_id == run_id, models.EpisodeRecord.id == episode_id)
        .with_for_update()
        .first()
    )
    if not ep:
        raise ValueError(f"Episode {episode_id} not found in run {run_id}")

    now = utc_now()

    # Check if episode is currently claimable
    if ep.analysis_status == "completed":
        raise LeaseConflictError(f"Episode {episode_id} has already completed analysis.")

    if ep.analysis_status == "analyzing":
        lease_exp = ensure_utc(ep.lease_expires_at)
        if lease_exp and lease_exp > now:
            raise LeaseConflictError(
                f"Episode {episode_id} is currently locked by active lease until {lease_exp.isoformat()}."
            )
        else:
            logger.warning(
                f"Recovering abandoned analyzing state for episode {episode_id} (lease expired at {lease_exp})"
            )

    # Issue new atomic lease
    lease_token = secrets.token_hex(16)
    attempt_num = (ep.attempt_number or 0) + 1

    ep.analysis_status = "analyzing"
    ep.lease_token = lease_token
    ep.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
    ep.attempt_number = attempt_num
    ep.error_message = None

    if run.status in ("ready", "paused"):
        run.status = "running"

    db.commit()
    db.refresh(ep)
    return ep, lease_token, attempt_num


def save_episode_analysis_result(
    db: Session,
    run_id: str,
    episode_id: str,
    lease_token: str,
    attempt_number: int,
    result: PromoAnalysisResponse,
) -> None:
    """
    Atomically persist analysis result, strictly validating attempt ownership and lease token.
    Stops late/stale attempts from overwriting newer results.
    """
    ep = (
        db.query(models.EpisodeRecord)
        .filter(models.EpisodeRecord.run_id == run_id, models.EpisodeRecord.id == episode_id)
        .with_for_update()
        .first()
    )
    if not ep:
        raise ValueError(f"Episode {episode_id} not found")

    if ep.lease_token != lease_token or ep.attempt_number != attempt_number:
        logger.warning(
            f"Stale attempt rejected for episode {episode_id}: "
            f"token={lease_token} (current={ep.lease_token}), attempt={attempt_number} (current={ep.attempt_number})"
        )
        raise StaleAttemptError(
            f"Stale attempt {attempt_number} rejected; lease expired or was claimed by another worker."
        )

    ep.analysis_status = "completed"
    ep.analysis_result_json = result.model_dump()
    ep.error_message = None
    ep.lease_token = None
    ep.lease_expires_at = None

    # Delete existing promos for this episode
    db.query(models.PromoCandidate).filter(
        models.PromoCandidate.run_id == run_id,
        models.PromoCandidate.episode_id == episode_id,
    ).delete()

    # Insert new promos
    for cand in result.candidates:
        score = cand.rubric.overall_score if cand.rubric else None
        db_promo = models.PromoCandidate(
            id=cand.id,
            run_id=run_id,
            episode_id=episode_id,
            rank=cand.rank,
            editorial_title=cand.editorial_title,
            overall_score=score,
            duration_ms=cand.segment.duration_ms,
            hook_description=cand.hook_explanation,
            cliffhanger_description=cand.cliffhanger_explanation,
            why_it_works=cand.rationale,
            unresolved_question=cand.unresolved_question,
            segments_json=[cand.segment.model_dump()],
            editorial_flags_json=cand.review_flags,
            candidate_data_json=cand.model_dump(),
            status="suggested",
        )
        db.add(db_promo)

    db.commit()

    # Recompute show-wide rankings
    recompute_show_wide_rankings(db, run_id)

    # Check if run as a whole completed
    db.expire_all()
    all_episodes = db.query(models.EpisodeRecord).filter(models.EpisodeRecord.run_id == run_id).all()
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if run:
        all_done = all(e.analysis_status == "completed" for e in all_episodes)
        if all_done:
            run.status = "completed"
        db.commit()


def record_episode_failure(
    db: Session,
    run_id: str,
    episode_id: str,
    lease_token: str,
    attempt_number: int,
    error_message: str,
) -> None:
    """Record an episode failure while releasing the lease."""
    ep = (
        db.query(models.EpisodeRecord)
        .filter(models.EpisodeRecord.run_id == run_id, models.EpisodeRecord.id == episode_id)
        .with_for_update()
        .first()
    )
    if not ep:
        return

    # Only record failure if attempt is still current
    if ep.lease_token == lease_token and ep.attempt_number == attempt_number:
        ep.analysis_status = "failed"
        ep.error_message = error_message
        ep.lease_token = None
        ep.lease_expires_at = None
        db.commit()


def analyze_episode(
    db: Session,
    run_id: str,
    episode_id: str,
    session_hash: Optional[str] = None,
    provider: Optional[AIProvider] = None,
    model_override: Optional[str] = None,
) -> PromoAnalysisResponse:
    """
    Analyze a single episode within a saved run.
    1. Atomic lease claim (DB transaction 1).
    2. AI discovery (runs OUTSIDE database transactions).
    3. Atomic save with stale-attempt verification (DB transaction 2).
    """
    # 1. Atomic claim
    ep_record, lease_token, attempt_num = claim_episode_for_analysis(
        db=db,
        run_id=run_id,
        episode_id=episode_id,
        session_hash=session_hash,
    )

    # Reconstruct Pydantic Episode schema for AI pipeline
    scenes = [Scene.model_validate(s) for s in (ep_record.scenes_json or [])]
    events = [Event.model_validate(ev) for ev in (ep_record.events_json or [])]
    warnings = [ParsingIssue.model_validate(w) for w in (ep_record.warnings_json or [])]

    episode_schema = Episode(
        id=ep_record.internal_id,
        episode_number=ep_record.episode_number,
        filename=ep_record.filename,
        logline=ep_record.logline,
        continuity_notes=ep_record.continuity_notes,
        duration_ms=ep_record.duration_ms,
        scenes=scenes,
        events=events,
        warnings=warnings,
        content_hash=ep_record.content_hash,
        parser_version=ep_record.parser_version,
    )

    # 2. AI execution OUTSIDE database transactions
    try:
        result = analyze_episode_for_promos(
            episode=episode_schema,
            provider=provider,
            model_override=model_override,
        )
    except Exception as e:
        logger.error(f"Failed to analyze episode {episode_id} in run {run_id}: {e}")
        record_episode_failure(
            db=db,
            run_id=run_id,
            episode_id=episode_id,
            lease_token=lease_token,
            attempt_number=attempt_num,
            error_message=str(e),
        )
        raise

    # 3. Save result with attempt validation
    save_episode_analysis_result(
        db=db,
        run_id=run_id,
        episode_id=episode_id,
        lease_token=lease_token,
        attempt_number=attempt_num,
        result=result,
    )
    return result


def pause_run(db: Session, run_id: str, session_hash: Optional[str] = None) -> RunDetailResponse:
    """Signal a running batch to pause."""
    query = db.query(models.Run).filter(models.Run.id == run_id)
    if session_hash:
        query = query.filter(models.Run.session_hash == session_hash)
    run = query.first()
    if not run:
        raise ValueError(f"Run {run_id} not found or unauthorized")

    run.status = "paused"
    db.commit()
    return get_run(db, run_id, session_hash=session_hash)


def resume_run(db: Session, run_id: str, session_hash: Optional[str] = None) -> RunDetailResponse:
    """Transition paused run back to running."""
    query = db.query(models.Run).filter(models.Run.id == run_id)
    if session_hash:
        query = query.filter(models.Run.session_hash == session_hash)
    run = query.first()
    if not run:
        raise ValueError(f"Run {run_id} not found or unauthorized")

    run.status = "running"
    db.commit()
    return get_run(db, run_id, session_hash=session_hash)


def retry_episode(
    db: Session,
    run_id: str,
    episode_id: str,
    session_hash: Optional[str] = None,
    provider: Optional[AIProvider] = None,
    model_override: Optional[str] = None,
) -> PromoAnalysisResponse:
    """Explicitly retry a failed episode, incrementing retry_count."""
    ep = (
        db.query(models.EpisodeRecord)
        .filter(models.EpisodeRecord.run_id == run_id, models.EpisodeRecord.id == episode_id)
        .with_for_update()
        .first()
    )
    if not ep:
        raise ValueError(f"Episode {episode_id} not found in run {run_id}")

    ep.retry_count = (ep.retry_count or 0) + 1
    ep.error_message = None
    ep.analysis_status = "pending"
    ep.lease_token = None
    ep.lease_expires_at = None
    db.commit()

    return analyze_episode(
        db=db,
        run_id=run_id,
        episode_id=episode_id,
        session_hash=session_hash,
        provider=provider,
        model_override=model_override,
    )


def get_show_wide_ranking(
    db: Session,
    run_id: str,
    session_hash: Optional[str] = None,
) -> ShowWideRankingResponse:
    """Get all candidates across the entire run ranked show-wide with provisional labeling."""
    query = db.query(models.Run).filter(models.Run.id == run_id)
    if session_hash:
        query = query.filter(models.Run.session_hash == session_hash)
    run = query.first()
    if not run:
        raise ValueError(f"Run {run_id} not found or unauthorized")

    recompute_show_wide_rankings(db, run_id)

    db_promos = (
        db.query(models.PromoCandidate)
        .filter(models.PromoCandidate.run_id == run_id, models.PromoCandidate.show_rank != None)  # noqa: E711
        .order_by(models.PromoCandidate.show_rank.asc())
        .all()
    )

    unassessed_count = (
        db.query(models.PromoCandidate)
        .filter(models.PromoCandidate.run_id == run_id, models.PromoCandidate.overall_score == None)  # noqa: E711
        .count()
    )

    candidates = []
    for p in db_promos:
        if p.candidate_data_json:
            try:
                cand = SchemaPromoCandidate.model_validate(p.candidate_data_json)
                cand.rank = p.show_rank or cand.rank
                candidates.append(cand)
            except Exception:
                pass

    total_ep = len(run.episodes)
    completed_ep = sum(1 for e in run.episodes if e.analysis_status == "completed")
    is_provisional = completed_ep < total_ep
    coverage_pct = round((completed_ep / total_ep) * 100.0, 1) if total_ep > 0 else 0.0

    return ShowWideRankingResponse(
        run_id=run.id,
        run_name=run.name,
        total_candidates=len(candidates),
        is_provisional=is_provisional,
        completed_episodes=completed_ep,
        total_episodes=total_ep,
        coverage_percentage=coverage_pct,
        unassessed_candidates_count=unassessed_count,
        candidates=candidates,
    )
