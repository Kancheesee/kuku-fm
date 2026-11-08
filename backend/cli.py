#!/usr/bin/env python3
"""CLI utility for Kuku Promo Studio: Parse scripts or ZIP archives,

display validation summaries, and export private validation reports.
"""

import argparse
import json
import os
import sys
from collections import Counter
from typing import List, Tuple

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.schemas.models import IngestPreviewResponse
from app.services.ingest import process_ingestion_payloads
from app.services.parser import PARSER_VERSION


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Parse microdrama screenplays and generate validation reports."
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Ingest / validate command (default)
    ingest_parser = subparsers.add_parser("ingest", help="Ingest and validate screenplays")
    ingest_parser.add_argument(
        "inputs",
        nargs="+",
        help="Path(s) to .txt script files, directories containing .txt files, or .zip archives.",
    )
    ingest_parser.add_argument(
        "--report",
        "-r",
        help="Path to write the JSON validation report (e.g. private_outputs/validation_report.json).",
        default=None,
    )
    ingest_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress human-readable summary output.",
    )

    # Analyze promos command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze promo candidates for an episode using AI")
    analyze_parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to .txt script or .zip archive containing episodes.",
    )
    analyze_parser.add_argument(
        "--input",
        "-i",
        dest="input_opt",
        default=None,
        help="Path to .txt script or .zip archive containing episodes.",
    )
    analyze_parser.add_argument(
        "--episode",
        "-e",
        type=int,
        default=None,
        help="Episode number to analyze (if omitted, analyzes the first episode found).",
    )
    analyze_parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Override Gemini model identifier.",
    )
    analyze_parser.add_argument(
        "--out",
        "-o",
        default=None,
        help="Path to save raw JSON promo analysis report (e.g. private_outputs/episode_001_promos.json).",
    )

    return parser.parse_args()


def collect_file_payloads(paths: List[str]) -> List[Tuple[str, bytes]]:
    payloads: List[Tuple[str, bytes]] = []

    for p in paths:
        if not os.path.exists(p):
            print(f"Error: Path '{p}' does not exist.", file=sys.stderr)
            continue

        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(".txt") or f.lower().endswith(".zip"):
                        full_path = os.path.join(root, f)
                        try:
                            with open(full_path, "rb") as fp:
                                payloads.append((f, fp.read()))
                        except Exception as e:
                            print(f"Error reading '{full_path}': {e}", file=sys.stderr)
        elif os.path.isfile(p):
            try:
                with open(p, "rb") as fp:
                    payloads.append((os.path.basename(p), fp.read()))
            except Exception as e:
                print(f"Error reading '{p}': {e}", file=sys.stderr)

    return payloads


def generate_validation_summary(response: IngestPreviewResponse) -> dict:
    ep_numbers = [e.episode_number for e in response.episodes if e.episode_number is not None]
    duplicate_ep_numbers = [num for num, count in Counter(ep_numbers).items() if count > 1]
    
    # Categorize issues by code and severity
    all_issues = []
    for f in response.file_results:
        all_issues.extend(f.issues)
    for e in response.episodes:
        all_issues.extend(e.warnings)
    # Deduplicate issues by (code, message, line)
    unique_issues_dict = {}
    for issue in all_issues:
        key = (issue.code, issue.severity, issue.message, issue.line)
        if key not in unique_issues_dict:
            unique_issues_dict[key] = issue
    unique_issues = list(unique_issues_dict.values())

    issues_by_code = Counter(i.code for i in unique_issues)
    issues_by_severity = Counter(i.severity.value for i in unique_issues)

    # Count categories across all events
    categories_count = Counter()
    for ep in response.episodes:
        for ev in ep.events:
            categories_count[ev.category.value] += 1

    report = {
        "parser_version": PARSER_VERSION,
        "summary": {
            "files_processed": len(response.file_results),
            "files_succeeded": sum(1 for f in response.file_results if f.success),
            "files_failed": sum(1 for f in response.file_results if not f.success),
            "episodes_parsed": response.total_episodes,
            "total_scenes": sum(len(e.scenes) for e in response.episodes),
            "total_events": response.total_events,
            "total_runtime_ms": response.total_runtime_ms,
            "total_runtime_formatted": f"{response.total_runtime_ms / 60000:.2f} mins",
            "ignored_files_count": response.ignored_files_count,
            "duplicate_episode_numbers": duplicate_ep_numbers,
        },
        "event_category_breakdown": dict(categories_count),
        "issues_summary": {
            "by_severity": dict(issues_by_severity),
            "by_code": dict(issues_by_code),
            "total_unique_issues": len(unique_issues),
        },
        "episodes": [
            {
                "id": ep.id,
                "episode_number": ep.episode_number,
                "filename": ep.filename,
                "duration_ms": ep.duration_ms,
                "scenes_count": len(ep.scenes),
                "events_count": len(ep.events),
                "issues_count": len(ep.warnings),
                "content_hash": ep.content_hash,
                "issues": [
                    {
                        "severity": w.severity.value,
                        "code": w.code,
                        "message": w.message,
                        "line": w.line,
                    }
                    for w in ep.warnings
                ],
            }
            for ep in response.episodes
        ],
    }
    return report


