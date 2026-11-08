import io
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.ingest import process_ingestion_payloads

VALID_SCRIPT_1 = """EPISODE NUMBER: Episode 1
SCENE 01
Scene heading: INT. CASTLE - DAY
Scene start: 00:00.00
Scene end: 00:20.00

**CAMERA:**
Start: (00:00.00) | End: (00:05.00)
Pan across courtyard.
"""

VALID_SCRIPT_2_SAME_EP = """EPISODE NUMBER: Episode 1
SCENE 01
Scene heading: INT. DUNGEON - NIGHT
Scene start: 00:00.00
Scene end: 00:25.00

**ACTION:**
Start: (00:00.00) | End: (00:10.00)
A prisoner rattles the bars.
"""


def test_duplicate_content_and_duplicate_episode_numbers():
    payloads = [
        ("file1.txt", VALID_SCRIPT_1.encode("utf-8")),
        ("file2.txt", VALID_SCRIPT_2_SAME_EP.encode("utf-8")),
        ("file1_copy.txt", VALID_SCRIPT_1.encode("utf-8")),
    ]
    res = process_ingestion_payloads(payloads)

    assert res.total_episodes == 3
    all_issues = [w for ep in res.episodes for w in ep.warnings]
    dup_ep_issues = [i for i in all_issues if i.code == "DUPLICATE_EPISODE_NUMBER"]
    assert len(dup_ep_issues) >= 1

    dup_content_issues = [i for i in all_issues if i.code == "DUPLICATE_CONTENT"]
    assert len(dup_content_issues) >= 1


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "database_connected" in data


def test_preview_endpoint_multipart():
    client = TestClient(app)
    files = [
        ("files", ("ep1.txt", io.BytesIO(VALID_SCRIPT_1.encode("utf-8")), "text/plain")),
        ("files", ("ep2.txt", io.BytesIO(VALID_SCRIPT_2_SAME_EP.encode("utf-8")), "text/plain")),
    ]
    resp = client.post("/api/ingest/preview", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_episodes"] == 2
    assert len(data["episodes"]) == 2
    assert data["total_events"] == 2
    assert data["total_runtime_ms"] > 0
