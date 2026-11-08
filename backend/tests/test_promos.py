import pytest
from app.schemas.models import Episode, Event, EventCategory, Scene
from app.schemas.promo import (
    CandidateAssessmentItem,
    RawCandidateProposal,
)
from app.services.ai.base import (
    AIMissingCredentialsError,
    AIProvider,
    AIQuotaExceededError,
    AssessmentResult,
    GenerationResult,
)
from app.services.ai.orchestrator import (
    analyze_episode_for_promos,
    compute_analysis_cache_key,
)
from app.services.ai.prompts import (
    ASSESSMENT_PROMPT_VERSION,
    PROMPT_VERSION,
    build_batched_assessment_prompt,
)
from app.services.ai.ranker import (
    WEIGHT_CLARITY,
    WEIGHT_ENDING,
    WEIGHT_OPENING,
    WEIGHT_STAKES,
    compute_temporal_iou,
    compute_weighted_overall_score,
    rank_and_deduplicate_candidates,
)
from app.services.ai.validator import validate_and_resolve_segment


def create_mock_episode() -> Episode:
    """Create a synthetic episode with 6 timestamped events."""
    events = [
        Event(
            id="ep1_e001",
            scene_id="ep1_s01",
            category=EventCategory.CAMERA,
            original_label="**CAMERA:**",
            start_ms=0,
            end_ms=4000,
            text="Establishing shot of the cathedral interior.",
            line_start=10,
            line_end=12,
        ),
        Event(
            id="ep1_e002",
            scene_id="ep1_s01",
            category=EventCategory.DIALOGUE,
            speaker="GERALD",
            delivery_notes="Cold, mocking",
            original_label="**GERALD (Cold, mocking):**",
            start_ms=1000,
            end_ms=5000,
            text='"You were foolish to think I would ever marry you."',
            line_start=14,
            line_end=16,
        ),
        Event(
            id="ep1_e003",
            scene_id="ep1_s01",
            category=EventCategory.ACTION,
            original_label="**ACTION:**",
            start_ms=5000,
            end_ms=10000,
            text="Clarissa steps forward and takes Gerald's arm with a cruel smile.",
            line_start=18,
            line_end=20,
        ),
        Event(
            id="ep1_e004",
            scene_id="ep1_s01",
            category=EventCategory.DIALOGUE,
            speaker="LADY JULIANA",
            delivery_notes="Trembling fury",
            original_label="**LADY JULIANA (Trembling fury):**",
            start_ms=10500,
            end_ms=25000,
            text='"Father, did you permit this dishonor against my mother\'s memory?"',
            line_start=22,
            line_end=25,
        ),
        Event(
            id="ep1_e005",
            scene_id="ep1_s01",
            category=EventCategory.ACTION,
            original_label="**ACTION:**",
            start_ms=25000,
            end_ms=30000,
            text="Her father turns his back without uttering a single word.",
            line_start=27,
            line_end=29,
        ),
        Event(
            id="ep1_e006",
            scene_id="ep1_s01",
            category=EventCategory.DIALOGUE,
            speaker="LADY JULIANA",
            delivery_notes="Steely resolve",
            original_label="**LADY JULIANA (Steely resolve):**",
            start_ms=30000,
            end_ms=34000,
            text='"Then consider this family dead to me."',
            line_start=31,
            line_end=33,
        ),
    ]

    scenes = [
        Scene(
            id="ep1_s01",
            scene_label="SCENE 01",
            heading="INT. CATHEDRAL - DAY",
            start_ms=0,
            end_ms=35000,
            line_start=5,
            line_end=35,
        )
    ]

    return Episode(
        id="ep1_mock",
        episode_number=1,
        filename="ep1.txt",
        logline="Secret family betrayal in high society",
        continuity_notes="Juliana is the disinherited elder daughter",
        duration_ms=35000,
        scenes=scenes,
        events=events,
        warnings=[],
        content_hash="mock_hash_123",
        parser_version="1.0.0",
    )


