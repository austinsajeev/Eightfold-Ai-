"""Extract candidate fields from CSV input."""

from __future__ import annotations

import csv

from schema import ExperienceEntry, RawExtract

from pipeline.extractors._helpers import (
    add_provenance,
    compute_overall_confidence,
    empty_extract,
    first_scalar,
    normalize_keys,
)

_COLUMN_ALIASES: dict[str, list[str]] = {
    "candidate_id": ["candidate_id", "id", "candidateid"],
    "full_name": ["name", "full_name", "fullname", "candidate_name"],
    "email": ["email", "emails", "email_address"],
    "phone": ["phone", "phones", "phone_number", "mobile"],
    "current_company": ["current_company", "company", "employer"],
    "current_title": ["title", "current_title", "job_title", "position"],
}


def _pick(row: dict[str, str], field: str) -> str | None:
    normalized = normalize_keys(row)
    for alias in _COLUMN_ALIASES[field]:
        value = first_scalar(normalized.get(alias))
        if value:
            return value
    return None


def extract(path: str) -> RawExtract:
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            row = next(reader, None)
        if not row:
            return empty_extract()

        provenance = []
        confidences: list[float] = []
        result: RawExtract = {}

        candidate_id = _pick(row, "candidate_id")
        if candidate_id:
            result["candidate_id"] = candidate_id
            add_provenance(provenance, "candidate_id", "csv", "direct")
            confidences.append(0.95)

        full_name = _pick(row, "full_name")
        if full_name:
            result["full_name"] = full_name
            add_provenance(provenance, "full_name", "csv", "direct")
            confidences.append(0.95)

        email = _pick(row, "email")
        if email:
            result["email"] = email
            add_provenance(provenance, "email", "csv", "direct")
            confidences.append(0.95)

        phone = _pick(row, "phone")
        if phone:
            result["phone"] = phone
            add_provenance(provenance, "phone", "csv", "direct")
            confidences.append(0.95)

        company = _pick(row, "current_company")
        title = _pick(row, "current_title")
        if company or title:
            entry = ExperienceEntry(
                company=company or "",
                title=title or "",
                start="0000-01",
            )
            result["experience"] = [entry]
            add_provenance(provenance, "experience", "csv", "direct")
            confidences.append(0.9)
            if company:
                result["current_company"] = company
                add_provenance(provenance, "current_company", "csv", "direct")
            if title:
                result["current_title"] = title
                add_provenance(provenance, "current_title", "csv", "direct")

        if provenance:
            result["provenance"] = provenance
            result["overall_confidence"] = compute_overall_confidence(confidences, 0.9)
        return result
    except Exception:
        return empty_extract()
