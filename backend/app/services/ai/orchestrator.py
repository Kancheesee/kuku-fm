import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.models import Episode
from app.schemas.promo import (
    CandidateAssessmentItem,
    PromoAnalysisResponse,
    PromoCandidate,
    PromoSegment,
    RawCandidateProposal,
    RejectedProposal,
)
from app.services.ai.base import AIProvider, AIQuotaExceededError
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.prompts import (
    ASSESSMENT_PROMPT_VERSION,
    ASSESSMENT_SYSTEM_INSTRUCTION,
    GENERATION_SYSTEM_INSTRUCTION,
    PROMPT_VERSION,
    build_batched_assessment_prompt,
    build_promo_generation_prompt,
)
from app.services.ai.ranker import rank_and_deduplicate_candidates
from app.services.ai.validator import validate_and_resolve_segment

logger = logging.getLogger(__name__)

# Overall pipeline deadline budget: enforce safety margin before Vercel function timeout (120s)
PIPELINE_DEADLINE_SECONDS = 90.0
ASSESSMENT_MIN_BUDGET_SECONDS = 30.0


def compute_analysis_cache_key(
    source_hash: str,
    parser_version: str,
    model: str,
    prompt_version: str,
    assessment_prompt_version: str,
    max_candidates: int,
) -> str:
    """Compute deterministic canonical configuration fingerprint incorporating source identity, parser, model, both prompt versions, and analysis settings."""
    return f"{source_hash}__{parser_version}__{model}__p{prompt_version}__a{assessment_prompt_version}__c{max_candidates}"


