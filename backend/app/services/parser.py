import hashlib
import re
from typing import List, Optional, Tuple

from app.schemas.models import (
    Episode,
    Event,
    EventCategory,
    IssueSeverity,
    ParsingIssue,
    Scene,
)
from app.services.timestamp import (
    extract_event_timing,
    format_ms_to_timestamp,
    parse_timestamp_to_ms,
)

PARSER_VERSION = "1.0.0"

# Category recognition
KNOWN_CAMERA = {"CAMERA", "SHOT", "ANGLE", "WIDE SHOT", "CLOSE-UP", "TRACKING"}
KNOWN_ACTION = {"ACTION"}
KNOWN_SOUND = {"SOUND EFFECT", "SOUND EFFECTS", "SOUND FX", "SFX", "AUDIO", "MUSIC", "FOLEY", "SCORE"}
TECHNICAL_NON_DIALOGUE = {"EFFECT", "VFX", "CGI", "LIGHTING", "TRANSITION", "UNKNOWN", "DIRECTOR", "NOTE", "PROPS"}

EVENT_LABEL_REGEX = re.compile(r"^\*{2}(.*?)\*{2}:?$")
SPEAKER_NOTES_REGEX = re.compile(r"^([^(]+?)(?:\s*\((.*?)\))?$")
SCENE_HEADER_REGEX = re.compile(r"^SCENE\s+(\d+|[A-Z0-9_-]+)", re.IGNORECASE)


def determine_category_and_speaker(
    raw_label: str,
) -> Tuple[EventCategory, Optional[str], Optional[str]]:
    """Determine event category, speaker name, and delivery notes from cleaned label text."""
    clean_label = raw_label.strip()
    upper = clean_label.upper()

    if upper in KNOWN_CAMERA:
        return EventCategory.CAMERA, None, None
    if upper in KNOWN_ACTION:
        return EventCategory.ACTION, None, None
    if upper in KNOWN_SOUND or any(upper.startswith(s) for s in ("SOUND FX", "SOUND EFFECT", "SFX:")):
        return EventCategory.SOUND_EFFECT, None, None

    # Check if this has technical cue indicators (like EFFECT, VFX, etc.) or underscores
    if "_" in upper or any(w in upper.split() for w in TECHNICAL_NON_DIALOGUE) or any(t in upper for t in ("EFFECT", "CGI", "VFX")):
        return EventCategory.UNKNOWN, None, None

    # Check dialogue with potential delivery notes: e.g. "PRUDENCE (Solemn)" or "ALEXANDER"
    match = SPEAKER_NOTES_REGEX.match(clean_label)
    if match:
        speaker = match.group(1).strip()
        notes = match.group(2).strip() if match.group(2) else None
        # Heuristic: If it looks like normal dialogue speaker
        if speaker and not any(k in speaker.upper() for k in ["SCENE", "---", "EPISODE"]):
            return EventCategory.DIALOGUE, speaker, notes

    return EventCategory.UNKNOWN, None, None


