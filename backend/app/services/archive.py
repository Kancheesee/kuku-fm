import io
import os
import zipfile
from typing import List, NamedTuple, Tuple

from app.schemas.models import IssueSeverity, ParsingIssue

# Security limits for safe decompression
DEFAULT_MAX_ZIP_SIZE = 50 * 1024 * 1024  # 50 MB
DEFAULT_MAX_MEMBER_COUNT = 500
DEFAULT_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_MAX_SINGLE_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


class SafeArchiveMember(NamedTuple):
    filename: str
    content_bytes: bytes


class ArchiveInspectionResult(NamedTuple):
    valid_members: List[SafeArchiveMember]
    ignored_count: int
    issues: List[ParsingIssue]


def is_macos_metadata_or_system(filename: str) -> bool:
    """Check if the archive member is macOS metadata, DS_Store, or system artifact."""
    norm = filename.replace("\\", "/")
    parts = norm.split("/")
    if any(p == "__MACOSX" for p in parts):
        return True
    basename = parts[-1]
    if basename.startswith("._") or basename == ".DS_Store" or basename.startswith("Thumbs.db"):
        return True
    return False


def is_safe_path(filename: str) -> bool:
    """Ensure the path does not attempt path traversal or absolute references."""
    norm = filename.replace("\\", "/")
    if norm.startswith("/") or ".." in norm.split("/"):
        return False
    return True


def read_zip_safely(
    zip_bytes: bytes,
    max_zip_size: int = DEFAULT_MAX_ZIP_SIZE,
    max_members: int = DEFAULT_MAX_MEMBER_COUNT,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    max_single_file_bytes: int = DEFAULT_MAX_SINGLE_FILE_BYTES,
) -> ArchiveInspectionResult:
    """Safely inspect and extract .txt files from a ZIP archive without writing to disk.

    Guards against zip bombs, path traversal, encrypted archives, and invalid members.
    """
    issues: List[ParsingIssue] = []
    valid_members: List[SafeArchiveMember] = []
    ignored_count = 0

    if len(zip_bytes) > max_zip_size:
        issues.append(
            ParsingIssue(
                severity=IssueSeverity.ERROR,
                code="ARCHIVE_TOO_LARGE",
                message=f"ZIP archive size ({len(zip_bytes)} bytes) exceeds limit of {max_zip_size} bytes",
            )
        )
        return ArchiveInspectionResult([], 0, issues)

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    except zipfile.BadZipFile as exc:
        issues.append(
            ParsingIssue(
                severity=IssueSeverity.ERROR,
                code="CORRUPT_ARCHIVE",
                message=f"The uploaded file is not a valid or readable ZIP archive: {exc}",
            )
        )
        return ArchiveInspectionResult([], 0, issues)

    infolist = zf.infolist()
    if len(infolist) > max_members:
        issues.append(
            ParsingIssue(
                severity=IssueSeverity.ERROR,
                code="ARCHIVE_MEMBER_LIMIT_EXCEEDED",
                message=f"ZIP archive contains {len(infolist)} entries, exceeding the maximum allowed ({max_members})",
            )
        )
        return ArchiveInspectionResult([], 0, issues)

    total_uncompressed = 0

    for info in infolist:
        # Check if directory
        if info.is_dir() or info.filename.endswith("/"):
            ignored_count += 1
            continue

        # Check macOS metadata
        if is_macos_metadata_or_system(info.filename):
            ignored_count += 1
            continue

        # Check path traversal
        if not is_safe_path(info.filename):
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="UNSAFE_ARCHIVE_PATH",
                    message=f"Ignored member with potential path traversal: '{info.filename}'",
                )
            )
            ignored_count += 1
            continue

        # Check encryption
        if info.flag_bits & 0x1:
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="ENCRYPTED_ARCHIVE_MEMBER",
                    message=f"Member '{info.filename}' is encrypted and cannot be processed",
                )
            )
            ignored_count += 1
            continue

        # Check extension: only accept .txt screenplays
        if not info.filename.lower().endswith(".txt"):
            ignored_count += 1
            continue

        # Check single file uncompressed limit
        if info.file_size > max_single_file_bytes:
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="MEMBER_TOO_LARGE",
                    message=f"Member '{info.filename}' size ({info.file_size} bytes) exceeds {max_single_file_bytes} bytes limit",
                )
            )
            ignored_count += 1
            continue

        total_uncompressed += info.file_size
        if total_uncompressed > max_uncompressed_bytes:
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.ERROR,
                    code="DECOMPRESSION_BOMB_LIMIT",
                    message=f"Decompressed archive size exceeds limit of {max_uncompressed_bytes} bytes",
                )
            )
            break

        try:
            content = zf.read(info)
            # Use basename or relative safe name for presentation
            clean_name = os.path.basename(info.filename)
            valid_members.append(SafeArchiveMember(filename=clean_name, content_bytes=content))
        except Exception as exc:
            issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="ARCHIVE_READ_ERROR",
                    message=f"Failed to read member '{info.filename}': {exc}",
                )
            )

    return ArchiveInspectionResult(valid_members, ignored_count, issues)

