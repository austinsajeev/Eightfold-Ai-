# eightfold-pipeline

A multi-source candidate data pipeline that ingests recruiter CSV exports, ATS JSON, GitHub profiles, resume PDFs, and recruiter notes; normalizes and merges them into a single canonical `CandidateProfile`; and projects that profile into a configurable JSON output schema with per-field provenance and confidence scoring.

**Repository:** https://github.com/austinsajeev/Eightfold-Ai-

## Demo video

[~2 min screen recording](https://drive.google.com/file/d/1pSN759dvYa9Rv9JslEGVJc4x7RrJwc5p/view) — pipeline run (default + custom config), design decision, edge case, and tests.

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

If you already have a virtual environment in the parent folder (`d:\eightfold\.venv`), activate that instead:

```powershell
..\.venv\Scripts\Activate.ps1
```

## Run on samples

John demo inputs (CSV + ATS + recruiter notes + resume PDF):

```powershell
$in = @(
  "sample_inputs/candidate_john.csv",
  "sample_inputs/candidate_john_ats.json",
  "sample_inputs/recruiter_notes.txt",
  "tests/fixtures/john_resume.pdf"
)
```

**Default projection** (built-in schema, no config file):

```powershell
python cli.py --inputs $in --pretty --output sample_outputs/default_output.json
```

**Custom projection** (`sample_config.json` — field renames, array projections):

```powershell
python cli.py --inputs $in --config sample_config.json --pretty --output sample_outputs/custom_output.json
```

**Assignment projection** (`assignment_config.json`):

```powershell
python cli.py --inputs $in --config assignment_config.json --pretty --output sample_outputs/assignment_output.json
```

Print to stdout instead of writing a file:

```powershell
python cli.py --inputs $in --config sample_config.json --pretty
```

## Sample outputs

Pre-generated JSON under `sample_outputs/` for the John demo inputs above:

| File | Config | Description |
|------|--------|-------------|
| `default_output.json` | *(none)* | Full canonical profile with per-field provenance and confidence |
| `custom_output.json` | `sample_config.json` | Renamed fields (`id`, `name`, `company`, …) and simplified `skills` array |
| `assignment_output.json` | `assignment_config.json` | Output shape aligned with the assignment example config |

Merged highlights (all three runs): `full_name` / `name` = **Jonathan Smith** (ATS wins over CSV), phones normalized to **E.164** (`+14155550101`), skills include **Python** from multiple corroborating sources.

Regenerate any file with the commands in [Run on samples](#run-on-samples).

## Run tests

```bash
pytest tests/ -v
```

## Project layout

| Path | Purpose |
|------|---------|
| `schema.py` | Pydantic models and `RawExtract` TypedDict |
| `config.py` | `OutputConfig` / `FieldSpec` and JSON loader |
| `cli.py` | Command-line entry point |
| `pipeline/ingest.py` | Route sources to extractors |
| `pipeline/normalizers.py` | Phone, date, skill, email normalization |
| `pipeline/merger.py` | Priority-based merge into `CandidateProfile` |
| `pipeline/projector.py` | Config-driven output projection |
| `pipeline/extractors/` | Per-source extractors |
| `sample_inputs/` | Example input files |
| `sample_outputs/` | Pre-generated demo JSON outputs |
| `sample_config.json` | Example output projection config |
| `assignment_config.json` | Assignment-style projection config |
| `tests/` | Pytest suite and resume PDF fixture |

## Design decisions

### Source priority

Sources are merged in fixed priority order:

`ats` → `csv` → `github` → `resume` → `notes`

ATS and CSV data are treated as the most authoritative for scalar fields (name, title, company) because they come from structured systems of record. GitHub and resume data enrich skills and experience heuristically. Recruiter notes are lowest priority — useful for contact hints and skill keywords, but noisy.

For array fields (`emails`, `phones`), values are unioned across all sources with higher-priority sources listed first, then deduplicated after normalization.

### Confidence scoring

Per-field confidence is derived from extraction method:

| Method | Score |
|--------|-------|
| `direct` | 0.9 |
| `api` | 0.8 |
| `regex` | 0.7 |
| `inferred` | 0.6 |
| `unavailable` | 0.0 |

Skills use source-trust baselines (`ats`/`github` 0.7, `csv` 0.65, `resume` 0.6, `notes` 0.4) plus +0.1 per additional corroborating source (capped at 0.95). `overall_confidence` is the mean of all non-zero field confidences.

### Projector as a separate layer

The merger produces one canonical internal model (`CandidateProfile`). The projector is a pure, side-effect-free transformation that maps that model into whatever output schema a downstream consumer needs — field renames, array projections, normalization (E.164 phones, canonical skill names), and missing-field policies (`null`, `omit`, `error`). Projected output is validated against each field's configured type before returning. This separation keeps merge logic stable while allowing different consumers (ATS export, search index, UI) to request different shapes without touching core pipeline code.

## Key design decision (proud of)

**Separating merge from projection.** The pipeline always builds one canonical `CandidateProfile` internally, then the projector reshapes it at runtime from `OutputConfig`. That means the same merged truth can produce the full default schema (with provenance and confidence), an assignment-style export (`primary_email`, `phone`, `skills[]`), or any other consumer shape — without duplicating merge logic or re-running extractors. Merge rules stay stable; only the final JSON view changes.

## Edge case handled

**Conflicting sources and missing inputs.** On the John demo, CSV has `John Smith` while ATS has `Jonathan Smith` — the merge picks **ATS** for scalar fields like name (`test_conflict_resolution`). For `emails` and `phones`, values are **unioned and deduplicated** after normalization (E.164 for phones), so nothing is silently dropped. If a source file is missing or corrupt, ingest returns a partial extract and the pipeline **does not crash** (`test_missing_source_graceful`). Unknown experience dates are left **`null`** rather than inventing placeholder values like `0000-01`.

## Known limitations / descoped items

- **LinkedIn** — not scraped; LinkedIn URLs may be extracted from resume text but profile data is not fetched (scraping restrictions and ToS).
- **Resume parsing** — heuristic regex and line-based rules, not ML/NLP; experience blocks and name detection are best-effort.
- **GitHub** — requires network access; rate limits and SSL issues can cause `unavailable` fallback.
- **Education** — extracted when present but not deeply structured from free text.
- **Multi-candidate batches** — CLI processes all `--inputs` as a single candidate; batch mode is out of scope.
