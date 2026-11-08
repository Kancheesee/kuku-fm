from typing import List, Optional, Set, Tuple
from app.schemas.models import Episode, Event, EventCategory
from app.schemas.promo import PromoSegment, RawCandidateProposal, RejectedProposal
from app.services.timestamp import format_ms_to_timestamp

MIN_DURATION_MS = 20000  # 20 seconds
MAX_DURATION_MS = 60000  # 60 seconds
HOOK_WINDOW_MS = 3000    # Opening 3 seconds
CLIFFHANGER_WINDOW_MS = 6000  # Last 6 seconds before cut


def validate_and_resolve_segment(
    proposal: RawCandidateProposal,
    episode: Episode,
) -> Tuple[Optional[PromoSegment], List[str], List[str], List[str]]:
    """Resolve boundary events and validate timeline rules.

    Returns:
        (resolved_segment, review_flags, rejection_codes, rejection_reasons)
        If rejected, resolved_segment is None and rejection_reasons is populated.
    """
    rejection_codes: List[str] = []
    rejection_reasons: List[str] = []
    review_flags: List[str] = []

    # 1. Check event ID existence
    events_by_id = {e.id: e for e in episode.events}

    start_event = events_by_id.get(proposal.start_event_id)
    if not start_event:
        rejection_codes.append("INVALID_START_EVENT_ID")
        rejection_reasons.append(f"Referenced start_event_id '{proposal.start_event_id}' does not exist in this episode.")

    end_event = events_by_id.get(proposal.end_event_id)
    if not end_event:
        rejection_codes.append("INVALID_END_EVENT_ID")
        rejection_reasons.append(f"Referenced end_event_id '{proposal.end_event_id}' does not exist in this episode.")

    if not start_event or not end_event:
        return None, review_flags, rejection_codes, rejection_reasons

    # 2. Extract boundaries
    start_ms = start_event.start_ms
    end_ms = end_event.end_ms

    if start_ms >= end_ms:
        rejection_codes.append("REVERSED_OR_ZERO_INTERVAL")
        rejection_reasons.append(
            f"Segment start ({format_ms_to_timestamp(start_ms)}) is not strictly before end ({format_ms_to_timestamp(end_ms)})."
        )
        return None, review_flags, rejection_codes, rejection_reasons

    duration_ms = end_ms - start_ms

    # 3. Duration constraints: 20s to 60s
    if duration_ms < MIN_DURATION_MS:
        rejection_codes.append("DURATION_TOO_SHORT")
        rejection_reasons.append(
            f"Duration {duration_ms / 1000:.2f}s is below the 20.0s microdrama minimum."
        )

    if duration_ms > MAX_DURATION_MS:
        rejection_codes.append("DURATION_TOO_LONG")
        rejection_reasons.append(
            f"Duration {duration_ms / 1000:.2f}s exceeds the 60.0s platform maximum."
        )

    # 4. Check all overlapping events inside [start_ms, end_ms]
    overlapping_events: List[Event] = []
    for ev in episode.events:
        # Event overlaps if ev.start_ms < end_ms and ev.end_ms > start_ms
        if ev.start_ms < end_ms and ev.end_ms > start_ms:
            overlapping_events.append(ev)

    # 5. Check dialogue cut integrity (do not cut mid-dialogue)
    for ev in episode.events:
        if ev.category == EventCategory.DIALOGUE:
            # Check if start cut splits an ongoing dialogue line
            if ev.start_ms < start_ms < ev.end_ms:
                rejection_codes.append("CUTS_DIALOGUE_START")
                rejection_reasons.append(
                    f"Promo starts at {format_ms_to_timestamp(start_ms)}, cutting inside dialogue by {ev.speaker or 'Speaker'} [{format_ms_to_timestamp(ev.start_ms)} - {format_ms_to_timestamp(ev.end_ms)}]."
                )
            # Check if end cut splits an ongoing dialogue line
            if ev.start_ms < end_ms < ev.end_ms:
                rejection_codes.append("CUTS_DIALOGUE_END")
                rejection_reasons.append(
                    f"Promo cuts at {format_ms_to_timestamp(end_ms)}, cutting mid-sentence through dialogue by {ev.speaker or 'Speaker'} [{format_ms_to_timestamp(ev.start_ms)} - {format_ms_to_timestamp(ev.end_ms)}]."
                )

    # 6. Hook evidence validation: must intersect opening 3 seconds [start_ms, start_ms + 3000]
    hook_window_end = start_ms + HOOK_WINDOW_MS
    hook_events = [events_by_id[eid] for eid in proposal.hook_event_ids if eid in events_by_id]

    if not proposal.hook_event_ids:
        review_flags.append("NO_EXPLICIT_HOOK_EVENT_IDS")
    else:
        # Check that at least one hook event intersects the first 3 seconds
        intersects_hook = any(
            h.start_ms < hook_window_end and h.end_ms > start_ms
            for h in hook_events
        )
        if not intersects_hook:
            rejection_codes.append("HOOK_OUTSIDE_OPENING_3S")
            rejection_reasons.append(
                f"Referenced hook events {proposal.hook_event_ids} do not intersect the opening 3-second window [{format_ms_to_timestamp(start_ms)} - {format_ms_to_timestamp(hook_window_end)}]."
            )

    # 7. Cliffhanger evidence validation: must occur near ending
    cliff_window_start = max(start_ms, end_ms - CLIFFHANGER_WINDOW_MS)
    cliff_events = [events_by_id[eid] for eid in proposal.cliffhanger_event_ids if eid in events_by_id]

    if not proposal.cliffhanger_event_ids:
        review_flags.append("NO_EXPLICIT_CLIFFHANGER_EVENT_IDS")
    else:
        intersects_cliff = any(
            c.start_ms < end_ms and c.end_ms > cliff_window_start
            for c in cliff_events
        )
        if not intersects_cliff:
            rejection_codes.append("CLIFFHANGER_OUTSIDE_ENDING_WINDOW")
            rejection_reasons.append(
                f"Referenced cliffhanger events {proposal.cliffhanger_event_ids} do not occur within {CLIFFHANGER_WINDOW_MS / 1000:.1f}s of the ending cut."
            )

    # 8. Propagate source warnings from overlapping events/scenes as review flags
    for ev in overlapping_events:
        for w in episode.warnings:
            if w.line and ev.line_start <= w.line <= ev.line_end:
                flag = f"Source {w.severity.value}: {w.code} on {ev.original_label} (L{w.line})"
                if flag not in review_flags:
                    review_flags.append(flag)

    # If any rejection codes triggered, reject
    if rejection_codes:
        return None, review_flags, rejection_codes, rejection_reasons

    # Construct resolved segment
    segment = PromoSegment(
        episode_id=episode.id,
        episode_number=episode.episode_number,
        filename=episode.filename,
        source_content_hash=episode.content_hash,
        start_ms=start_ms,
        end_ms=end_ms,
        start_timestamp=format_ms_to_timestamp(start_ms),
        end_timestamp=format_ms_to_timestamp(end_ms),
        duration_ms=duration_ms,
        duration_seconds=round(duration_ms / 1000.0, 2),
        event_ids=[e.id for e in overlapping_events],
        events=overlapping_events,
    )

    return segment, review_flags, [], []