class MockAIProvider(AIProvider):
    def __init__(
        self,
        proposals=None,
        assessments=None,
        error_to_raise=None,
        assessment_error_to_raise=None,
    ):
        self.proposals = proposals or []
        self.assessments = assessments or []
        self.error_to_raise = error_to_raise
        self.assessment_error_to_raise = assessment_error_to_raise
        self.last_assessment_prompt = None

    def generate_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        if self.error_to_raise:
            raise self.error_to_raise
        return GenerationResult(
            raw_response_text='{"candidates": []}',
            parsed_candidates=self.proposals,
            model_identifier="mock-model",
            prompt_version=PROMPT_VERSION,
            token_usage={"total_tokens": 120},
            latency_ms=250,
        )

    def assess_candidates(self, system_prompt: str, user_prompt: str, model_override=None):
        self.last_assessment_prompt = user_prompt
        if self.assessment_error_to_raise:
            raise self.assessment_error_to_raise
        return AssessmentResult(
            raw_response_text='{"assessments": []}',
            assessments=self.assessments,
            model_identifier="mock-model",
            prompt_version=ASSESSMENT_PROMPT_VERSION,
            token_usage={"total_tokens": 150},
            latency_ms=300,
        )


def test_valid_proposal_resolution():
    ep = create_mock_episode()
    proposal = RawCandidateProposal(
        editorial_title="Altar Betrayal",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Gerald delivers a brutal rejection at the altar.",
        hook_event_ids=["ep1_e001", "ep1_e002"],
        cliffhanger_explanation="Juliana disowns her entire family.",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Where will Juliana go now that her family betrayed her?",
        rationale="High emotional betrayal with clear hero-villain dynamic.",
        standalone_assessment="Completely standalone; betrayal is universally understood.",
        editorial_risks=[],
    )

    segment, flags, rej_codes, rej_reasons = validate_and_resolve_segment(proposal, ep)
    assert segment is not None
    assert len(rej_codes) == 0
    assert segment.start_ms == 0
    assert segment.end_ms == 34000
    assert segment.duration_ms == 34000
    assert len(segment.events) == 6


def test_unknown_event_ids_rejected():
    ep = create_mock_episode()
    proposal = RawCandidateProposal(
        editorial_title="Bad IDs",
        start_event_id="non_existent_start",
        end_event_id="ep1_e006",
        hook_explanation="Fake hook",
        hook_event_ids=["ep1_e001"],
        cliffhanger_explanation="Fake cliffhanger",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Fake question",
        rationale="Rationale",
        standalone_assessment="Assessment",
    )

    segment, flags, rej_codes, rej_reasons = validate_and_resolve_segment(proposal, ep)
    assert segment is None
    assert "INVALID_START_EVENT_ID" in rej_codes


def test_reversed_timestamps_rejected():
    ep = create_mock_episode()
    proposal = RawCandidateProposal(
        editorial_title="Reversed Cut",
        start_event_id="ep1_e006",  # 30000ms
        end_event_id="ep1_e002",    # 5000ms
        hook_explanation="Hook",
        cliffhanger_explanation="Cliffhanger",
        unresolved_question="Question",
        rationale="Rationale",
        standalone_assessment="Assessment",
    )

    segment, flags, rej_codes, rej_reasons = validate_and_resolve_segment(proposal, ep)
    assert segment is None
    assert "REVERSED_OR_ZERO_INTERVAL" in rej_codes


def test_duration_limits():
    ep = create_mock_episode()
    # Too short: ep1_e001 (0-4s) to ep1_e003 (5-10s) -> 10s < 20s
    short_proposal = RawCandidateProposal(
        editorial_title="Too Short",
        start_event_id="ep1_e001",
        end_event_id="ep1_e003",
        hook_explanation="Hook",
        hook_event_ids=["ep1_e001"],
        cliffhanger_explanation="Cliffhanger",
        cliffhanger_event_ids=["ep1_e003"],
        unresolved_question="Question",
        rationale="Rationale",
        standalone_assessment="Assessment",
    )
    segment, _, rej_codes, _ = validate_and_resolve_segment(short_proposal, ep)
    assert segment is None
    assert "DURATION_TOO_SHORT" in rej_codes


