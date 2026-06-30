"""Project CandidateProfile to output formats (JSON, etc.)."""

from __future__ import annotations

import re
from typing import Any

from config import OutputConfig
from schema import CandidateProfile

from pipeline.normalizers import normalize_phone, normalize_skill

_SEGMENT_RE = re.compile(r"^([A-Za-z_][\w]*)(?:\[(\d*)\])?$")


def _split_path(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def _parse_segment(segment: str) -> tuple[str, int | str | None]:
    match = _SEGMENT_RE.fullmatch(segment)
    if not match:
        return segment, None
    key = match.group(1)
    bracket = match.group(2)
    if bracket is None:
        return key, None
    if bracket == "":
        return key, "all"
    return key, int(bracket)


def _get_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _resolve_value(obj: Any, parts: list[str]) -> Any:
    if obj is None:
        return None
    if not parts:
        return obj

    segment = parts[0]
    rest = parts[1:]
    key, index = _parse_segment(segment)
    current = _get_key(obj, key)

    if index is None:
        if not rest:
            return current
        return _resolve_value(current, rest)

    if not isinstance(current, list):
        return None

    if index == "all":
        if not rest:
            return current
        return [_resolve_value(item, rest) for item in current]

    if index < 0 or index >= len(current):
        return None
    return _resolve_value(current[index], rest)


def resolve_path(obj: dict, path: str) -> Any:
    """Resolve a dot-path against a profile dict; returns None if missing."""
    if not path:
        return None
    try:
        return _resolve_value(obj, _split_path(path))
    except (TypeError, ValueError, AttributeError):
        return None


def _apply_normalize(value: Any, normalize: str | None) -> Any:
    if normalize is None or value is None:
        return value

    if normalize == "E164":
        if isinstance(value, list):
            return [normalize_phone(str(item)) for item in value]
        return normalize_phone(str(value))

    if normalize == "canonical":
        if isinstance(value, list):
            return [normalize_skill(str(item)) for item in value]
        return normalize_skill(str(value))

    return value


def _check_type(value: Any, type_name: str, path: str) -> None:
    """Validate a projected value matches the configured field type."""
    if type_name == "auto":
        return
    if value is None:
        return

    if type_name == "string":
        if not isinstance(value, str):
            raise ValueError(f"Field '{path}' expected string, got {type(value).__name__}")
        return

    if type_name in {"string[]", "string_array"}:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Field '{path}' expected string[], got {type(value).__name__}")
        return

    if type_name == "array":
        if not isinstance(value, list):
            raise ValueError(f"Field '{path}' expected array, got {type(value).__name__}")
        return

    if type_name == "number":
        if not isinstance(value, (int, float)):
            raise ValueError(f"Field '{path}' expected number, got {type(value).__name__}")
        return

    if type_name == "object":
        if not isinstance(value, dict):
            raise ValueError(f"Field '{path}' expected object, got {type(value).__name__}")
        return


def validate_output(output: dict[str, Any], config: OutputConfig) -> None:
    """Validate projected output values against OutputConfig field types."""
    for spec in config.fields:
        if spec.path not in output:
            continue
        _check_type(output[spec.path], spec.type, spec.path)

    if config.include_confidence and "confidence" in output:
        _check_type(output["confidence"], "number", "confidence")

    if config.include_provenance and "provenance" in output:
        if not isinstance(output["provenance"], list):
            raise ValueError("Field 'provenance' expected array")


def project(profile: CandidateProfile, config: OutputConfig) -> dict:
    """Project a canonical profile into a configured output dictionary."""
    source_data = profile.model_dump()
    output: dict[str, Any] = {}

    for spec in config.fields:
        source_path = spec.from_ or spec.path
        value = resolve_path(source_data, source_path)
        value = _apply_normalize(value, spec.normalize)

        if value is None:
            if spec.required or config.on_missing == "error":
                raise ValueError(f"Missing value for field path: {spec.path}")
            if config.on_missing == "omit":
                continue
            output[spec.path] = None
            continue

        output[spec.path] = value

    if config.include_confidence:
        output["confidence"] = profile.overall_confidence

    if config.include_provenance:
        output["provenance"] = [entry.model_dump() for entry in profile.provenance]

    validate_output(output, config)
    return output
