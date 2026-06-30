"""Extract candidate fields from ATS JSON input."""

from __future__ import annotations

import json
from typing import Any

from schema import CanonicalSkill, ExperienceEntry, RawExtract

from pipeline.extractors._helpers import (
    add_provenance,
    compute_overall_confidence,
    empty_extract,
    first_scalar,
    get_by_aliases,
)

_FIELD_MAPPINGS: dict[str, list[str]] = {
    "full_name": ["applicant_name", "candidate_name", "full_name", "name"],
    "email": ["contact_email", "email_address", "primaryemail", "primary_email", "email"],
    "phone": ["mobile", "cell", "phone_number", "phone", "primary_phone"],
    "experience_title": ["job_title", "position", "role", "title", "current_title"],
    "experience_company": ["employer", "company_name", "org", "organization", "current_company"],
}


def _load_payload(path: str) -> dict[str, Any] | None:
    with open(path, encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        if not data:
            return None
        first = data[0]
        return first if isinstance(first, dict) else None
    if isinstance(data, dict):
        for key in ("candidate", "applicant", "profile", "data"):
            nested = data.get(key)
            if isinstance(nested, dict):
                return nested
            if isinstance(nested, list) and nested and isinstance(nested[0], dict):
                return nested[0]
        return data
    return None


def extract(path: str) -> RawExtract:
    try:
        payload = _load_payload(path)
        if not payload:
            return empty_extract()

        provenance = []
        confidences: list[float] = []
        result: RawExtract = {}

        full_name = first_scalar(get_by_aliases(payload, _FIELD_MAPPINGS["full_name"]))
        if full_name:
            result["full_name"] = full_name
            add_provenance(provenance, "full_name", "ats", "direct")
            confidences.append(0.9)

        email = first_scalar(get_by_aliases(payload, _FIELD_MAPPINGS["email"]))
        if email:
            result["email"] = email
            add_provenance(provenance, "email", "ats", "direct")
            confidences.append(0.9)

        phone = first_scalar(get_by_aliases(payload, _FIELD_MAPPINGS["phone"]))
        if phone:
            result["phone"] = phone
            add_provenance(provenance, "phone", "ats", "direct")
            confidences.append(0.9)

        title = first_scalar(get_by_aliases(payload, _FIELD_MAPPINGS["experience_title"]))
        company = first_scalar(get_by_aliases(payload, _FIELD_MAPPINGS["experience_company"]))
        if title or company:
            entry = ExperienceEntry(
                company=company or "",
                title=title or "",
            )
            result["experience"] = [entry]
            add_provenance(provenance, "experience", "ats", "direct")
            confidences.append(0.85)
            if title:
                result["current_title"] = title
                add_provenance(provenance, "current_title", "ats", "direct")
            if company:
                result["current_company"] = company
                add_provenance(provenance, "current_company", "ats", "direct")

        skills_raw = get_by_aliases(payload, ["skills_raw", "skills", "skill_list"])
        if isinstance(skills_raw, str) and skills_raw.strip():
            skill_names = [part.strip() for part in skills_raw.split(",") if part.strip()]
            if skill_names:
                result["skills"] = [
                    CanonicalSkill(name=name, confidence=0.9, sources=["ats"]) for name in skill_names
                ]
                add_provenance(provenance, "skills", "ats", "direct")
                confidences.append(0.85)

        if provenance:
            result["provenance"] = provenance
            result["overall_confidence"] = compute_overall_confidence(confidences, 0.85)
        return result
    except Exception:
        return empty_extract()
