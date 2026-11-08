import io
import zipfile
import pytest

from app.services.archive import read_zip_safely


def create_synthetic_zip(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in entries.items():
            z.writestr(path, content)
    return buf.getvalue()


def test_zip_with_nested_folders_and_macos_metadata():
    entries = {
        "folder/subfolder/episode-001.txt": "SCENE 01\nScene heading: A\nScene start: 00:00.00\nScene end: 00:10.00\n",
        "__MACOSX/._episode-001.txt": b"\x00\x05\x16\x07",
        ".DS_Store": b"\x00\x00\x00\x01",
        "notes.pdf": b"%PDF-1.4...",
    }
    zip_bytes = create_synthetic_zip(entries)
    result = read_zip_safely(zip_bytes)

    # Only episode-001.txt is valid
    assert len(result.valid_members) == 1
    assert result.valid_members[0].filename == "episode-001.txt"
    # Ignored: __MACOSX, .DS_Store, notes.pdf
    assert result.ignored_count >= 3


def test_zip_path_traversal_protection():
    entries = {
        "../../etc/passwd.txt": "root:x:0:0",
        "/etc/shadow.txt": "secret",
        "safe_episode.txt": "SCENE 01\nScene heading: Safe\nScene start: 00:00.00\nScene end: 00:10.00\n",
    }
    zip_bytes = create_synthetic_zip(entries)
    result = read_zip_safely(zip_bytes)

    assert len(result.valid_members) == 1
    assert result.valid_members[0].filename == "safe_episode.txt"
    traversal_warnings = [i for i in result.issues if i.code == "UNSAFE_ARCHIVE_PATH"]
    assert len(traversal_warnings) >= 1


def test_corrupt_zip():
    bad_bytes = b"NOT_A_ZIP_HEADER_DATA_123456"
    result = read_zip_safely(bad_bytes)
    assert len(result.valid_members) == 0
    assert any(i.code == "CORRUPT_ARCHIVE" for i in result.issues)


def test_decompression_bomb_protection():
    # File whose uncompressed size exceeds max_single_file_bytes limit
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("huge.txt", "A" * 2000)
    zip_bytes = buf.getvalue()

    # Pass very small limit for testing
    result = read_zip_safely(zip_bytes, max_single_file_bytes=500)
    assert len(result.valid_members) == 0
    assert any(i.code == "MEMBER_TOO_LARGE" for i in result.issues)

