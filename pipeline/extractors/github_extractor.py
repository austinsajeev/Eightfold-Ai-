"""Extract candidate fields from GitHub API / profile data."""

from __future__ import annotations

from collections import Counter

import requests

from schema import CanonicalSkill, ProfileLinks, RawExtract

from pipeline.extractors._helpers import (
    add_provenance,
    compute_overall_confidence,
    empty_extract,
    parse_github_username,
)

_USER_URL = "https://api.github.com/users/{username}"
_REPOS_URL = "https://api.github.com/users/{username}/repos"
_TIMEOUT = 10


def _get_json(url: str) -> dict | list | None:
    try:
        response = requests.get(
            url,
            timeout=_TIMEOUT,
            headers={"Accept": "application/vnd.github+json"},
        )
        if response.status_code in {403, 404}:
            return None
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _language_counts(repos: list) -> Counter[str]:
    counts: Counter[str] = Counter()
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        language = repo.get("language")
        if language:
            counts[str(language)] += 1
    return counts


def _skills_from_counts(language_counts: Counter[str]) -> list[CanonicalSkill]:
    skills: list[CanonicalSkill] = []
    for language, repo_count in language_counts.most_common(10):
        confidence = min(0.5 + (repo_count * 0.05), 0.9)
        skills.append(
            CanonicalSkill(name=language, confidence=confidence, sources=["github"])
        )
    return skills


def extract(url: str) -> RawExtract:
    try:
        username = parse_github_username(url)
        if not username:
            return _unavailable_extract()

        profile = _get_json(_USER_URL.format(username=username))
        if not isinstance(profile, dict):
            return _unavailable_extract()

        provenance = []
        confidences: list[float] = []
        result: RawExtract = {"github_username": username}
        add_provenance(provenance, "github_username", "github", "api")
        confidences.append(0.8)

        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            result["full_name"] = name.strip()
            add_provenance(provenance, "full_name", "github", "api")
            confidences.append(0.75)

        bio = profile.get("bio")
        if isinstance(bio, str) and bio.strip():
            result["headline"] = bio.strip()
            add_provenance(provenance, "headline", "github", "api")
            confidences.append(0.7)

        location = profile.get("location")
        if isinstance(location, str) and location.strip():
            result["location"] = location.strip()
            add_provenance(provenance, "location", "github", "api")
            confidences.append(0.75)

        blog = profile.get("blog")
        if isinstance(blog, str) and blog.strip():
            result["links"] = ProfileLinks(portfolio=blog.strip())
            add_provenance(provenance, "links", "github", "api")
            confidences.append(0.75)

        public_email = profile.get("email") or profile.get("public_email")
        if isinstance(public_email, str) and public_email.strip():
            result["emails"] = [public_email.strip()]
            add_provenance(provenance, "emails", "github", "api")
            confidences.append(0.8)

        repos = _get_json(
            f"{_REPOS_URL.format(username=username)}?per_page=10&sort=updated"
        )
        if isinstance(repos, list):
            language_counts = _language_counts(repos)
            skills = _skills_from_counts(language_counts)
            if skills:
                result["skills"] = skills
                add_provenance(provenance, "skills", "github", "api")
                confidences.extend(skill.confidence for skill in skills)

        result["provenance"] = provenance
        result["overall_confidence"] = compute_overall_confidence(confidences, 0.7)
        return result
    except Exception:
        return _unavailable_extract()


def _unavailable_extract() -> RawExtract:
    result = empty_extract()
    result["provenance"] = []
    for field in (
        "full_name",
        "headline",
        "location",
        "links",
        "emails",
        "github_username",
        "skills",
    ):
        add_provenance(result["provenance"], field, "github", "unavailable")
    result["overall_confidence"] = 0.0
    return result