def handle_analyze(args):
    from app.services.ai.orchestrator import analyze_episode_for_promos
    input_path = args.input_opt or args.input
    if not input_path:
        print("Error: Input path to .txt or .zip required.", file=sys.stderr)
        sys.exit(1)

    payloads = collect_file_payloads([input_path])
    if not payloads:
        print(f"Error: No valid screenplay files found in '{input_path}'", file=sys.stderr)
        sys.exit(1)

    ingest_res = process_ingestion_payloads(payloads)
    if not ingest_res.episodes:
        print("Error: Ingestion yielded 0 valid episodes.", file=sys.stderr)
        sys.exit(1)

    target_ep = None
    if args.episode is not None:
        for ep in ingest_res.episodes:
            if ep.episode_number == args.episode:
                target_ep = ep
                break
        if not target_ep:
            print(f"Error: Episode {args.episode} not found in input.", file=sys.stderr)
            sys.exit(1)
    else:
        target_ep = ingest_res.episodes[0]

    print(f"\nAnalyzing Episode {target_ep.episode_number or 'Untitled'} ({target_ep.filename}) for promo candidates...")
    print(f"Total events: {len(target_ep.events)} | Duration: {target_ep.duration_ms / 1000:.1f}s")

    try:
        res = analyze_episode_for_promos(
            episode=target_ep,
            model_override=args.model,
        )
    except Exception as e:
        print(f"AI Promo analysis failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n=== Promo Discovery Results ===")
    print(f"Model: {res.metadata.get('model')} (Total Latency: {res.metadata.get('total_latency_ms', 0)} ms)")
    print(f"API Calls: {res.metadata.get('api_calls_completed', 1)} completed of {res.metadata.get('api_calls_attempted', 1)} attempted | Assessment Status: {res.metadata.get('assessment_status')}")
    print(f"Tokens: Generation: {res.metadata.get('generation_tokens')} | Assessment: {res.metadata.get('assessment_tokens')}")
    print(f"Cache Key: {res.cache_key}")
    print(f"Proposals Generated: {res.metadata.get('total_proposals_generated')}")
    print(f"Candidates Accepted: {len(res.candidates)}")
    print(f"Proposals Rejected: {len(res.rejected_proposals)}")
    print(f"Duplicates Suppressed: {len(res.suppressed_candidates)}")

    for c in res.candidates:
        seg = c.segment
        print(f"\n[Rank #{c.rank}] {c.editorial_title}")
        print(f"  Duration: {seg.duration_seconds}s | Range: {seg.start_timestamp} -> {seg.end_timestamp} ({len(seg.events)} events)")
        print(f"  Hook (First 3s): {c.hook_explanation}")
        print(f"  Cliffhanger: {c.cliffhanger_explanation}")
        print(f"  Unresolved Question: {c.unresolved_question}")
        print(f"  Rationale: {c.rationale}")
        if c.rubric:
            print(f"  Editorial Rubric: Score {c.rubric.overall_score}/5.0 (Opening: {c.rubric.opening_strength}, Clarity: {c.rubric.standalone_clarity}, Stakes: {c.rubric.escalation_stakes}, Ending: {c.rubric.unresolved_ending})")
        else:
            print("  Editorial Rubric: Assessment unavailable (mechanically valid cut)")
        if c.review_flags:
            print(f"  Review Flags: {', '.join(c.review_flags)}")

    if res.rejected_proposals:
        print(f"\n--- Rejected Proposals ({len(res.rejected_proposals)}) ---")
        for r in res.rejected_proposals:
            print(f"  - '{r.proposal.editorial_title}': {'; '.join(r.rejection_reasons)}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(res.model_dump_json(indent=2))
        print(f"\nRaw analysis and audit exported to: {args.out}")


def main():
    args = parse_arguments()
    command = args.command or "ingest"

    if command == "analyze":
        handle_analyze(args)
        return

    # Ingest / validation logic
    inputs = getattr(args, "inputs", None)
    if not inputs:
        # Fallback if no command specified but inputs passed
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            inputs = [sys.argv[1]]
        else:
            print("Please specify files or archive to ingest.", file=sys.stderr)
            sys.exit(1)

    payloads = collect_file_payloads(inputs)
    if not payloads:
        print("No valid files or zip archives found to process.", file=sys.stderr)
        sys.exit(1)

    result = process_ingestion_payloads(payloads)
    report = generate_validation_summary(result)

    if not args.quiet:
        print("\n=== Kuku Promo Studio - Script Ingestion Summary ===")
        print(f"Parser Version: {report['parser_version']}")
        print(f"Files Processed: {report['summary']['files_processed']} (Success: {report['summary']['files_succeeded']}, Failed: {report['summary']['files_failed']})")
        print(f"Episodes Parsed: {report['summary']['episodes_parsed']}")
        print(f"Total Scenes: {report['summary']['total_scenes']}")
        print(f"Total Timed Events: {report['summary']['total_events']}")
        print(f"Total Runtime: {report['summary']['total_runtime_formatted']} ({report['summary']['total_runtime_ms']} ms)")
        print(f"Ignored Non-Script / System Members: {report['summary']['ignored_files_count']}")
        print(f"Event Categories: {report['event_category_breakdown']}")
        print(f"Issues Detected: {report['issues_summary']['by_code']} (Total: {report['issues_summary']['total_unique_issues']})")
        if report['summary']['duplicate_episode_numbers']:
            print(f"Duplicate Episode Numbers Detected: {report['summary']['duplicate_episode_numbers']}")
        print("====================================================\n")

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        if not args.quiet:
            print(f"Validation report saved to: {args.report}")


if __name__ == "__main__":
    main()