def test_cutting_overlapping_dialogue_rejected():
    ep = create_mock_episode()
    ep.events.append(
        Event(
            id="ep1_e_overlap",
            scene_id="ep1_s01",
            category=EventCategory.DIALOGUE,
            speaker="PRIEST",
            original_label="**PRIEST:**",
            start_ms=4000,
            end_ms=6000,
            text='"Do you take this woman?"',
            line_start=17,
            line_end=17,
        )
    )
    cut_dialogue_prop = RawCandidateProposal(
        editorial_title="Cuts Dialogue",
        start_event_id="ep1_e003",  # start_ms = 5000, inside 4000-6000 dialogue!
        end_event_id="ep1_e006",
        hook_explanation="Hook",
        hook_event_ids=["ep1_e003"],
        cliffhanger_explanation="Cliffhanger",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Question",
        rationale="Rationale",
        standalone_assessment="Assessment",
    )
    segment, _, rej_codes, _ = validate_and_resolve_segment(cut_dialogue_prop, ep)
    assert segment is None
    assert "CUTS_DIALOGUE_START" in rej_codes


def test_hook_outside_first_3_seconds():
    ep = create_mock_episode()
    bad_hook_prop = RawCandidateProposal(
        editorial_title="Late Hook",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Hook starts late",
        hook_event_ids=["ep1_e003"],  # 5000ms - 10000ms (outside first 3s)
        cliffhanger_explanation="Cliffhanger",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Question",
        rationale="Rationale",
        standalone_assessment="Assessment",
    )
    segment, _, rej_codes, _ = validate_and_resolve_segment(bad_hook_prop, ep)
    assert segment is None
    assert "HOOK_OUTSIDE_OPENING_3S" in rej_codes


def test_weighted_overall_score_calculation():
    # opening * 0.30 + clarity * 0.25 + stakes * 0.20 + ending * 0.25
    # 4*0.30 + 5*0.25 + 3*0.20 + 4*0.25 = 1.2 + 1.25 + 0.60 + 1.0 = 4.05
    score = compute_weighted_overall_score(opening=4, clarity=5, stakes=3, ending=4)
    assert score == 4.05


def test_two_call_pipeline_with_batched_assessment():
    ep = create_mock_episode()
    prop = RawCandidateProposal(
        editorial_title="Cathedral Betrayal",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Gerald insults bride",
        hook_event_ids=["ep1_e001", "ep1_e002"],
        cliffhanger_explanation="Juliana disowns family",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Draft question",
        rationale="Dramatic high stakes",
        standalone_assessment="Clear",
        editorial_risks=[],
    )

    assessment = CandidateAssessmentItem(
        candidate_index=1,
        opening_strength=4,
        opening_reason="Verbal insult establishes conflict immediately.",
        standalone_clarity=5,
        clarity_reason="The rejection and family betrayal need no outside context.",
        escalation_stakes=4,
        stakes_reason="Public humiliation and family disowning create irreversible stakes.",
        unresolved_ending=4,
        ending_reason="Cut right on Juliana's declaration leaves next action uncertain.",
        grounded_unresolved_question="Where will Juliana go now that her family turned their back on her?",
        uncertainty_or_weakness=None,
    )

    provider = MockAIProvider(proposals=[prop], assessments=[assessment])
    res = analyze_episode_for_promos(ep, provider=provider)

    assert len(res.candidates) == 1
    cand = res.candidates[0]
    assert cand.assessment_status == "assessed"
    assert cand.rubric is not None
    assert cand.rubric.opening_strength == 4
    assert cand.rubric.standalone_clarity == 5
    assert cand.rubric.escalation_stakes == 4
    assert cand.rubric.unresolved_ending == 4
    # Expected weighted: 4*0.3 + 5*0.25 + 4*0.2 + 4*0.25 = 1.2 + 1.25 + 0.8 + 1.0 = 4.25
    assert cand.rubric.overall_score == 4.25
    assert cand.unresolved_question == "Where will Juliana go now that her family turned their back on her?"

    # Verify that the assessment prompt excludes background notes
    assert provider.last_assessment_prompt is not None
    assert "Secret family betrayal in high society" not in provider.last_assessment_prompt
    assert "Juliana is the disinherited elder daughter" not in provider.last_assessment_prompt
    # Verify that the assessment prompt explicitly marks the 3s opening and final cliffhanger cut window
    assert "[0.0s - 3.0s OPENING HOOK WINDOW]" in provider.last_assessment_prompt
    assert "[FINAL" in provider.last_assessment_prompt and "CLIFFHANGER CUT WINDOW]" in provider.last_assessment_prompt


