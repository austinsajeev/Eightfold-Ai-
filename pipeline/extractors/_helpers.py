"""Shared helpers for extractors."""

from __future__ import annotations

import re
from typing import Any

from schema import MethodType, ProvenanceEntry, RawExtract, SourceType

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}(?:[-.\s]?\d{1,4})?"
)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w%-]+/?", re.IGNORECASE)
GITHUB_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})?)/?",
    re.IGNORECASE,
)

PROFILE_FIELDS: tuple[str, ...] = (
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


def empty_extract() -> RawExtract:
    return {field: None for field in PROFILE_FIELDS}  # type: ignore[misc]


def add_provenance(
    provenance: list[ProvenanceEntry],
    field: str,
    source: SourceType,
    method: MethodType,
) -> None:
    provenance.append(ProvenanceEntry(field=field, source=source, method=method))


def first_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        return first_scalar(value[0])
    if isinstance(value, dict):
        for key in ("email", "address", "value", "number"):
            if key in value and value[key]:
                return first_scalar(value[key])
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.split(";")[0].split(",")[0].strip() or None


def normalize_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key).strip().lstrip("\ufeff").lower(): value
        for key, value in row.items()
        if key is not None and str(key).strip()
    }


def get_by_aliases(data: dict[str, Any], aliases: list[str]) -> Any:
    normalized = normalize_keys(data) if not any("." in alias for alias in aliases) else data
    for alias in aliases:
        if "." in alias:
            value = _get_dotted(data, alias)
        else:
            value = normalized.get(alias.lower())
        if value not in (None, "", [], {}):
            return value
    return None


def _get_dotted(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def parse_github_username(url: str) -> str | None:
    text = url.strip().rstrip("/")
    if not text:
        return None
    if "github.com" in text.lower():
        match = GITHUB_URL_RE.search(text)
        if match:
            return match.group(1)
    text = text.lstrip("/")
    if text.lower().startswith("github.com/"):
        text = text[len("github.com/") :]
    username = text.split("/")[0].strip()
    if username and username.lower() not in {"orgs", "repos", "settings"}:
        return username
    return None


def find_emails(text: str) -> list[str]:
    return EMAIL_RE.findall(text)


def find_phones(text: str) -> list[str]:
    phones: list[str] = []
    for match in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= 7:
            phones.append(match.strip())
    return phones


def find_linkedin_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in LINKEDIN_RE.findall(text):
        url = match if match.startswith("http") else f"https://{match.lstrip('/')}"
        urls.append(url.rstrip("/"))
    return urls


def find_github_usernames(text: str) -> list[str]:
    return list(dict.fromkeys(GITHUB_URL_RE.findall(text)))


def guess_name_from_text(text: str) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or len(candidate) > 40:
            continue
        if EMAIL_RE.search(candidate) or PHONE_RE.search(candidate):
            continue
        if "http" in candidate.lower() or "www." in candidate.lower():
            continue
        if candidate.isupper() or candidate.istitle():
            return candidate
    return None


def compute_overall_confidence(confidences: list[float], default: float) -> float:
    if not confidences:
        return default
    return round(sum(confidences) / len(confidences), 3)
