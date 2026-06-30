"""Configuration for the eightfold-pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_INPUTS_DIR = PROJECT_ROOT / "sample_inputs"


class FieldSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    path: str
    type: str
    required: bool = False
    from_: Optional[str] = Field(None, alias="from")
    normalize: Optional[str] = None


class OutputConfig(BaseModel):
    fields: list[FieldSpec]
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: Literal["null", "omit", "error"] = "null"


def load_config(path: str) -> OutputConfig:
    with open(path, encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return OutputConfig.model_validate(data)


def default_config() -> OutputConfig:
    """Default projection schema: all profile fields."""
    field_names = [
        "candidate_id",
        "full_name",
        "emails",
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
    ]
    return OutputConfig(
        fields=[FieldSpec(path=name, type="auto") for name in field_names],
        include_confidence=True,
        include_provenance=True,
        on_missing="null",
    )
