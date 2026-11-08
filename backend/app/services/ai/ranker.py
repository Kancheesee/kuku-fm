import uuid
from typing import Dict, List, Optional, Tuple
from app.schemas.models import Episode
from app.schemas.promo import (
    CandidateAssessmentItem,
    EditorialRubricScore,
    PromoCandidate,
    PromoSegment,
    RawCandidateProposal,
)

# Documented rubric weights for editorial ranking
WEIGHT_OPENING = 0.30
WEIGHT_CLARITY = 0.25
WEIGHT_STAKES = 0.20
WEIGHT_ENDING = 0.25

IOU_DUPLICATE_THRESHOLD = 0.60


def compute_weighted_overall_score(
    opening: int,
    clarity: int,
    stakes: int,
    ending: int,
) -> float:
    """Compute weighted editorial overall score (1.0 to 5.0) in code."""
    val = (
        WEIGHT_OPENING * opening
        + WEIGHT_CLARITY * clarity
        + WEIGHT_STAKES * stakes
        + WEIGHT_ENDING * ending
    )
    return round(val, 2)


def compute_temporal_iou(s1: PromoSegment, s2: PromoSegment) -> float:
    """Compute Intersection-over-Union (IoU) of two promo time intervals."""
    intersection_start = max(s1.start_ms, s2.start_ms)
    intersection_end = min(s1.end_ms, s2.end_ms)
    intersection = max(0, intersection_end - intersection_start)

    union = (s1.end_ms - s1.start_ms) + (s2.end_ms - s2.start_ms) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def rank_and_deduplicate_candidates(
    proposals_with_segments: List[Tuple[RawCandidateProposal, PromoSegment, List[str]]],
    assessments_by_index: Optional[Dict[int, CandidateAssessmentItem]],
    episode: Episode,
) -> Tuple[List[PromoCandidate], List[PromoCandidate]]:
    """Rank and deduplicate mechanically valid candidates using genuine model assessments.

    If model assessments are unavailable, candidates are preserved with
    assessment_status='unavailable' and no fabricated scores are generated.

    Returns:
        (ranked_candidates, suppressed_duplicates)
    """
    scored_candidates: List[PromoCandidate] = []

    for idx, (proposal, segment, mechanical_flags) in enumerate(proposals_with_segments, start=1):
        assessment = assessments_by_index.get(idx) if assessments_by_index else None
        review_flags = list(mechanical_flags)

        if assessment is not None:
            overall = compute_weighted_overall_score(
                opening=assessment.opening_strength,
                clarity=assessment.standalone_clarity,
                stakes=assessment.escalation_stakes,
                ending=assessment.unresolved_ending,
            )
            rubric = EditorialRubricScore(
                opening_strength=assessment.opening_strength,
                standalone_clarity=assessment.standalone_clarity,
                escalation_stakes=assessment.escalation_stakes,
                unresolved_ending=assessment.unresolved_ending,
                opening_reason=assessment.opening_reason,
                clarity_reason=assessment.clarity_reason,
                stakes_reason=assessment.stakes_reason,
                ending_reason=assessment.ending_reason,
                grounded_unresolved_question=assessment.grounded_unresolved_question,
                uncertainty_or_weakness=assessment.uncertainty_or_weakness,
                overall_score=overall,
            )
            assessment_status = "assessed"
            if assessment.uncertainty_or_weakness:
                review_flags.append(f"Editorial note: {assessment.uncertainty_or_weakness}")
        else:
            # Assessment failed or unavailable: DO NOT fabricate authoritative-looking heuristic scores
            rubric = None
            assessment_status = "unavailable"
            review_flags.append("Editorial assessment unavailable - displaying mechanically valid candidate for review")

        candidate = PromoCandidate(
            id=f"promo_{uuid.uuid4().hex[:8]}",
            rank=0,  # Assigned after sorting
            editorial_title=proposal.editorial_title,
            episode_number=episode.episode_number,
            filename=episode.filename,
            source_content_hash=episode.content_hash,
            segment=segment,
            hook_explanation=proposal.hook_explanation,
            hook_event_ids=proposal.hook_event_ids,
            cliffhanger_explanation=proposal.cliffhanger_explanation,
            cliffhanger_event_ids=proposal.cliffhanger_event_ids,
            unresolved_question=(
                assessment.grounded_unresolved_question
                if assessment and assessment.grounded_unresolved_question
                else proposal.unresolved_question
            ),
            rationale=proposal.rationale,
            standalone_assessment=proposal.standalone_assessment,
            editorial_risks=proposal.editorial_risks,
            assessment_status=assessment_status,
            rubric=rubric,
            review_flags=review_flags,
            mechanical_status="warning" if review_flags else "passed",
        )
        scored_candidates.append(candidate)

    # Sort descending by overall score (if assessed), or keep order
    scored_candidates.sort(
        key=lambda c: (c.rubric.overall_score if c.rubric else 0.0, c.segment.duration_ms),
        reverse=True,
    )

    ranked: List[PromoCandidate] = []
    suppressed: List[PromoCandidate] = []

    for candidate in scored_candidates:
        is_duplicate = False
        for accepted in ranked:
            iou = compute_temporal_iou(candidate.segment, accepted.segment)
            if iou >= IOU_DUPLICATE_THRESHOLD:
                is_duplicate = True
                candidate.review_flags.append(
                    f"Suppressed duplicate: overlaps {iou * 100:.0f}% with '{accepted.editorial_title}'."
                )
                suppressed.append(candidate)
                break

        if not is_duplicate:
            ranked.append(candidate)

    # Assign sequential ranks to surviving candidates
    for i, candidate in enumerate(ranked):
        candidate.rank = i + 1

    return ranked, suppressed
