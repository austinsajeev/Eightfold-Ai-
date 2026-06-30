"""Orchestrate extraction from all configured sources."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from schema import RawExtract

from pipeline.extractors import (
    ats_extractor,
    csv_extractor,
    github_extractor,
    notes_extractor,
    resume_extractor,
)

SOURCE_TYPES = ("csv", "ats_json", "github_url", "resume_pdf", "notes_txt")

_EXTENSION_TO_TYPE: dict[str, str] = {
    ".csv": "csv",
    ".json": "ats_json",
    ".pdf": "resume_pdf",
    ".txt": "notes_txt",
}

_EXTRACTOR_MODULES: dict[str, Any] = {
    "csv": csv_extractor,
    "ats_json": ats_extractor,
    "github_url": github_extractor,
    "resume_pdf": resume_extractor,
    "notes_txt": notes_extractor,
}

_PROFILE_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "full_name",
    "email",
    "emails",
    "phone",
    "phones",
    "location",
    "headline",
    "links",
    "current_title",
    "current_company",
    "linkedin_url",
    "github_username",
    "summary",
    "skills",
    "experience",
    "education",
    "recruiter_notes",
    "provenance",
    "overall_confidence",
)


def detect_source_type(path: str) -> str:
    """Guess source type from file extension."""
    ext = Path(path).suffix.lower()
    if ext not in _EXTENSION_TO_TYPE:
        raise ValueError(f"Cannot detect source type from extension: {ext!r}")
    return _EXTENSION_TO_TYPE[ext]


def _empty_raw_extract() -> RawExtract:
    return {field: None for field in _PROFILE_FIELDS}  # type: ignore[misc]


def _failure_extract(source_type: str, message: str, candidate_id: str) -> RawExtract:
    result = _empty_raw_extract()
    result["_error"] = f"{source_type}: {message}"
    result["_source"] = source_type
    result["_candidate_id"] = candidate_id
    return result


def _resolve_extractor(source_type: str) -> Callable[..., RawExtract]:
    module = _EXTRACTOR_MODULES.get(source_type)
    if module is None:
        raise ValueError(f"Unknown source type: {source_type!r}")
    extractor = getattr(module, "extract", None)
    if extractor is None:
        raise ValueError(f"No extract() function for source type: {source_type!r}")
    return extractor


def ingest(sources: list[dict]) -> list[RawExtract]:
    """Load each source descriptor and return one RawExtract per source."""
    results: list[RawExtract] = []

    for source in sources:
        candidate_id = str(source.get("candidate_id", ""))
        source_type: str | None = source.get("type")

        try:
            if not source_type:
                path = source.get("path")
                if not path:
                    raise ValueError("source missing both 'type' and 'path'")
                source_type = detect_source_type(path)

            extractor = _resolve_extractor(source_type)

            if source_type == "github_url":
                url = source.get("url")
                if not url:
                    raise ValueError("github_url source requires 'url'")
                raw = dict(extractor(url))
            else:
                path = source.get("path")
                if not path:
                    raise ValueError(f"{source_type} source requires 'path'")
                raw = dict(extractor(path))

            raw["_source"] = source_type
            raw["_candidate_id"] = candidate_id
            results.append(raw)  # type: ignore[arg-type]
        except Exception as exc:
            resolved_type = source_type or source.get("type") or "unknown"
            results.append(_failure_extract(resolved_type, str(exc), candidate_id))

    return results
