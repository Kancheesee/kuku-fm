import pytest
from app.schemas.models import EventCategory, IssueSeverity
from app.services.parser import parse_script_content


SYNTHETIC_CLEAN_SCRIPT = """EPISODE NUMBER: Episode 99
EPISODE LOGLINE: A brave knight enters the castle seeking truth.
CONTINUITY NOTES: Follows the cliffhanger from Episode 98.

--- SCRIPT START ---

SCENE 01
Scene heading: INT. THRONE ROOM - DUSK
Scene start: 00:00.00
Scene end: 01:00.00

Actions and dialogue:

**CAMERA:**
Start: (00:00.00) | End: (00:05.00)
Wide establishing shot of the gothic throne room.

**ARTHUR (Defiant, Whispering):**
Start: (00:02.00) | End: (00:08.50)
"I will not surrender the crown."
"Not to you, and not to anyone."

**ACTION:**
Start: (00:04.00) | End: (00:07.00)
Arthur draws his ceremonial sword with steady resolve.

**SOUND FX:**
Start: (00:06.50) | End: (00:09.00)
Steel singing as the blade clears the scabbard.

--- SCRIPT END ---
"""


def test_clean_script_parsing():
    content = SYNTHETIC_CLEAN_SCRIPT.encode("utf-8")
    ep, issues = parse_script_content(content, filename="episode_99.txt")

    assert ep is not None
    assert ep.episode_number == 99
    assert ep.logline == "A brave knight enters the castle seeking truth."
    assert ep.continuity_notes == "Follows the cliffhanger from Episode 98."
    assert len(ep.scenes) == 1
    assert ep.scenes[0].heading == "INT. THRONE ROOM - DUSK"
    assert ep.scenes[0].start_ms == 0
    assert ep.scenes[0].end_ms == 60000

    # Events check
    assert len(ep.events) == 4
    # Camera
    assert ep.events[0].category == EventCategory.CAMERA
    assert ep.events[0].start_ms == 0
    assert ep.events[0].end_ms == 5000
    # Dialogue with delivery notes and multiline body
    assert ep.events[1].category == EventCategory.DIALOGUE
    assert ep.events[1].speaker == "ARTHUR"
    assert ep.events[1].delivery_notes == "Defiant, Whispering"
    assert ep.events[1].start_ms == 2000
    assert ep.events[1].end_ms == 8500
    assert '"I will not surrender the crown."' in ep.events[1].text
    assert '"Not to you, and not to anyone."' in ep.events[1].text
    # Action
    assert ep.events[2].category == EventCategory.ACTION
    # Sound effect
    assert ep.events[3].category == EventCategory.SOUND_EFFECT

    # Episode duration derived from bounds (0 to 60000)
    assert ep.duration_ms == 60000


def test_bom_and_crlf():
    # Prepend UTF-8 BOM and use CRLF
    crlf_text = SYNTHETIC_CLEAN_SCRIPT.replace("\n", "\r\n")
    bom_data = b"\xef\xbb\xbf" + crlf_text.encode("utf-8")

    ep, issues = parse_script_content(bom_data, filename="episode_bom.txt")
    assert ep is not None
    assert ep.episode_number == 99
    assert len(ep.events) == 4
    # Zero decoding errors
    errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
    assert len(errors) == 0


def test_overlapping_events_legitimacy():
    # Camera (0-5s), Arthur (2-8.5s), Action (4-7s) overlap legitimately
    ep, issues = parse_script_content(SYNTHETIC_CLEAN_SCRIPT.encode("utf-8"))
    assert ep is not None
    # No false error flagged for normal screenplay concurrency
    overlap_errors = [i for i in issues if "overlap" in i.message.lower()]
    assert len(overlap_errors) == 0


def test_reversed_timestamps():
    script = """SCENE 01
Scene heading: INT. ROOM
Scene start: 00:00.00
Scene end: 00:30.00

**CAMERA:**
Start: (00:15.00) | End: (00:05.00)
Reversed camera move.
"""
    ep, issues = parse_script_content(script.encode("utf-8"))
    assert ep is not None
    rev_issues = [i for i in issues if i.code == "REVERSED_TIMESTAMPS"]
    assert len(rev_issues) == 1


def test_event_exceeds_scene_bounds():
    script = """SCENE 01
Scene heading: INT. ROOM
Scene start: 00:10.00
Scene end: 00:30.00

**CAMERA:**
Start: (00:05.00) | End: (00:15.00)
Starts before scene.

**ACTION:**
Start: (00:25.00) | End: (00:35.00)
Ends after scene.
"""
    ep, issues = parse_script_content(script.encode("utf-8"))
    assert ep is not None
    bound_issues = [i for i in issues if i.code == "EVENT_EXCEEDS_SCENE_BOUNDS"]
    assert len(bound_issues) == 2


def test_unknown_event_label():
    script = """SCENE 01
Scene heading: INT. ROOM
Scene start: 00:00.00
Scene end: 00:30.00

**MYSTERY_EFFECT_999:**
Start: (00:05.00) | End: (00:10.00)
Strange holographic pulse.
"""
    ep, issues = parse_script_content(script.encode("utf-8"))
    assert ep is not None
    assert len(ep.events) == 1
    assert ep.events[0].category == EventCategory.UNKNOWN
    assert ep.events[0].original_label == "**MYSTERY_EFFECT_999:**"
    unknown_issues = [i for i in issues if i.code == "UNKNOWN_EVENT_LABEL"]
    assert len(unknown_issues) == 1


def test_stable_ids_on_repeated_parse():
    data = SYNTHETIC_CLEAN_SCRIPT.encode("utf-8")
    ep1, _ = parse_script_content(data, "ep1.txt")
    ep2, _ = parse_script_content(data, "ep1.txt")

    assert ep1.id == ep2.id
    assert ep1.content_hash == ep2.content_hash
    for ev1, ev2 in zip(ep1.events, ep2.events):
        assert ev1.id == ev2.id
        assert ev1.scene_id == ev2.scene_id