def test_assessment_failure_preserves_candidates_without_invented_heuristics():
    ep = create_mock_episode()
    prop = RawCandidateProposal(
        editorial_title="Valid Cut Without Assessment",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Hook",
        hook_event_ids=["ep1_e001", "ep1_e002"],
        cliffhanger_explanation="Cliffhanger",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="What happens next?",
        rationale="Rationale",
        standalone_assessment="Clear",
        editorial_risks=[],
    )

    # Provider generates proposals, but assessment call fails (e.g. timeout or quota)
    provider = MockAIProvider(
        proposals=[prop],
        assessment_error_to_raise=RuntimeError("Assessment service temporarily unavailable"),
    )

    res = analyze_episode_for_promos(ep, provider=provider)

    # Candidate MUST be preserved for review!
    assert len(res.candidates) == 1
    cand = res.candidates[0]
    assert cand.assessment_status == "unavailable"
    assert cand.rubric is None  # NO fabricated heuristic scores
    assert any("Editorial assessment unavailable" in flag for flag in cand.review_flags)


def test_cache_key_distinguishes_model_prompt_and_source():
    k1 = compute_analysis_cache_key(
        source_hash="hash_a",
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.0.0",
        max_candidates=5,
    )
    k2 = compute_analysis_cache_key(
        source_hash="hash_b",  # different hash
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.0.0",
        max_candidates=5,
    )
    k3 = compute_analysis_cache_key(
        source_hash="hash_a",
        parser_version="1.0.0",
        model="gemini-2.5-flash",  # different model
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.0.0",
        max_candidates=5,
    )
    k4 = compute_analysis_cache_key(
        source_hash="hash_a",
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.3.0",  # different generation prompt version
        assessment_prompt_version="assessment_v1.0.0",
        max_candidates=5,
    )
    k5 = compute_analysis_cache_key(
        source_hash="hash_a",
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.1.0",  # different assessment prompt version
        max_candidates=5,
    )
    k6 = compute_analysis_cache_key(
        source_hash="hash_a",
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.0.0",
        max_candidates=10,  # different settings
    )

    assert k1 != k2
    assert k1 != k3
    assert k1 != k4
    assert k1 != k5
    assert k1 != k6
    assert "hash_a" in k1
    assert "gemini-3.5-flash-lite" in k1
    assert "assessment_v1.0.0" in k1


def test_changing_assessment_prompt_version_changes_cache_key():
    base_key = compute_analysis_cache_key(
        source_hash="ep1_content_hash",
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.0.0",
        max_candidates=5,
    )
    updated_key = compute_analysis_cache_key(
        source_hash="ep1_content_hash",
        parser_version="1.0.0",
        model="gemini-3.5-flash-lite",
        prompt_version="2.2.0",
        assessment_prompt_version="assessment_v1.0.1",
        max_candidates=5,
    )
    assert base_key != updated_key
    assert "assessment_v1.0.0" in base_key
    assert "assessment_v1.0.1" in updated_key


