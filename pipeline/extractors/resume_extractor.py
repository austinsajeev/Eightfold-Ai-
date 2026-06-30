"""Extract candidate fields from resume PDF/text."""

from __future__ import annotations

import re

import pdfplumber

from schema import ExperienceEntry, RawExtract

from pipeline.extractors._helpers import (
    add_provenance,
    compute_overall_confidence,
    empty_extract,
    find_emails,
    find_github_usernames,
    find_linkedin_urls,
    find_phones,
    guess_name_from_text,
)

_DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
    r"\s*[-–—to]+\s*"
    r"(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|Current)",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?P<year>\d{4})",
    re.IGNORECASE,
)
_YEAR_RANGE_RE = re.compile(r"(?P<start>\d{4})\s*[-–—]\s*(?P<end>\d{4}|Present|Current)", re.IGNORECASE)

_MONTHS = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

_CONFIDENCE = 0.6


def _to_year_month(token: str) -> str | None:
    token = token.strip()
    if token.lower() in {"present", "current"}:
        return None
    if re.fullmatch(r"\d{4}", token):
        return f"{token}-01"
    match = _MONTH_YEAR_RE.search(token)
    if not match:
        return None
    month = _MONTHS[match.group("month")[:3].lower()]
    return f"{match.group('year')}-{month}"


def _extract_experience_blocks(text: str) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        range_match = _DATE_RANGE_RE.search(block) or _YEAR_RANGE_RE.search(block)
        if not range_match:
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        title = lines[0]
        company = lines[1] if len(lines) > 1 else ""
        start = _to_year_month(range_match.group("start")) or "0000-01"
        end = _to_year_month(range_match.group("end"))
        entries.append(
            ExperienceEntry(
                company=company,
                title=title,
                start=start,
                end=end,
            )
        )
    return entries


def _read_pdf_text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract(path: str) -> RawExtract:
    try:
        text = _read_pdf_text(path)
        if not text.strip():
            return empty_extract()

        provenance = []
        confidences: list[float] = []
        result: RawExtract = {}

        emails = find_emails(text)
        if emails:
            result["email"] = emails[0]
            add_provenance(provenance, "email", "resume", "inferred")
            confidences.append(_CONFIDENCE)

        phones = find_phones(text)
        if phones:
            result["phone"] = phones[0]
            add_provenance(provenance, "phone", "resume", "inferred")
            confidences.append(_CONFIDENCE)

        linkedin_urls = find_linkedin_urls(text)
        if linkedin_urls:
            result["linkedin_url"] = linkedin_urls[0]
            add_provenance(provenance, "linkedin_url", "resume", "inferred")
            confidences.append(_CONFIDENCE)

        github_users = find_github_usernames(text)
        if github_users:
            result["github_username"] = github_users[0]
            add_provenance(provenance, "github_username", "resume", "inferred")
            confidences.append(_CONFIDENCE)

        name = guess_name_from_text(text)
        if name:
            result["full_name"] = name
            add_provenance(provenance, "full_name", "resume", "inferred")
            confidences.append(_CONFIDENCE)

        experience = _extract_experience_blocks(text)
        if experience:
            result["experience"] = experience
            add_provenance(provenance, "experience", "resume", "inferred")
            confidences.append(_CONFIDENCE)
            result["current_title"] = experience[0].title or None
            result["current_company"] = experience[0].company or None
            if result["current_title"]:
                add_provenance(provenance, "current_title", "resume", "inferred")
            if result["current_company"]:
                add_provenance(provenance, "current_company", "resume", "inferred")

        if provenance:
            result["provenance"] = provenance
            result["overall_confidence"] = compute_overall_confidence(confidences, _CONFIDENCE)
        return result
    except Exception:
        return empty_extract()
