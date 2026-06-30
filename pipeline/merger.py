"""Merge multiple RawExtract dicts into a single CandidateProfile."""

from __future__ import annotations

from rapidfuzz import fuzz

from schema import (
    CanonicalSkill,
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    MethodType,
    ProfileLinks,
    ProvenanceEntry,
    RawExtract,
    SourceType,
)

from pipeline.normalizers import normalize_date, normalize_email, normalize_phone, normalize_skill

SOURCE_PRIORITY: list[SourceType] = ["ats", "csv", "github", "resume", "notes"]

_SOURCE_ALIASES: dict[str, SourceType] = {
    "ats": "ats",
    "ats_json": "ats",
    "csv": "csv",
    "github": "github",
    "github_url": "github",
    "resume": "resume",
    "resume_pdf": "resume",
    "notes": "notes",
    "notes_txt": "notes",
}

METHOD_CONFIDENCE: dict[MethodType, float] = {
    "direct": 0.9,
    "api": 0.8,
    "inferred": 0.6,
    "regex": 0.7,
    "unavailable": 0.0,
}

SOURCE_CONFIDENCE: dict[SourceType, float] = {
    "ats": 0.7,
    "csv": 0.65,
    "github": 0.7,
    "resume": 0.6,
    "notes": 0.4,
}

_SCALAR_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "full_name",
    "headline",
    "location",
    "current_title",
    "current_company",
    "linkedin_url",
    "github_username",
    "summary",
    "recruiter_notes",
)

_PRIORITY_SCALAR_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "full_name",
    "headline",
    "location",
)

_EXPERIENCE_MATCH_THRESHOLD = 85


def _normalize_source(raw_source: str | None) -> SourceType | None:
    if not raw_source:
        return None
    return _SOURCE_ALIASES.get(raw_source.strip().lower())


def _source_rank(extract: RawExtract) -> int:
    source = _normalize_source(extract.get("_source"))
    if source is None:
        return len(SOURCE_PRIORITY)
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _sorted_extracts(extracts: list[RawExtract]) -> list[RawExtract]:
    return sorted(extracts, key=_source_rank)


def _get_method(extract: RawExtract, field: str) -> MethodType:
    for entry in extract.get("provenance") or []:
        if entry.field == field:
            return entry.method
    source = _normalize_source(extract.get("_source"))
    if source == "github":
        return "api"
    if source in {"csv", "ats"}:
        return "direct"
    if source in {"resume", "notes"}:
        return "inferred"
    return "inferred"


def _get_scalar_value(extract: RawExtract, field: str) -> object | None:
    if field == "candidate_id":
        value = extract.get("candidate_id")
        return value if value is not None and str(value).strip() else None
    return extract.get(field)


def _pick_scalar(
    extracts: list[RawExtract],
    field: str,
) -> tuple[object | None, SourceType | None, MethodType]:
    for extract in extracts:
        value = _get_scalar_value(extract, field)
        if value is not None and str(value).strip():
            source = _normalize_source(extract.get("_source"))
            if source is None:
                continue
            return value, source, _get_method(extract, field)
    return None, None, "unavailable"


def _record_scalar(
    field: str,
    value: object | None,
    source: SourceType | None,
    method: MethodType,
    provenance: list[ProvenanceEntry],
    field_confidences: dict[str, float],
) -> None:
    if value is None or source is None:
        if field in _PRIORITY_SCALAR_FIELDS:
            field_confidences[field] = 0.0
        return
    provenance.append(ProvenanceEntry(field=field, source=source, method=method))
    field_confidences[field] = METHOD_CONFIDENCE[method]


def _merge_emails(extracts: list[RawExtract]) -> tuple[list[str], SourceType | None, MethodType]:
    seen: set[str] = set()
    merged: list[str] = []
    winning_source: SourceType | None = None
    winning_method: MethodType = "unavailable"

    for extract in extracts:
        source = _normalize_source(extract.get("_source"))
        if source is None:
            continue
        raw_values: list[str] = []
        if extract.get("emails"):
            raw_values.extend(extract["emails"])
        if extract.get("email"):
            raw_values.append(extract["email"])

        for raw in raw_values:
            normalized = normalize_email(raw)
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(normalized)
                if winning_source is None:
                    winning_source = source
                    winning_method = _get_method(extract, "emails" if extract.get("emails") else "email")

    return merged, winning_source, winning_method