def parse_script_content(
    content_bytes: bytes,
    filename: str = "untitled.txt",
) -> Tuple[Optional[Episode], List[ParsingIssue]]:
    """Parse a microdrama screenplay from raw bytes into an Episode model and parsing issues.

    Pure function with no database or external API dependencies.
    """
    issues: List[ParsingIssue] = []

    # 1. Encodings & BOM check
    if content_bytes.startswith(b"\xef\xbb\xbf"):
        try:
            text = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.ERROR,
                    code="UNSUPPORTED_ENCODING",
                    message=f"File has UTF-8 BOM but failed decoding: {exc}",
                )
            )
            return None, issues
    else:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                # Fallback check to report unsupported encoding clearly
                text = content_bytes.decode("cp1252")
                issues.append(
                    ParsingIssue(
                        severity=IssueSeverity.WARNING,
                        code="NON_UTF8_ENCODING",
                        message="File is encoded in Windows CP1252 rather than UTF-8. Converted cleanly.",
                    )
                )
            except Exception as exc:
                issues.append(
                    ParsingIssue(
                        severity=IssueSeverity.ERROR,
                        code="UNSUPPORTED_ENCODING",
                        message=f"File contains unsupported binary or non-UTF-8 characters: {exc}",
                    )
                )
                return None, issues

    content_hash = hashlib.sha256(content_bytes).hexdigest()
    # Generate stable deterministic episode ID
    ep_id = hashlib.sha256(f"{content_hash}_{PARSER_VERSION}".encode("utf-8")).hexdigest()[:16]

    # Normalize line endings: handle CRLF or LF transparently
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    episode_number: Optional[int] = None
    logline: Optional[str] = None
    continuity_notes: Optional[str] = None

    scenes: List[Scene] = []
    events: List[Event] = []

    # Try extracting episode number from filename first as fallback
    num_match = re.search(r"episode[-_\s]*(\d+)", filename, re.IGNORECASE)
    if num_match:
        try:
            episode_number = int(num_match.group(1))
        except ValueError:
            pass

    line_idx = 0
    total_lines = len(lines)

    # State machine for parsing
    current_scene_idx = 0
    current_scene_id = ""
    current_scene_label = ""
    current_scene_heading = ""
    current_scene_start_ms: Optional[int] = None
    current_scene_end_ms: Optional[int] = None
    current_scene_line_start = 0

    def finalize_current_scene(end_line: int):
        nonlocal current_scene_id, current_scene_start_ms, current_scene_end_ms
        if current_scene_id and current_scene_start_ms is not None and current_scene_end_ms is not None:
            scenes.append(
                Scene(
                    id=current_scene_id,
                    scene_label=current_scene_label or f"SCENE {current_scene_idx:02d}",
                    heading=current_scene_heading or "SCENE",
                    start_ms=current_scene_start_ms,
                    end_ms=current_scene_end_ms,
                    line_start=current_scene_line_start,
                    line_end=end_line,
                )
            )

    event_counter = 0

    while line_idx < total_lines:
        line_num = line_idx + 1
        raw_line = lines[line_idx]
        stripped = raw_line.strip()

        if not stripped:
            line_idx += 1
            continue

        # Header metadata checks
        if stripped.upper().startswith("EPISODE NUMBER:"):
            val = stripped.split(":", 1)[1].strip()
            digits = re.search(r"\d+", val)
            if digits:
                parsed_num = int(digits.group(0))
                if episode_number is not None and episode_number != parsed_num:
                    issues.append(
                        ParsingIssue(
                            severity=IssueSeverity.WARNING,
                            code="EPISODE_NUMBER_MISMATCH",
                            message=f"Filename suggests episode {episode_number} but header specifies episode {parsed_num}",
                            line=line_num,
                        )
                    )
                episode_number = parsed_num
            line_idx += 1
            continue

        if stripped.upper().startswith("EPISODE LOGLINE:"):
            logline = stripped.split(":", 1)[1].strip()
            line_idx += 1
            continue

        if stripped.upper().startswith("CONTINUITY NOTES:"):
            continuity_notes = stripped.split(":", 1)[1].strip()
            line_idx += 1
            continue

        if stripped in ("--- SCRIPT START ---", "--- SCRIPT END ---", "Actions and dialogue:"):
            line_idx += 1
            continue

        # Scene detection
        scene_match = SCENE_HEADER_REGEX.match(stripped)
        if scene_match:
            # Finalize previous scene if any
            if current_scene_id:
                finalize_current_scene(line_num - 1)

            current_scene_idx += 1
            current_scene_id = f"{ep_id}_s{current_scene_idx}"
            current_scene_label = stripped
            current_scene_heading = ""
            current_scene_start_ms = None
            current_scene_end_ms = None
            current_scene_line_start = line_num

            # Look ahead for heading, start, and end
            peek = line_idx + 1
            while peek < total_lines:
                peek_line = lines[peek].strip()
                if not peek_line:
                    peek += 1
                    continue
                if peek_line.lower().startswith("scene heading:"):
                    current_scene_heading = peek_line.split(":", 1)[1].strip()
                elif peek_line.lower().startswith("scene start:"):
                    ts_str = peek_line.split(":", 1)[1].strip()
                    parsed_start = parse_timestamp_to_ms(ts_str)
                    if parsed_start is None:
                        issues.append(
                            ParsingIssue(
                                severity=IssueSeverity.ERROR,
                                code="MALFORMED_TIMESTAMP",
                                message=f"Malformed Scene start timestamp '{ts_str}'",
                                line=peek + 1,
                            )
                        )
                    else:
                        current_scene_start_ms = parsed_start
                elif peek_line.lower().startswith("scene end:"):
                    ts_str = peek_line.split(":", 1)[1].strip()
                    parsed_end = parse_timestamp_to_ms(ts_str)
                    if parsed_end is None:
                        issues.append(
                            ParsingIssue(
                                severity=IssueSeverity.ERROR,
                                code="MALFORMED_TIMESTAMP",
                                message=f"Malformed Scene end timestamp '{ts_str}'",
                                line=peek + 1,
                            )
                        )
                    else:
                        current_scene_end_ms = parsed_end
                        if current_scene_start_ms is not None and parsed_end < current_scene_start_ms:
                            issues.append(
                                ParsingIssue(
                                    severity=IssueSeverity.ERROR,
                                    code="REVERSED_SCENE_TIMESTAMPS",
                                    message=f"Scene end ({format_ms_to_timestamp(parsed_end)}) occurs before scene start ({format_ms_to_timestamp(current_scene_start_ms)})",
                                    line=peek + 1,
                                )
                            )
                elif peek_line.startswith("**") or SCENE_HEADER_REGEX.match(peek_line):
                    break
                peek += 1

            line_idx = peek
            continue

        # Event detection: lines starting with ** or containing bold event header
        if stripped.startswith("**"):
            event_line_start = line_num
            raw_event_label = stripped
            # Extract inner content between **
            clean_label_content = stripped.replace("**", "").rstrip(":").strip()
            category, speaker, delivery_notes = determine_category_and_speaker(clean_label_content)

            if category == EventCategory.UNKNOWN:
                issues.append(
                    ParsingIssue(
                        severity=IssueSeverity.WARNING,
                        code="UNKNOWN_EVENT_LABEL",
                        message=f"Unrecognized event label: '{raw_event_label}'",
                        line=event_line_start,
                    )
                )

            # Look ahead for timing line
            timing_found = False
            event_start_ms: Optional[int] = None
            event_end_ms: Optional[int] = None
            body_lines: List[str] = []

            peek = line_idx + 1
            while peek < total_lines:
                peek_line = lines[peek]
                peek_stripped = peek_line.strip()
                if not peek_stripped:
                    # An empty line might separate header from timing or timing from body
                    peek += 1
                    continue

                if not timing_found:
                    if "Start:" in peek_stripped and "End:" in peek_stripped:
                        timing = extract_event_timing(peek_stripped)
                        if timing:
                            event_start_ms, event_end_ms = timing
                            timing_found = True
                        else:
                            issues.append(
                                ParsingIssue(
                                    severity=IssueSeverity.ERROR,
                                    code="MALFORMED_TIMESTAMP",
                                    message=f"Malformed event timing in line: '{peek_stripped}'",
                                    line=peek + 1,
                                )
                            )
                        peek += 1
                        continue
                    elif peek_stripped.startswith("**") or SCENE_HEADER_REGEX.match(peek_stripped):
                        # Another event started without timing
                        break
                    else:
                        peek += 1
                        continue
                else:
                    # Timing already found, read body lines until next event, scene or delimiter
                    if peek_stripped.startswith("**") or SCENE_HEADER_REGEX.match(peek_stripped) or peek_stripped.startswith("---"):
                        break
                    body_lines.append(peek_stripped)
                    peek += 1

            event_text = "\n".join(body_lines).strip()
            event_line_end = peek

            if timing_found and event_start_ms is not None and event_end_ms is not None:
                # Validation checks
                if event_end_ms < event_start_ms:
                    issues.append(
                        ParsingIssue(
                            severity=IssueSeverity.ERROR,
                            code="REVERSED_TIMESTAMPS",
                            message=f"Event end ({format_ms_to_timestamp(event_end_ms)}) before start ({format_ms_to_timestamp(event_start_ms)})",
                            line=event_line_start,
                        )
                    )

                if current_scene_start_ms is not None and event_start_ms < current_scene_start_ms:
                    issues.append(
                        ParsingIssue(
                            severity=IssueSeverity.WARNING,
                            code="EVENT_EXCEEDS_SCENE_BOUNDS",
                            message=f"Event start ({format_ms_to_timestamp(event_start_ms)}) precedes scene start ({format_ms_to_timestamp(current_scene_start_ms)})",
                            line=event_line_start,
                        )
                    )

                if current_scene_end_ms is not None and event_end_ms > current_scene_end_ms:
                    issues.append(
                        ParsingIssue(
                            severity=IssueSeverity.WARNING,
                            code="EVENT_EXCEEDS_SCENE_BOUNDS",
                            message=f"Event end ({format_ms_to_timestamp(event_end_ms)}) exceeds scene end ({format_ms_to_timestamp(current_scene_end_ms)})",
                            line=event_line_start,
                        )
                    )

                event_counter += 1
                if not current_scene_id:
                    # Event before any scene header
                    current_scene_idx += 1
                    current_scene_id = f"{ep_id}_s{current_scene_idx}"
                    current_scene_label = f"SCENE {current_scene_idx:02d}"
                    current_scene_heading = "UNTITLED SCENE"
                    current_scene_start_ms = event_start_ms
                    current_scene_end_ms = event_end_ms
                    current_scene_line_start = event_line_start

                events.append(
                    Event(
                        id=f"{ep_id}_e{event_counter:03d}",
                        scene_id=current_scene_id,
                        category=category,
                        original_label=raw_event_label,
                        speaker=speaker,
                        delivery_notes=delivery_notes,
                        start_ms=event_start_ms,
                        end_ms=event_end_ms,
                        text=event_text,
                        line_start=event_line_start,
                        line_end=event_line_end,
                    )
                )
            else:
                issues.append(
                    ParsingIssue(
                        severity=IssueSeverity.ERROR,
                        code="MISSING_EVENT_TIMING",
                        message=f"Event block '{raw_event_label}' missing valid Start/End timestamps",
                        line=event_line_start,
                    )
                )

            line_idx = peek
            continue

        # If a line has Start:/End: without preceding ** label
        if "Start:" in stripped and "End:" in stripped:
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="ORPHAN_TIMING_LINE",
                    message=f"Found timing line without recognized event label: '{stripped}'",
                    line=line_num,
                )
            )

        line_idx += 1

    # Finalize last scene
    if current_scene_id:
        finalize_current_scene(total_lines)

    # Compute duration from timeline bounds (never sum overlapping events!)
    timeline_ends = [s.end_ms for s in scenes] + [e.end_ms for e in events]
    timeline_starts = [s.start_ms for s in scenes] + [e.start_ms for e in events]

    if timeline_ends:
        duration_ms = max(timeline_ends) - (min(timeline_starts) if min(timeline_starts) < 0 else 0)
    else:
        duration_ms = 0

    episode = Episode(
        id=ep_id,
        episode_number=episode_number,
        filename=filename,
        logline=logline,
        continuity_notes=continuity_notes,
        duration_ms=duration_ms,
        scenes=scenes,
        events=events,
        warnings=issues,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
    )

    return episode, issues