def test_duplicate_suppression_with_iou():
    ep = create_mock_episode()
    prop1 = RawCandidateProposal(
        editorial_title="Promo A",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Hook",
        hook_event_ids=["ep1_e001"],
        cliffhanger_explanation="Ending",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Q1?",
        rationale="Good",
        standalone_assessment="Standalone",
    )
    prop2 = RawCandidateProposal(
        editorial_title="Promo B",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Hook",
        hook_event_ids=["ep1_e001"],
        cliffhanger_explanation="Ending",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Q2?",
        rationale="Good duplicate",
        standalone_assessment="Standalone",
    )

    seg1, _, _, _ = validate_and_resolve_segment(prop1, ep)
    seg2, _, _, _ = validate_and_resolve_segment(prop2, ep)
    assert seg1 is not None and seg2 is not None

    # Assessment gives Promo A higher score than Promo B
    assessments = {
        1: CandidateAssessmentItem(
            candidate_index=1,
            opening_strength=5,
            opening_reason="Great",
            standalone_clarity=5,
            clarity_reason="Clear",
            escalation_stakes=5,
            stakes_reason="High",
            unresolved_ending=5,
            ending_reason="Sharp",
            grounded_unresolved_question="Q1?",
        ),
        2: CandidateAssessmentItem(
            candidate_index=2,
            opening_strength=3,
            opening_reason="Moderate",
            standalone_clarity=3,
            clarity_reason="Moderate",
            escalation_stakes=3,
            stakes_reason="Moderate",
            unresolved_ending=3,
            ending_reason="Moderate",
            grounded_unresolved_question="Q2?",
        ),
    }

    ranked, suppressed = rank_and_deduplicate_candidates(
        proposals_with_segments=[(prop1, seg1, []), (prop2, seg2, [])],
        assessments_by_index=assessments,
        episode=ep,
    )
    assert len(ranked) == 1
    assert ranked[0].editorial_title == "Promo A"
    assert len(suppressed) == 1
    assert suppressed[0].editorial_title == "Promo B"
    assert "Suppressed duplicate" in suppressed[0].review_flags[0]


def test_missing_credentials_and_quota_errors():
    ep = create_mock_episode()
    provider_missing = MockAIProvider(error_to_raise=AIMissingCredentialsError("No key"))
    with pytest.raises(AIMissingCredentialsError):
        analyze_episode_for_promos(ep, provider=provider_missing)

    provider_quota = MockAIProvider(error_to_raise=AIQuotaExceededError("Rate limit 429"))
    with pytest.raises(AIQuotaExceededError):
        analyze_episode_for_promos(ep, provider=provider_quota)


def test_zero_candidates():
    ep = create_mock_episode()
    provider_empty = MockAIProvider(proposals=[])
    res = analyze_episode_for_promos(ep, provider=provider_empty)
    assert len(res.candidates) == 0
    assert len(res.rejected_proposals) == 0
    assert res.metadata["total_proposals_generated"] == 0


def test_response_preserves_episode_identity():
    ep = create_mock_episode()
    prop = RawCandidateProposal(
        editorial_title="Identity Test",
        start_event_id="ep1_e001",
        end_event_id="ep1_e006",
        hook_explanation="Hook",
        hook_event_ids=["ep1_e001", "ep1_e002"],
        cliffhanger_explanation="Cliffhanger",
        cliffhanger_event_ids=["ep1_e006"],
        unresolved_question="Question?",
        rationale="Rationale",
        standalone_assessment="Assessment",
    )
    provider = MockAIProvider(proposals=[prop])
    res = analyze_episode_for_promos(ep, provider=provider)

    assert res.episode_id == ep.id
    assert res.episode_number == 1
    assert res.filename == "ep1.txt"
    assert res.source_content_hash == "mock_hash_123"

    assert len(res.candidates) == 1
    cand = res.candidates[0]
    assert cand.episode_number == 1
    assert cand.filename == "ep1.txt"
    assert cand.source_content_hash == "mock_hash_123"
    assert cand.segment.filename == "ep1.txt"
    assert cand.segment.source_content_hash == "mock_hash_123"