def _merge_phones(extracts: list[RawExtract]) -> tuple[list[str], SourceType | None, MethodType]:
    seen: set[str] = set()
    merged: list[str] = []
    winning_source: SourceType | None = None
    winning_method: MethodType = "unavailable"

    for extract in extracts:
        source = _normalize_source(extract.get("_source"))
        if source is None:
            continue
        raw_values: list[str] = []
        if extract.get("phones"):
            raw_values.extend(extract["phones"])
        if extract.get("phone"):
            raw_values.append(extract["phone"])

        for raw in raw_values:
            normalized = normalize_phone(raw)
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(normalized)
                if winning_source is None:
                    winning_source = source
                    winning_method = _get_method(extract, "phones" if extract.get("phones") else "phone")

    return merged, winning_source, winning_method


def _skill_confidence(sources: set[SourceType]) -> float:
    ranked = [source for source in SOURCE_PRIORITY if source in sources]
    if not ranked:
        return 0.5
    base = SOURCE_CONFIDENCE.get(ranked[0], 0.5)
    extra_source_count = max(len(sources) - 1, 0)
    return round(min(base + (0.1 * extra_source_count), 0.95), 2)


def _merge_skills(extracts: list[RawExtract]) -> list[CanonicalSkill]:
    sources_by_skill: dict[str, set[SourceType]] = {}

    for extract in extracts:
        source = _normalize_source(extract.get("_source"))
        if source is None:
            continue
        for skill in extract.get("skills") or []:
            name = normalize_skill(skill.name)
            if not name:
                continue
            sources_by_skill.setdefault(name, set()).add(source)

    merged: list[CanonicalSkill] = []
    for name in sorted(sources_by_skill):
        source_set = sources_by_skill[name]
        source_list = [source for source in SOURCE_PRIORITY if source in source_set]
        merged.append(
            CanonicalSkill(
                name=name,
                confidence=_skill_confidence(source_set),
                sources=source_list,
            )
        )
    return merged


def _experience_match_score(left: ExperienceEntry, right: ExperienceEntry) -> float:
    left_key = f"{left.company} {left.title}".strip().lower()
    right_key = f"{right.company} {right.title}".strip().lower()
    return float(fuzz.token_sort_ratio(left_key, right_key))


def _normalize_entry_dates(entry: ExperienceEntry) -> tuple[str, str | None]:
    start = normalize_date(entry.start) or entry.start
    end = normalize_date(entry.end) if entry.end else None
    return start, end


def _merge_experience_group(entries: list[ExperienceEntry]) -> tuple[ExperienceEntry, bool]:
    starts: list[str] = []
    ends: list[str | None] = []
    summaries: list[str] = []

    for entry in entries:
        start, end = _normalize_entry_dates(entry)
        starts.append(start)
        ends.append(end)
        summaries.append(entry.summary or "")

    date_conflict = len(set(starts)) > 1 or len({end for end in ends if end is not None}) > 1
    merged_start = min(starts)
    merged_end: str | None
    if any(end is None for end in ends):
        merged_end = None
    elif ends:
        merged_end = max(end for end in ends if end is not None)
    else:
        merged_end = None

    longest_summary = max(summaries, key=len) if summaries else ""
    anchor = entries[0]
    return (
        ExperienceEntry(
            company=anchor.company,
            title=anchor.title,
            start=merged_start,
            end=merged_end,
            summary=longest_summary or None,
        ),
        date_conflict,
    )


def _merge_experience(extracts: list[RawExtract]) -> tuple[list[ExperienceEntry], float | None]:
    groups: list[list[ExperienceEntry]] = []

    for extract in extracts:
        for entry in extract.get("experience") or []:
            matched = False
            for group in groups:
                if _experience_match_score(group[0], entry) >= _EXPERIENCE_MATCH_THRESHOLD:
                    group.append(entry)
                    matched = True
                    break
            if not matched:
                groups.append([entry])

    merged: list[ExperienceEntry] = []
    experience_confidence: float | None = None
    for group in groups:
        entry, date_conflict = _merge_experience_group(group)
        merged.append(entry)
        if date_conflict:
            experience_confidence = 0.5

    return merged, experience_confidence


