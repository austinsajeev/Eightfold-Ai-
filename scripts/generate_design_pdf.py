"""Generate the one-page Step-1 design PDF for the Eightfold assignment."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "AustinSajeevAbraham_austin.sajeev@btech.christuniversity.in_Eightfold.pdf"
)


class DesignPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.set_margins(11, 12, 11)

    @property
    def content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header_block(self) -> None:
        self.set_font("Helvetica", "B", 10.5)
        self.cell(
            self.content_width,
            4.5,
            "Multi-Source Candidate Data Transformer - Technical Design",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.set_font("Helvetica", "", 7.5)
        self.cell(
            self.content_width,
            4,
            "Austin Sajeev Abraham | Eightfold Engineering Intern Assignment | Step 1",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.ln(1)

    def section(self, title: str) -> None:
        self.set_font("Helvetica", "B", 8)
        self.cell(self.content_width, 3.8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 7)

    def bullet(self, text: str) -> None:
        self.multi_cell(self.content_width, 2.9, f"- {text}")


def build_pdf(path: Path) -> None:
    pdf = DesignPDF()
    pdf.add_page()
    pdf.header_block()

    pdf.section("1. Pipeline")
    pdf.bullet("detect: extension or explicit type -> csv | ats_json | github_url | resume_pdf | notes_txt")
    pdf.bullet("extract: per-source extractor; failures return partial RawExtract, never raise")
    pdf.bullet("normalize: E.164 phones, lowercase emails, canonical skills, YYYY-MM dates")
    pdf.bullet("merge: priority union into CandidateProfile + per-field provenance")
    pdf.bullet("confidence: method weights + skill source-trust; overall = mean of field scores")
    pdf.bullet("project: OutputConfig maps canonical profile to consumer JSON (pure transform)")

    pdf.section("2. Canonical Schema and Formats")
    pdf.bullet("Fields: candidate_id, full_name, emails[], phones[] (E.164), headline, skills[], experience[], education[]")
    pdf.bullet("Skills: alias map (py/Python, js/JavaScript, k8s/Kubernetes); title-case unknowns")
    pdf.bullet("Dates: YYYY-MM; Present/Current -> null end date")
    pdf.bullet("Location: comma-split {city, region, country}; expand US/UK/IN abbreviations")

    pdf.section("3. Merge / Conflict Policy")
    pdf.bullet("Priority: ats > csv > github > resume > notes")
    pdf.bullet("Scalars: first non-null from highest-priority source")
    pdf.bullet("emails/phones: union + dedupe; priority-source values listed first")
    pdf.bullet("Skills: union by canonical name; conf = source_trust + 0.1 per extra source (max 0.95)")
    pdf.bullet("Experience: fuzzy match company+title (score>=85); merge date range; 0.5 if dates conflict")

    pdf.section("4. Runtime Custom Output")
    pdf.bullet("OutputConfig: field paths, optional from-remap, normalize (E164/canonical), on_missing null|omit|error")
    pdf.bullet("Supports emails[0], skills[].name; toggles confidence and provenance in output")
    pdf.bullet("Projector does not mutate canonical record - multiple schemas from one merge")

    pdf.section("5. Edge Cases")
    pdf.bullet("Bad/missing file: skip with error extract; other sources still merge")
    pdf.bullet("Name conflict ATS vs CSV: ATS wins scalar; both emails retained")
    pdf.bullet("Duplicate phones in different formats: one E.164 after normalization")
    pdf.bullet("GitHub API failure: unavailable provenance, null fields, no crash")
    pdf.bullet("Sparse resume PDF: heuristic extraction may yield partial experience only")

    pdf.section("6. Descoped")
    pdf.bullet("LinkedIn fetch; ISO country codes; years_experience; ML resume parsing; multi-candidate batch")
    pdf.bullet("DOCX resumes; full links object; post-projection JSON Schema validator")

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


if __name__ == "__main__":
    build_pdf(OUTPUT)
    print(f"Wrote {OUTPUT}")
