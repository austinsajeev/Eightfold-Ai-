"""Pydantic models and TypedDict definitions for the eightfold-pipeline."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

SourceType = Literal["csv", "ats", "github", "resume", "notes"]
MethodType = Literal["direct", "inferred", "api", "regex", "unavailable"]


class ProvenanceEntry(BaseModel):
    field: str
    source: SourceType
    method: MethodType


class CanonicalSkill(BaseModel):
    name: str
    confidence: float
    sources: list[str]


class ExperienceEntry(BaseModel):
    company: str
    title: str
    start: str | None = None  # YYYY-MM; null when unknown
    end: str | None = None  # YYYY-MM
    summary: str | None = None


class EducationEntry(BaseModel):
    institution: str
    degree: str
    field: str
    end_year: int | None = None


class ProfileLinks(BaseModel):
    portfolio: str | None = None


class CandidateProfile(BaseModel):
    """Canonical merged candidate profile (assignment output schema)."""

    candidate_id: str | None = None
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: str | None = None
    headline: str | None = None
    links: ProfileLinks | None = None
    current_title: str | None = None
    current_company: str | None = None
    linkedin_url: str | None = None
    github_username: str | None = None
    summary: str | None = None
    skills: list[CanonicalSkill] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    recruiter_notes: str | None = None
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    overall_confidence: float


class RawExtract(TypedDict, total=False):
    """Intermediate dict returned by each extractor; all fields optional."""

    candidate_id: str
    full_name: str
    email: str
    emails: list[str]
    phone: str
    phones: list[str]
    location: str
    headline: str
    links: ProfileLinks
    current_title: str
    current_company: str
    linkedin_url: str
    github_username: str
    summary: str
    skills: list[CanonicalSkill]
    experience: list[ExperienceEntry]
    education: list[EducationEntry]
    recruiter_notes: str
    provenance: list[ProvenanceEntry]
    overall_confidence: float
    _error: str
    _source: str
    _candidate_id: str
