from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.promo import PromoAnalysisResponse, PromoCandidate


class RunSummaryResponse(BaseModel):
    id: str
    name: str
    status: str
    browser_session_id: Optional[str] = None  # legacy identifier
    session_hash: Optional[str] = None
    created_at: str
    updated_at: str
    total_episodes: int = 0
    completed_episodes: int = 0
    failed_episodes: int = 0
    promos_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EpisodeRecordResponse(BaseModel):
    id: str
    run_id: str
    internal_id: str
    episode_number: Optional[int] = None
    filename: str
    content_hash: str
    duration_ms: int
    analysis_status: str  # pending, analyzing, completed, failed, paused
    analysis_result: Optional[PromoAnalysisResponse] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    lease_token: Optional[str] = None
    lease_expires_at: Optional[str] = None
    attempt_number: int = 0
    scenes_count: int = 0
    events_count: int = 0
    warnings_count: int = 0


class RunDetailResponse(BaseModel):
    id: str
    name: str
    status: str  # created, ready, running, paused, completed, failed
    browser_session_id: Optional[str] = None  # legacy identifier
    session_hash: Optional[str] = None
    created_at: str
    updated_at: str
    total_episodes: int
    completed_episodes: int
    failed_episodes: int
    is_provisional: bool = False
    coverage_percentage: float = 0.0
    episodes: List[EpisodeRecordResponse] = Field(default_factory=list)
    show_ranking: List[PromoCandidate] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ShowWideRankingResponse(BaseModel):
    run_id: str
    run_name: str
    total_candidates: int
    is_provisional: bool = False
    completed_episodes: int = 0
    total_episodes: int = 0
    coverage_percentage: float = 0.0
    unassessed_candidates_count: int = 0
    candidates: List[PromoCandidate] = Field(default_factory=list)


class CreateRunFromPreviewRequest(BaseModel):
    name: Optional[str] = None
    episodes: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)
