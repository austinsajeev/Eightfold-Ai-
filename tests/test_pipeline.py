"""Pytest suite for the eightfold candidate pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import FieldSpec, OutputConfig
from pipeline.ingest import ingest
from pipeline.merger import merge
from pipeline.normalizers import normalize_extract, normalize_phone
from pipeline.projector import project
from schema import CandidateProfile, ProvenanceEntry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INPUTS = PROJECT_ROOT / "sample_inputs"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_full_pipeline(sources: list[dict]) -> CandidateProfile:
    extracts = ingest(sources)
    normalized = [normalize_extract(extract) for extract in extracts]
    return merge(normalized)


def test_gold_profile() -> None:
    sources = [
        {
            "type": "csv",
            "path": str(SAMPLE_INPUTS / "candidate_john.csv"),
            "candidate_id": "C001",
        },
        {
            "type": "ats_json",
            "path": str(SAMPLE_INPUTS / "candidate_john_ats.json"),
            "candidate_id": "C001",
        },
        {
            "type": "resume_pdf",
            "path": str(FIXTURES / "john_resume.pdf"),
            "candidate_id": "C001",
        },
        {
            "type": "notes_txt",
            "path": str(SAMPLE_INPUTS / "recruiter_notes.txt"),
            "candidate_id": "C001",
        },
    ]

    profile = run_full_pipeline(sources)

    assert profile.full_name == "Jonathan Smith"
    assert profile.phones
    assert profile.phones[0] == "+14155550101"
    assert "Python" in [skill.name for skill in profile.skills]
    assert profile.overall_confidence > 0.6
    assert any(entry.source == "csv" for entry in profile.provenance)


def test_missing_source_graceful() -> None:
    sources = [
        {
            "type": "csv",
            "path": str(SAMPLE_INPUTS / "candidate_john.csv"),
            "candidate_id": "C001",
        },
        {
            "type": "csv",
            "path": str(SAMPLE_INPUTS / "does_not_exist.csv"),
            "candidate_id": "C001",
        },
    ]

    profile = run_full_pipeline(sources)

    assert profile.full_name is not None
    assert profile.candidate_id == "C001"


def test_phone_normalization() -> None:
    expected = "+14155550101"
    assert normalize_phone("415-555-0101") == expected
    assert normalize_phone("(415) 555-0101") == expected
    assert normalize_phone("+1 415 555 0101") == expected
    assert normalize_phone("garbage123") is None


def test_conflict_resolution() -> None:
    ats_extract = {
        "_source": "ats_json",
        "full_name": "Jonathan Smith",
        "provenance": [
            ProvenanceEntry(field="full_name", source="ats", method="direct"),
        ],
    }
    csv_extract = {
        "_source": "csv",
        "full_name": "John Smith",
        "provenance": [
            ProvenanceEntry(field="full_name", source="csv", method="direct"),
        ],
    }

    profile = merge([normalize_extract(ats_extract), normalize_extract(csv_extract)])

    assert profile.full_name == "Jonathan Smith"


def test_projector_on_missing_omit() -> None:
    profile = CandidateProfile(full_name="John Smith", overall_confidence=0.8)
    config = OutputConfig(
        fields=[FieldSpec(path="headline", type="string")],
        include_confidence=False,
        include_provenance=False,
        on_missing="omit",
    )

    output = project(profile, config)

    assert "headline" not in output


def test_projector_on_missing_error() -> None:
    profile = CandidateProfile(full_name="John Smith", overall_confidence=0.8)
    config = OutputConfig(
        fields=[FieldSpec(path="headline", type="string", required=True)],
        include_confidence=False,
        include_provenance=False,
        on_missing="error",
    )

    with pytest.raises(ValueError):
        project(profile, config)
