from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.models import Event, Episode


class RawCandidateProposal(BaseModel):
    editorial_title: str = Field(description="Short editorial title summarizing the promo clip")
    start_event_id: str = Field(description="ID of the starting event in the episode")
    end_event_id: str = Field(description="ID of the ending event in the episode")
    hook_explanation: str = Field(description="What happens within the first 3 seconds that hooks the viewer")
    hook_event_ids: List[str] = Field(default_factory=list, description="IDs of events comprising the hook")
    cliffhanger_explanation: str = Field(description="How the segment ends on an unresolved cliffhanger")
    cliffhanger_event_ids: List[str] = Field(default_factory=list, description="IDs of events comprising the cliffhanger")
    unresolved_question: str = Field(description="The specific unresolved question left in the viewer's mind")
    rationale: str = Field(description="One-sentence explanation of why this segment works as a standalone promo")
    standalone_assessment: str = Field(description="Assessment of whether a scrolling viewer understands the scene without prior show knowledge")
    editorial_risks: List[str] = Field(default_factory=list, description="Editorial risks (e.g. unclear relationship, resolved conflict, slow start)")


class CandidateAssessmentItem(BaseModel):
    candidate_index: int = Field(description="1-based index of the candidate being assessed")
    opening_strength: int = Field(ge=1, le=5, description="Hook strength in the first 3 seconds (1-5)")
    standalone_clarity: int = Field(ge=1, le=5, description="Clarity for viewers with zero context (1-5)")
    escalation_stakes: int = Field(ge=1, le=5, description="Dramatic escalation and emotional tension (1-5)")
    unresolved_ending: int = Field(ge=1, le=5, description="Strength of the cliffhanger / cut point (1-5)")
    opening_reason: str
    clarity_reason: str
    stakes_reason: str
    ending_reason: str
    grounded_unresolved_question: str
    uncertainty_or_weakness: Optional[str] = None


class BatchedAssessmentPayload(BaseModel):
    assessments: List[CandidateAssessmentItem]


class EditorialRubricScore(BaseModel):
    opening_strength: int = Field(ge=1, le=5, description="Hook strength in the first 3 seconds (1-5)")
    standalone_clarity: int = Field(ge=1, le=5, description="Clarity for viewers with zero context (1-5)")
    escalation_stakes: int = Field(ge=1, le=5, description="Dramatic escalation and emotional tension (1-5)")
    unresolved_ending: int = Field(ge=1, le=5, description="Strength of the cliffhanger / cut point (1-5)")
    opening_reason: str
    clarity_reason: str
    stakes_reason: str
    ending_reason: str
    grounded_unresolved_question: Optional[str] = None
    uncertainty_or_weakness: Optional[str] = None
    overall_score: float = Field(description="Calculated weighted editorial score (1.0 to 5.0)")


class PromoSegment(BaseModel):
    episode_id: str
    episode_number: Optional[int] = None
    filename: str
    source_content_hash: str
    start_ms: int
    end_ms: int
    start_timestamp: str
    end_timestamp: str
    duration_ms: int
    duration_seconds: float
    event_ids: List[str]
    events: List[Event] = Field(default_factory=list)


class PromoCandidate(BaseModel):
    id: str
    rank: int
    editorial_title: str
    episode_number: Optional[int] = None
    filename: str
    source_content_hash: str
    segment: PromoSegment
    hook_explanation: str
    hook_event_ids: List[str]
    cliffhanger_explanation: str
    cliffhanger_event_ids: List[str]
    unresolved_question: str
    rationale: str
    standalone_assessment: str
    editorial_risks: List[str] = Field(default_factory=list)
    assessment_status: Literal["assessed", "unavailable"] = "assessed"
    rubric: Optional[EditorialRubricScore] = None
    review_flags: List[str] = Field(default_factory=list)
    mechanical_status: Literal["passed", "warning"] = "passed"


class RejectedProposal(BaseModel):
    proposal: RawCandidateProposal
    rejection_reasons: List[str]
    rejection_codes: List[str]


class PromoAnalysisRequest(BaseModel):
    episode: Episode
    max_candidates: int = Field(default=5, ge=1, le=5)
    model_override: Optional[str] = None


class PromoAnalysisResponse(BaseModel):
    episode_id: str
    episode_number: Optional[int] = None
    filename: str
    source_content_hash: str
    parser_version: str
    prompt_version: str
    assessment_prompt_version: Optional[str] = None
    model: str
    analysis_settings: Dict[str, Any] = Field(default_factory=dict)
    cache_key: str
    candidates: List[PromoCandidate] = Field(default_factory=list)
    rejected_proposals: List[RejectedProposal] = Field(default_factory=list)
    suppressed_candidates: List[PromoCandidate] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_generation_response: str
    raw_assessment_response: Optional[str] = None
