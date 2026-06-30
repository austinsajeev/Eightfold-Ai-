"""Command-line entry point for the eightfold-pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import default_config, load_config
from pipeline.ingest import detect_source_type, ingest
from pipeline.merger import _SOURCE_ALIASES, merge
from pipeline.normalizers import normalize_extract
from pipeline.projector import project
from schema import CandidateProfile

SUPPORTED_EXTENSIONS = {".csv", ".json", ".pdf", ".txt"}


def collect_input_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(child)
        elif path.is_file():
            files.append(path)
    return files


def build_sources(files: list[Path], candidate_id: str | None) -> list[dict]:
    sources: list[dict] = []
    for path in files:
        descriptor: dict = {
            "path": str(path),
            "candidate_id": candidate_id or "",
        }
        try:
            descriptor["type"] = detect_source_type(str(path))
        except ValueError:
            print(f"Skipping unsupported file: {path}", file=sys.stderr)
            continue
        sources.append(descriptor)
    return sources


def count_filled_fields(profile: CandidateProfile) -> list[str]:
    data = profile.model_dump()
    filled: list[str] = []
    for key, value in data.items():
        if key in {"provenance", "overall_confidence"}:
            continue
        if value is None:
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        filled.append(key)
    return filled


def source_label(raw_source: str | None) -> str | None:
    if not raw_source:
        return None
    return _SOURCE_ALIASES.get(raw_source, raw_source)


def print_summary(
    extracts: list[dict],
    profile: CandidateProfile,
) -> None:
    labels: list[str] = []
    for extract in extracts:
        label = source_label(extract.get("_source"))
        if label and label not in labels:
            labels.append(label)

    filled = count_filled_fields(profile)
    print(f"Sources processed: {', '.join(labels) if labels else 'none'} ({len(labels)})", file=sys.stderr)
    print(f"Fields filled: {', '.join(filled) if filled else 'none'} ({len(filled)})", file=sys.stderr)
    print(f"Overall confidence: {profile.overall_confidence:.2f}", file=sys.stderr)


def run_pipeline(
    input_paths: list[str],
    config_path: str | None,
    candidate_id: str | None,
) -> tuple[dict, CandidateProfile, list[dict]]:
    files = collect_input_files(input_paths)
    if not files:
        raise SystemExit("No supported input files found.")

    sources = build_sources(files, candidate_id)
    if not sources:
        raise SystemExit("No ingestible sources found.")

    extracts = ingest(sources)
    normalized = [normalize_extract(extract) for extract in extracts]
    profile = merge(normalized)

    if candidate_id:
        profile = profile.model_copy(update={"candidate_id": candidate_id})

    config = load_config(config_path) if config_path else default_config()
    output = project(profile, config)
    return output, profile, [dict(extract) for extract in extracts]


def main() -> None:
    parser = argparse.ArgumentParser(description="Eightfold candidate data pipeline")
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input files or directories containing supported source files",
    )
    parser.add_argument("--config", help="Path to OutputConfig JSON")
    parser.add_argument("--output", help="Path to write result JSON (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output with 2 spaces")
    parser.add_argument("--candidate-id", help="Optional override for candidate_id")
    args = parser.parse_args()

    output, profile, extracts = run_pipeline(args.inputs, args.config, args.candidate_id)
    print_summary(extracts, profile)

    indent = 2 if args.pretty else None
    rendered = json.dumps(output, indent=indent, default=str)

    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
