import re
from typing import Optional, Tuple


TIMESTAMP_REGEX = re.compile(r"^\(?\s*(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)\s*\)?$")
# Also match inline timestamp pattern like "Start: (00:00.00) | End: (00:01.80)"
EVENT_TIMING_REGEX = re.compile(
    r"Start:\s*\(?(\d+(?::\d+){1,2}(?:\.\d+)?)\)?\s*\|\s*End:\s*\(?(\d+(?::\d+){1,2}(?:\.\d+)?)\)?",
    re.IGNORECASE,
)


def parse_timestamp_to_ms(ts_str: str) -> Optional[int]:
    """Parse a timestamp string like '01:10.50' or '(00:00.00)' or '01:02:03.45'

    into integer milliseconds. Returns None if invalid or negative.
    """
    if not ts_str:
        return None
    cleaned = ts_str.strip()
    match = TIMESTAMP_REGEX.match(cleaned)
    if not match:
        return None

    hours_s, mins_s, secs_s = match.groups()
    hours = int(hours_s) if hours_s is not None else 0
    mins = int(mins_s)
    try:
        secs = float(secs_s)
    except ValueError:
        return None

    if hours < 0 or mins < 0 or secs < 0:
        return None

    total_seconds = hours * 3600 + mins * 60 + secs
    return int(round(total_seconds * 1000))


def format_ms_to_timestamp(ms: int) -> str:
    """Format milliseconds into canonical representation: 'mm:ss.SS' or 'hh:mm:ss.SS'."""
    if ms < 0:
        return "00:00.00"
    total_seconds = ms / 1000.0
    hours = int(total_seconds // 3600)
    remaining = total_seconds % 3600
    minutes = int(remaining // 60)
    seconds = remaining % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
    return f"{minutes:02d}:{seconds:05.2f}"


def extract_event_timing(line: str) -> Optional[Tuple[int, int]]:
    """Extract (start_ms, end_ms) from an event timing line:

    'Start: (00:00.00) | End: (00:01.80)'
    """
    match = EVENT_TIMING_REGEX.search(line)
    if not match:
        return None
    start_str, end_str = match.groups()
    start_ms = parse_timestamp_to_ms(start_str)
    end_ms = parse_timestamp_to_ms(end_str)
    if start_ms is None or end_ms is None:
        return None
    return start_ms, end_ms

