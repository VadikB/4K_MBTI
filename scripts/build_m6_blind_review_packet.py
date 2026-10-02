"""Build the review input without Codex draft analysis or reviewer conclusions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/m6_gc/v1/candidates"
OUTPUT = ROOT / "tests/fixtures/m6_gc/v1/blind_review"
ALLOWED = (
    "id",
    "version",
    "status",
    "group",
    "purpose",
    "synthetic",
    "as_snapshot",
    "material",
    "review_scope",
    "unreviewed_targets",
    "semantic_expectations",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for source in sorted(SOURCE.glob("*.json")):
        candidate = json.loads(source.read_text())
        blind = {key: candidate[key] for key in ALLOWED}
        blind["review_instructions"] = {
            "draft_analysis_available": False,
            "independent_first_opinion_required": True,
            "scope": "M6-A Fragment/BS/Evidence/EB; no IA, IE, L0-L3, Score or C-54",
            "assignment": "docs/evc/tasks/m6-task02/review-assignments.md",
        }
        destination = OUTPUT / source.name
        destination.write_text(json.dumps(blind, ensure_ascii=False, indent=2) + "\n")
        records.append({
            "candidate_id": candidate["id"],
            "source_path": str(source.relative_to(ROOT)),
            "source_sha256": digest(source),
            "review_path": str(destination.relative_to(ROOT)),
            "review_sha256": digest(destination),
        })
    manifest = {
        "kind": "m6_blind_independent_review_packet",
        "version": "0.1",
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "generated_from": "tests/fixtures/m6_gc/v1/candidates",
        "contains_draft_analysis": False,
        "contains_personal_contacts": False,
        "reviewer_assignments": "docs/evc/tasks/m6-task02/review-assignments.md",
        "records": records,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    build()
