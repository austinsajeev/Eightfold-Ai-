"""Extract candidate fields from recruiter notes."""

from __future__ import annotations

import re

from schema import CanonicalSkill, RawExtract

from pipeline.extractors._helpers import (
    add_provenance,
    compute_overall_confidence,
    empty_extract,
    find_emails,
    find_phones,
)

_CANONICAL_SKILLS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "sql",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "react",
    "node",
    "go",
    "rust",
    "c++",
    "machine learning",
    "data engineering",
]

_CONFIDENCE = 0.4


def _find_skills(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for skill in _CANONICAL_SKILLS:
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, lowered):
            found.append(skill.title() if skill != "c++" else "C++")
    return found


def extract(path: str) -> RawExtract:
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
        if not text.strip():
            return empty_extract()

        provenance = []
        confidences: list[float] = []
        result: RawExtract = {}

        emails = find_emails(text)
        if emails:
            result["email"] = emails[0]
            add_provenance(provenance, "email", "notes", "inferred")
            confidences.append(_CONFIDENCE)

        phones = find_phones(text)
        if phones:
            result["phone"] = phones[0]
            add_provenance(provenance, "phone", "notes", "inferred")
            confidences.append(_CONFIDENCE)

        skills = _find_skills(text)
        if skills:
            result["skills"] = [
                CanonicalSkill(name=skill, confidence=_CONFIDENCE, sources=["notes"])
                for skill in skills
            ]
            add_provenance(provenance, "skills", "notes", "inferred")
            confidences.extend([_CONFIDENCE] * len(skills))

        if provenance:
            result["provenance"] = provenance
            result["overall_confidence"] = compute_overall_confidence(confidences, _CONFIDENCE)
        return result
    except Exception:
        return empty_extract()
