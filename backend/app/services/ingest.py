import os
from typing import Dict, List, Set, Tuple

from app.schemas.models import (
    Episode,
    IngestFileResult,
    IngestPreviewResponse,
    IssueSeverity,
    ParsingIssue,
)
from app.services.archive import read_zip_safely
from app.services.parser import parse_script_content


def process_ingestion_payloads(
    raw_files: List[Tuple[str, bytes]],
) -> IngestPreviewResponse:
    """Process a collection of uploaded files (which may include .txt scripts or .zip archives).

    Returns a comprehensive IngestPreviewResponse with all parsed episodes, validation
    diagnostics, and batch metrics.
    """
    total_ignored = 0
    batch_issues: List[ParsingIssue] = []
    file_results: List[IngestFileResult] = []
    parsed_episodes: List[Episode] = []

    # Flatten zip members into scripts to process
    scripts_to_process: List[Tuple[str, bytes]] = []

    for filename, content_bytes in raw_files:
        clean_name = os.path.basename(filename)
        if clean_name.lower().endswith(".zip"):
            archive_res = read_zip_safely(content_bytes)
            total_ignored += archive_res.ignored_count
            batch_issues.extend(archive_res.issues)
            for member in archive_res.valid_members:
                scripts_to_process.append((member.filename, member.content_bytes))
        elif clean_name.lower().endswith(".txt"):
            scripts_to_process.append((clean_name, content_bytes))
        else:
            # Non-txt, non-zip file uploaded directly
            total_ignored += 1
            batch_issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="IGNORED_NON_SCRIPT_FILE",
                    message=f"Ignored unsupported file format: '{clean_name}' (expected .txt or .zip)",
                )
            )

    # Track duplicates across files in this ingestion batch
    seen_hashes: Dict[str, str] = {}  # hash -> first filename
    ep_numbers_seen: Dict[int, str] = {}  # ep_num -> first filename

    for fname, data in scripts_to_process:
        ep, issues = parse_script_content(data, filename=fname)

        if ep is None:
            file_results.append(
                IngestFileResult(
                    filename=fname,
                    success=False,
                    episode=None,
                    issues=issues,
                )
            )
            continue

        file_issues = list(issues)

        # Content duplicate check
        if ep.content_hash in seen_hashes:
            first_seen = seen_hashes[ep.content_hash]
            file_issues.append(
                ParsingIssue(
                    severity=IssueSeverity.WARNING,
                    code="DUPLICATE_CONTENT",
                    message=f"Exact duplicate content as '{first_seen}'",
                )
            )
        else:
            seen_hashes[ep.content_hash] = fname

        # Episode number collision check
        if ep.episode_number is not None:
            if ep.episode_number in ep_numbers_seen:
                prior_fname = ep_numbers_seen[ep.episode_number]
                file_issues.append(
                    ParsingIssue(
                        severity=IssueSeverity.WARNING,
                        code="DUPLICATE_EPISODE_NUMBER",
                        message=f"Episode number {ep.episode_number} was also claimed by '{prior_fname}'",
                    )
                )
            else:
                ep_numbers_seen[ep.episode_number] = fname

        # Update episode warnings to include batch-level duplicates
        ep.warnings = file_issues

        parsed_episodes.append(ep)
        file_results.append(
            IngestFileResult(
                filename=fname,
                success=True,
                episode=ep,
                issues=file_issues,
            )
        )

    # Sort episodes by episode number (if available) then filename
    parsed_episodes.sort(key=lambda e: (e.episode_number is None, e.episode_number or 0, e.filename))

    total_runtime_ms = sum(e.duration_ms for e in parsed_episodes)
    total_events = sum(len(e.events) for e in parsed_episodes)
    total_issues = sum(len(res.issues) for res in file_results) + len(batch_issues)

    return IngestPreviewResponse(
        episodes=parsed_episodes,
        total_episodes=len(parsed_episodes),
        total_runtime_ms=total_runtime_ms,
        total_events=total_events,
        total_issues=total_issues,
        ignored_files_count=total_ignored,
        file_results=file_results,
    )

