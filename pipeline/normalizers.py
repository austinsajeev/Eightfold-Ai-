"""Normalize raw field values (phones, dates, names, skills)."""

from __future__ import annotations

import re
from datetime import datetime

import phonenumbers
from dateutil import parser as date_parser
from phonenumbers.phonenumberutil import NumberParseException

_CANONICAL_SKILLS: dict[str, str] = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "py": "Python",
    "python": "Python",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "react.js": "React",
    "react": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
}

_COUNTRY_ABBREVS: dict[str, str] = {
    "us": "United States",
    "usa": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "in": "India",
}

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w+$", re.IGNORECASE)
_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_ONLY_RE = re.compile(r"^(\d{4})$")
_MM_YYYY_RE = re.compile(r"^(\d{1,2})/(\d{4})$")
_PRESENT_RE = re.compile(r"^(present|current)$", re.IGNORECASE)


def normalize_phone(raw: str, default_country: str = "US") -> str | None:
    if not raw or not str(raw).strip():
        return None

    text = str(raw).strip()
    for region in (default_country, None):
        try:
            number = phonenumbers.parse(text, region)
            if phonenumbers.is_valid_number(number):
                return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            continue
    return None


def normalize_date(raw: str) -> str | None:
    if not raw or not str(raw).strip():
        return None

    text = str(raw).strip()
    if _PRESENT_RE.fullmatch(text):
        return None

    year_month_match = _YEAR_MONTH_RE.fullmatch(text)
    if year_month_match:
        year, month = int(year_month_match.group(1)), int(year_month_match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
        return None

    mm_yyyy_match = _MM_YYYY_RE.fullmatch(text)
    if mm_yyyy_match:
        month, year = int(mm_yyyy_match.group(1)), int(mm_yyyy_match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
        return None

    year_only_match = _YEAR_ONLY_RE.fullmatch(text)
    if year_only_match:
        return f"{int(year_only_match.group(1)):04d}-01"

    try:
        parsed = date_parser.parse(text, default=datetime(1900, 1, 1))
        return f"{parsed.year:04d}-{parsed.month:02d}"
    except (ValueError, OverflowError, TypeError):
        return None


def normalize_skill(raw: str) -> str:
    if not raw:
        return ""

    key = str(raw).strip().lower()
    if not key:
        return ""

    return _CANONICAL_SKILLS.get(key, str(raw).strip().title())


def _normalize_country(value: str) -> str:
    stripped = value.strip()
    mapped = _COUNTRY_ABBREVS.get(stripped.lower())
    return mapped if mapped else stripped


def normalize_location(raw: str) -> dict | None:
    if not raw or not str(raw).strip():
        return None

    parts = [part.strip() for part in str(raw).split(",") if part.strip()]
    if not parts:
        return None

    if len(parts) == 1:
        return {"city": parts[0], "region": None, "country": None}
    if len(parts) == 2:
        return {
            "city": parts[0],
            "region": None,
            "country": _normalize_country(parts[1]),
        }
    return {
        "city": parts[0],
        "region": parts[1],
        "country": _normalize_country(parts[2]),
    }


def normalize_email(raw: str) -> str | None:
    if not raw or not str(raw).strip():
        return None

    email = str(raw).strip().lower()
    if _EMAIL_RE.fullmatch(email):
        return email
    return None


def normalize_extract(extract: dict) -> dict:
    """Normalize fields on a single RawExtract before merging."""
    from schema import CanonicalSkill, ExperienceEntry, RawExtract

    result: RawExtract = dict(extract)  # type: ignore[assignment]

    if result.get("email"):
        normalized = normalize_email(str(result["email"]))
        result["email"] = normalized

    if result.get("emails"):
        result["emails"] = [
            email
            for email in (normalize_email(str(value)) for value in result["emails"])
            if email
        ]

    if result.get("phone"):
        result["phone"] = normalize_phone(str(result["phone"]))

    if result.get("phones"):
        result["phones"] = [
            phone
            for phone in (normalize_phone(str(value)) for value in result["phones"])
            if phone
        ]

    if result.get("location"):
        location = normalize_location(str(result["location"]))
        if location:
            parts = [location.get("city"), location.get("region"), location.get("country")]
            result["location"] = ", ".join(part for part in parts if part)

    skills = result.get("skills") or []
    normalized_skills: list[CanonicalSkill] = []
    for skill in skills:
        if isinstance(skill, CanonicalSkill):
            normalized_skills.append(
                skill.model_copy(update={"name": normalize_skill(skill.name)})
            )
        else:
            normalized_skills.append(
                CanonicalSkill(
                    name=normalize_skill(str(skill.get("name", ""))),
                    confidence=float(skill.get("confidence", 0.5)),
                    sources=list(skill.get("sources", [])),
                )
            )
    if normalized_skills:
        result["skills"] = normalized_skills

    experience = result.get("experience") or []
    normalized_experience: list[ExperienceEntry] = []
    for entry in experience:
        if isinstance(entry, ExperienceEntry):
            start = normalize_date(entry.start) or entry.start
            end = normalize_date(entry.end) if entry.end else None
            normalized_experience.append(entry.model_copy(update={"start": start, "end": end}))
        else:
            start = normalize_date(str(entry.get("start", ""))) or str(entry.get("start", "0000-01"))
            end_raw = entry.get("end")
            end = normalize_date(str(end_raw)) if end_raw else None
            normalized_experience.append(
                ExperienceEntry(
                    company=str(entry.get("company", "")),
                    title=str(entry.get("title", "")),
                    start=start,
                    end=end,
                    summary=entry.get("summary"),
                )
            )
    if normalized_experience:
        result["experience"] = normalized_experience

    return result
