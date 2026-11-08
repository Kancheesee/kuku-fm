import csv
import io
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.session import get_or_create_session_hash, validate_request_origin
from app.db.session import get_db
from app.schemas.promo import PromoAnalysisResponse
from app.schemas.runs import (
    CreateRunFromPreviewRequest,
    RunDetailResponse,
    RunSummaryResponse,
    ShowWideRankingResponse,
)
from app.services import runs_service
from app.services.ai.base import AIQuotaExceededError
from app.services.runs_service import LeaseConflictError, StaleAttemptError

router = APIRouter()


def require_db(db: Optional[Session] = Depends(get_db)) -> Session:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence is currently unavailable. Check DATABASE_URL configuration.",
        )
    return db


@router.get("/session")
def check_session(
    session_hash: str = Depends(get_or_create_session_hash),
) -> Dict[str, Any]:
    """Ensure an HttpOnly session cookie exists and return active status."""
    return {"active": True}


@router.post("/runs", response_model=RunDetailResponse, status_code=status.HTTP_201_CREATED)
def create_saved_run(
    payload: CreateRunFromPreviewRequest,
    request: Request,
    response: Response,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> RunDetailResponse:
    """Save parsed screenplay episodes into a persistent Run record scoped to HttpOnly session."""
    validate_request_origin(request)
    if not payload.episodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a run with 0 episodes.",
        )
    return runs_service.create_run(
        db=db,
        episodes=payload.episodes,
        name=payload.name,
        session_hash=session_hash,
        metadata=payload.metadata,
    )


@router.get("/runs", response_model=List[RunSummaryResponse])
def list_saved_runs(
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> List[RunSummaryResponse]:
    """List saved runs, strictly filtered by current session hash."""
    return runs_service.list_runs(db=db, session_hash=session_hash)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_saved_run(
    run_id: str,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> RunDetailResponse:
    """Retrieve full run details, episode analysis statuses, and show rankings."""
    run = runs_service.get_run(db=db, run_id=run_id, session_hash=session_hash)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    return run


@router.post("/runs/{run_id}/episodes/{episode_id}/analyze", response_model=PromoAnalysisResponse)
def analyze_run_episode(
    run_id: str,
    episode_id: str,
    request: Request,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> PromoAnalysisResponse:
    """Trigger AI promo discovery for a single episode within a saved run (atomic claim + bounded lease)."""
    validate_request_origin(request)
    try:
        return runs_service.analyze_episode(
            db=db,
            run_id=run_id,
            episode_id=episode_id,
            session_hash=session_hash,
        )
    except LeaseConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except StaleAttemptError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AIQuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API quota exceeded: {e}",
            headers={"Retry-After": "60"},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {e}")


@router.post("/runs/{run_id}/pause", response_model=RunDetailResponse)
def pause_saved_run(
    run_id: str,
    request: Request,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> RunDetailResponse:
    """Pause an active batch run execution."""
    validate_request_origin(request)
    try:
        return runs_service.pause_run(db=db, run_id=run_id, session_hash=session_hash)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/runs/{run_id}/resume", response_model=RunDetailResponse)
def resume_saved_run(
    run_id: str,
    request: Request,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> RunDetailResponse:
    """Transition run back to running status."""
    validate_request_origin(request)
    try:
        return runs_service.resume_run(db=db, run_id=run_id, session_hash=session_hash)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/runs/{run_id}/episodes/{episode_id}/retry", response_model=PromoAnalysisResponse)
def retry_run_episode(
    run_id: str,
    episode_id: str,
    request: Request,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> PromoAnalysisResponse:
    """Explicitly retry analysis for a failed episode."""
    validate_request_origin(request)
    try:
        return runs_service.retry_episode(
            db=db,
            run_id=run_id,
            episode_id=episode_id,
            session_hash=session_hash,
        )
    except LeaseConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except StaleAttemptError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AIQuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API quota exceeded: {e}",
            headers={"Retry-After": "60"},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Retry failed: {e}")


@router.get("/runs/{run_id}/ranking", response_model=ShowWideRankingResponse)
def get_run_show_ranking(
    run_id: str,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
) -> ShowWideRankingResponse:
    """Retrieve show-wide ranked promo candidates across all episodes in the run."""
    try:
        return runs_service.get_show_wide_ranking(db=db, run_id=run_id, session_hash=session_hash)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/runs/{run_id}/export/csv")
def export_run_ranking_csv(
    run_id: str,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
):
    """Export show-wide candidate rankings to CSV (enforces session ownership)."""
    try:
        ranking = runs_service.get_show_wide_ranking(db=db, run_id=run_id, session_hash=session_hash)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Show Rank",
        "Episode Rank",
        "Title",
        "Episode",
        "Filename",
        "Duration (s)",
        "Start Time",
        "End Time",
        "Overall Score",
        "Opening Strength",
        "Opening Hook",
        "Unresolved Ending Score",
        "Cliffhanger Cut",
        "Unresolved Question",
        "Rationale",
        "Review Flags",
    ])

    for c in ranking.candidates:
        writer.writerow([
            c.rank,
            c.rank,
            c.editorial_title,
            c.episode_number or "Unknown",
            c.filename or "Unknown",
            c.segment.duration_seconds,
            c.segment.start_timestamp,
            c.segment.end_timestamp,
            c.rubric.overall_score if c.rubric else "Unavailable",
            c.rubric.opening_strength if c.rubric else "Unavailable",
            c.hook_explanation,
            c.rubric.unresolved_ending if c.rubric else "Unavailable",
            c.cliffhanger_explanation,
            c.unresolved_question,
            c.rationale,
            "; ".join(c.review_flags),
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}_show_ranking.csv"'},
    )


@router.get("/runs/{run_id}/export/json")
def export_run_ranking_json(
    run_id: str,
    session_hash: str = Depends(get_or_create_session_hash),
    db: Session = Depends(require_db),
):
    """Export complete audit JSON for a run (enforces session ownership)."""
    run = runs_service.get_run(db=db, run_id=run_id, session_hash=session_hash)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    return Response(
        content=run.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}_audit.json"'},
    )