def analyze_episode_for_promos(
    episode: Episode,
    provider: Optional[AIProvider] = None,
    max_candidates: int = 5,
    model_override: Optional[str] = None,
) -> PromoAnalysisResponse:
    """Analyze a single validated episode for continuous promo candidates.

    Flow:
    1. Call 1: Generate proposals from screenplay events.
    2. Deterministic mechanical cut validation in code.
    3. Call 2 (at most 1 batched call): Genuine model assessment of resolved footage.
       (If assessment fails, candidates are preserved with status 'unavailable').
    4. Code ranking, score weighting, and deduplication.
    """
    if provider is None:
        provider = GeminiProvider()

    pipeline_start = time.time()

    # Step 1: Candidate Generation
    generation_prompt = build_promo_generation_prompt(episode, max_candidates=max_candidates)

    gen_result = provider.generate_candidates(
        system_prompt=GENERATION_SYSTEM_INSTRUCTION,
        user_prompt=generation_prompt,
        model_override=model_override,
    )

    valid_proposals_with_segments: List[Tuple[RawCandidateProposal, PromoSegment, List[str]]] = []
    rejected_proposals: List[RejectedProposal] = []

    # Step 2: Mechanical validation in code
    for proposal in gen_result.parsed_candidates:
        segment, review_flags, rejection_codes, rejection_reasons = validate_and_resolve_segment(
            proposal=proposal,
            episode=episode,
        )

        if segment is None or rejection_codes:
            rejected_proposals.append(
                RejectedProposal(
                    proposal=proposal,
                    rejection_reasons=rejection_reasons,
                    rejection_codes=rejection_codes,
                )
            )
        else:
            valid_proposals_with_segments.append((proposal, segment, review_flags))

    # Step 3: Batched Model Assessment (at most 1 call per episode)
    assessments_by_index: Optional[Dict[int, CandidateAssessmentItem]] = None
    raw_assessment_response: Optional[str] = None
    assessment_latency_ms = 0
    assessment_tokens: Dict[str, Any] = {}
    assessment_error_msg: Optional[str] = None

    if valid_proposals_with_segments:
        elapsed = time.time() - pipeline_start
        remaining_budget = PIPELINE_DEADLINE_SECONDS - elapsed

        if remaining_budget < ASSESSMENT_MIN_BUDGET_SECONDS:
            logger.warning(
                f"Skipping Call 2 assessment: elapsed={elapsed:.1f}s, remaining={remaining_budget:.1f}s "
                f"below safety margin ({ASSESSMENT_MIN_BUDGET_SECONDS}s) of {PIPELINE_DEADLINE_SECONDS}s deadline."
            )
            assessment_error_msg = (
                f"Assessment skipped: pipeline deadline threshold reached ({elapsed:.1f}s elapsed) "
                f"to guarantee completion within Vercel function timeout."
            )
            assessments_by_index = None
        else:
            assessment_items = [
                (idx, prop, seg)
                for idx, (prop, seg, _) in enumerate(valid_proposals_with_segments, start=1)
            ]
            assessment_prompt = build_batched_assessment_prompt(assessment_items)

            try:
                assess_result = provider.assess_candidates(
                    system_prompt=ASSESSMENT_SYSTEM_INSTRUCTION,
                    user_prompt=assessment_prompt,
                    model_override=model_override,
                )
                raw_assessment_response = assess_result.raw_response_text
                assessment_latency_ms = assess_result.latency_ms
                assessment_tokens = assess_result.token_usage
                assessments_by_index = {a.candidate_index: a for a in assess_result.assessments}
            except AIQuotaExceededError as qe:
                logger.warning(f"Assessment quota exceeded: {qe}. Persisting generated candidates before pausing.")
                # Build partial response with unassessed valid candidates so they are saved to DB
                ranked_cands, supp_cands = rank_and_deduplicate_candidates(
                    proposals_with_segments=valid_proposals_with_segments,
                    assessments_by_index=None,
                    episode=episode,
                )
                target_model = gen_result.model_identifier
                cache_key = compute_analysis_cache_key(
                    source_hash=episode.content_hash,
                    parser_version=episode.parser_version,
                    model=target_model,
                    prompt_version=PROMPT_VERSION,
                    assessment_prompt_version=ASSESSMENT_PROMPT_VERSION,
                    max_candidates=max_candidates,
                )
                partial_meta = {
                    "provider": "google-gemini",
                    "model": target_model,
                    "prompt_version": PROMPT_VERSION,
                    "assessment_prompt_version": None,
                    "source_content_hash": episode.content_hash,
                    "parser_version": episode.parser_version,
                    "api_calls_attempted": 2,
                    "api_calls_completed": 1,
                    "assessment_status": "unavailable",
                    "generation_latency_ms": gen_result.latency_ms,
                    "assessment_latency_ms": 0,
                    "total_latency_ms": gen_result.latency_ms,
                    "generation_tokens": gen_result.token_usage,
                    "assessment_tokens": {},
                    "assessment_error": f"Quota exhausted during assessment: {qe}",
                    "total_proposals_generated": len(gen_result.parsed_candidates),
                    "valid_proposals_count": len(valid_proposals_with_segments),
                    "rejected_proposals_count": len(rejected_proposals),
                    "suppressed_duplicates_count": len(supp_cands),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                partial_res = PromoAnalysisResponse(
                    episode_id=episode.id,
                    episode_number=episode.episode_number,
                    filename=episode.filename,
                    source_content_hash=episode.content_hash,
                    parser_version=episode.parser_version,
                    prompt_version=PROMPT_VERSION,
                    assessment_prompt_version=None,
                    model=target_model,
                    analysis_settings={"max_candidates": max_candidates},
                    cache_key=cache_key,
                    candidates=ranked_cands,
                    rejected_proposals=rejected_proposals,
                    suppressed_candidates=supp_cands,
                    metadata=partial_meta,
                    raw_generation_response=gen_result.raw_response_text,
                    raw_assessment_response=None,
                )
                raise AIQuotaExceededError(str(qe), partial_result=partial_res) from qe
            except Exception as exc:
                logger.warning(f"Batched assessment call failed: {exc}. Preserving mechanically valid candidates.")
                assessment_error_msg = str(exc)
                assessments_by_index = None

    # Step 4: Rank and deduplicate
    ranked_candidates, suppressed_candidates = rank_and_deduplicate_candidates(
        proposals_with_segments=valid_proposals_with_segments,
        assessments_by_index=assessments_by_index,
        episode=episode,
    )

    target_model = gen_result.model_identifier
    cache_key = compute_analysis_cache_key(
        source_hash=episode.content_hash,
        parser_version=episode.parser_version,
        model=target_model,
        prompt_version=PROMPT_VERSION,
        assessment_prompt_version=ASSESSMENT_PROMPT_VERSION,
        max_candidates=max_candidates,
    )

    metadata = {
        "provider": "google-gemini",
        "model": target_model,
        "prompt_version": PROMPT_VERSION,
        "assessment_prompt_version": ASSESSMENT_PROMPT_VERSION if assessments_by_index else None,
        "source_content_hash": episode.content_hash,
        "parser_version": episode.parser_version,
        "api_calls_attempted": 2 if valid_proposals_with_segments else 1,
        "api_calls_completed": 2 if assessments_by_index else 1,
        "assessment_status": "assessed" if assessments_by_index else "unavailable",
        "generation_latency_ms": gen_result.latency_ms,
        "assessment_latency_ms": assessment_latency_ms,
        "total_latency_ms": gen_result.latency_ms + assessment_latency_ms,
        "generation_tokens": gen_result.token_usage,
        "assessment_tokens": assessment_tokens,
        "assessment_error": assessment_error_msg,
        "total_proposals_generated": len(gen_result.parsed_candidates),
        "valid_proposals_count": len(valid_proposals_with_segments),
        "rejected_proposals_count": len(rejected_proposals),
        "suppressed_duplicates_count": len(suppressed_candidates),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return PromoAnalysisResponse(
        episode_id=episode.id,
        episode_number=episode.episode_number,
        filename=episode.filename,
        source_content_hash=episode.content_hash,
        parser_version=episode.parser_version,
        prompt_version=PROMPT_VERSION,
        assessment_prompt_version=ASSESSMENT_PROMPT_VERSION if assessments_by_index else None,
        model=target_model,
        analysis_settings={"max_candidates": max_candidates},
        cache_key=cache_key,
        candidates=ranked_candidates,
        rejected_proposals=rejected_proposals,
        suppressed_candidates=suppressed_candidates,
        metadata=metadata,
        raw_generation_response=gen_result.raw_response_text,
        raw_assessment_response=raw_assessment_response,
    )


def assess_existing_candidates(
    episode: Episode,
    existing_response: PromoAnalysisResponse,
    provider: Optional[AIProvider] = None,
    model_override: Optional[str] = None,
) -> PromoAnalysisResponse:
    """
    Resume batched assessment for an episode that already has mechanically valid
    candidates persisted from a prior generation step (e.g. following quota exhaustion).
    Avoids redundant generation API calls, conserving quota and latency.
    """
    if provider is None:
        provider = GeminiProvider()

    if not existing_response.candidates:
        return analyze_episode_for_promos(
            episode=episode,
            provider=provider,
            model_override=model_override,
        )

    # Reconstruct assessment proposals from existing valid candidates
    assessment_items = []
    for idx, cand in enumerate(existing_response.candidates, start=1):
        raw_prop = RawCandidateProposal(
            editorial_title=cand.editorial_title,
            start_event_id=cand.segment.event_ids[0] if cand.segment.event_ids else "",
            end_event_id=cand.segment.event_ids[-1] if cand.segment.event_ids else "",
            hook_explanation=cand.hook_explanation,
            hook_event_ids=cand.hook_event_ids,
            cliffhanger_explanation=cand.cliffhanger_explanation,
            cliffhanger_event_ids=cand.cliffhanger_event_ids,
            unresolved_question=cand.unresolved_question,
            rationale=cand.rationale,
            standalone_assessment=cand.standalone_assessment,
            editorial_risks=cand.editorial_risks,
        )
        assessment_items.append((idx, raw_prop, cand.segment))

    assessment_prompt = build_batched_assessment_prompt(assessment_items)
    target_model = model_override or existing_response.model or "gemini-3.5-flash-lite"

    try:
        assess_result = provider.assess_candidates(
            system_prompt=ASSESSMENT_SYSTEM_INSTRUCTION,
            user_prompt=assessment_prompt,
            model_override=target_model,
        )
        assessments_by_index = {a.candidate_index: a for a in assess_result.assessments}
        raw_assessment_response = assess_result.raw_response_text
        assessment_latency_ms = assess_result.latency_ms
        assessment_tokens = assess_result.token_usage
        assessment_error_msg = None
    except AIQuotaExceededError as qe:
        raise AIQuotaExceededError(str(qe), partial_result=existing_response) from qe
    except Exception as exc:
        logger.warning(f"Resumed assessment call failed: {exc}.")
        assessment_error_msg = str(exc)
        assessments_by_index = None
        raw_assessment_response = None
        assessment_latency_ms = 0
        assessment_tokens = {}

    proposals_with_segments = [
        (
            item[1],
            item[2],
            existing_response.candidates[item[0] - 1].review_flags,
        )
        for item in assessment_items
    ]

    ranked_candidates, suppressed_candidates = rank_and_deduplicate_candidates(
        proposals_with_segments=proposals_with_segments,
        assessments_by_index=assessments_by_index,
        episode=episode,
    )

    meta = dict(existing_response.metadata)
    meta["assessment_status"] = "assessed" if assessments_by_index else "unavailable"
    meta["assessment_prompt_version"] = ASSESSMENT_PROMPT_VERSION if assessments_by_index else None
    meta["api_calls_completed"] = 2 if assessments_by_index else 1
    meta["assessment_latency_ms"] = assessment_latency_ms
    meta["total_latency_ms"] = meta.get("generation_latency_ms", 0) + assessment_latency_ms
    meta["assessment_tokens"] = assessment_tokens
    meta["assessment_error"] = assessment_error_msg

    cache_key = compute_analysis_cache_key(
        source_hash=episode.content_hash,
        parser_version=episode.parser_version,
        model=target_model,
        prompt_version=PROMPT_VERSION,
        assessment_prompt_version=ASSESSMENT_PROMPT_VERSION,
        max_candidates=len(ranked_candidates),
    )

    return PromoAnalysisResponse(
        episode_id=episode.id,
        episode_number=episode.episode_number,
        filename=episode.filename,
        source_content_hash=episode.content_hash,
        parser_version=episode.parser_version,
        prompt_version=PROMPT_VERSION,
        assessment_prompt_version=ASSESSMENT_PROMPT_VERSION if assessments_by_index else None,
        model=target_model,
        analysis_settings=existing_response.analysis_settings,
        cache_key=cache_key,
        candidates=ranked_candidates,
        rejected_proposals=existing_response.rejected_proposals,
        suppressed_candidates=suppressed_candidates,
        metadata=meta,
        raw_generation_response=existing_response.raw_generation_response,
        raw_assessment_response=raw_assessment_response,
    )