def _merge_education(extracts: list[RawExtract]) -> list[EducationEntry]:
    seen: set[tuple[str, str, str]] = set()
    merged: list[EducationEntry] = []

    for extract in _sorted_extracts(extracts):
        for entry in extract.get("education") or []:
            key = (entry.institution.strip().lower(), entry.degree.strip().lower(), entry.field.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
    return merged


def _pick_links(extracts: list[RawExtract]) -> tuple[ProfileLinks | None, SourceType | None, MethodType]:
    for extract in extracts:
        links = extract.get("links")
        if links is None:
            continue
        source = _normalize_source(extract.get("_source"))
        if source is None:
            continue
        if isinstance(links, ProfileLinks):
            return links, source, _get_method(extract, "links")
        return ProfileLinks.model_validate(links), source, _get_method(extract, "links")
    return None, None, "unavailable"


def _first_source_with_field(
    extracts: list[RawExtract],
    field: str,
) -> tuple[SourceType | None, MethodType]:
    for extract in extracts:
        source = _normalize_source(extract.get("_source"))
        if source is None:
            continue
        if field == "experience" and extract.get("experience"):
            return source, _get_method(extract, "experience")
        if field == "education" and extract.get("education"):
            return source, _get_method(extract, "education")
        if field == "skills" and extract.get("skills"):
            return source, _get_method(extract, "skills")
    return None, "unavailable"


def _overall_confidence(field_confidences: dict[str, float]) -> float:
    non_zero = [value for value in field_confidences.values() if value > 0]
    if not non_zero:
        return 0.0
    return round(sum(non_zero) / len(non_zero), 2)


def merge(extracts: list[RawExtract]) -> CandidateProfile:
    """Merge extractor outputs into one canonical candidate profile."""
    ordered = _sorted_extracts(extracts)
    provenance: list[ProvenanceEntry] = []
    field_confidences: dict[str, float] = {}
    scalars: dict[str, object | None] = {}

    for field in _SCALAR_FIELDS:
        value, source, method = _pick_scalar(ordered, field)
        if field in _PRIORITY_SCALAR_FIELDS:
            scalars[field] = value
            _record_scalar(field, value, source, method, provenance, field_confidences)
        elif value is not None:
            scalars[field] = value
            _record_scalar(field, value, source, method, provenance, field_confidences)

    links, links_source, links_method = _pick_links(ordered)
    if links is not None and links_source is not None:
        provenance.append(ProvenanceEntry(field="links", source=links_source, method=links_method))
        field_confidences["links"] = METHOD_CONFIDENCE[links_method]

    emails, email_source, email_method = _merge_emails(ordered)
    if emails and email_source is not None:
        provenance.append(ProvenanceEntry(field="emails", source=email_source, method=email_method))
        field_confidences["emails"] = METHOD_CONFIDENCE[email_method]

    phones, phone_source, phone_method = _merge_phones(ordered)
    if phones and phone_source is not None:
        provenance.append(ProvenanceEntry(field="phones", source=phone_source, method=phone_method))
        field_confidences["phones"] = METHOD_CONFIDENCE[phone_method]

    skills = _merge_skills(ordered)
    if skills:
        skill_source, skill_method = _first_source_with_field(ordered, "skills")
        if skill_source is not None:
            provenance.append(ProvenanceEntry(field="skills", source=skill_source, method=skill_method))
        field_confidences["skills"] = round(
            sum(skill.confidence for skill in skills) / len(skills),
            2,
        )

    experience, experience_confidence = _merge_experience(ordered)
    if experience:
        exp_source, exp_method = _first_source_with_field(ordered, "experience")
        if exp_source is not None:
            provenance.append(ProvenanceEntry(field="experience", source=exp_source, method=exp_method))
        field_confidences["experience"] = (
            experience_confidence if experience_confidence is not None else METHOD_CONFIDENCE[exp_method]
        )

    education = _merge_education(ordered)
    if education:
        edu_source, edu_method = _first_source_with_field(ordered, "education")
        if edu_source is not None:
            provenance.append(ProvenanceEntry(field="education", source=edu_source, method=edu_method))
        field_confidences["education"] = METHOD_CONFIDENCE[edu_method]

    return CandidateProfile(
        candidate_id=scalars.get("candidate_id"),  # type: ignore[arg-type]
        full_name=scalars.get("full_name"),  # type: ignore[arg-type]
        emails=emails,
        phones=phones,
        location=scalars.get("location"),  # type: ignore[arg-type]
        headline=scalars.get("headline"),  # type: ignore[arg-type]
        links=links,
        current_title=scalars.get("current_title"),  # type: ignore[arg-type]
        current_company=scalars.get("current_company"),  # type: ignore[arg-type]
        linkedin_url=scalars.get("linkedin_url"),  # type: ignore[arg-type]
        github_username=scalars.get("github_username"),  # type: ignore[arg-type]
        summary=scalars.get("summary"),  # type: ignore[arg-type]
        skills=skills,
        experience=experience,
        education=education,
        recruiter_notes=scalars.get("recruiter_notes"),  # type: ignore[arg-type]
        provenance=provenance,
        overall_confidence=_overall_confidence(field_confidences),
    )
