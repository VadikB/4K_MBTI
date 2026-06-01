from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Api.database import get_connection


SUMMARY_SQL = """
SELECT
    domain_family,
    status,
    COUNT(*) AS candidate_count,
    MAX(quality_score) AS max_quality,
    SUM(sample_count) AS sample_total
FROM domain_case_scene_candidates
GROUP BY domain_family, status
ORDER BY domain_family, status
"""


DETAIL_SQL = """
SELECT
    id,
    domain_family,
    case_type_code,
    incident_title,
    problem_event,
    expected_step,
    quality_score,
    quality_notes,
    status,
    sample_count,
    last_seen_at
FROM domain_case_scene_candidates
WHERE (%s::text IS NULL OR domain_family = %s::text)
ORDER BY domain_family, quality_score DESC, sample_count DESC, incident_title ASC
"""


def _render_report(rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Scene Candidates Review")
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    if not summary_rows:
        lines.append("Нет candidate-сцен.")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Домен | Статус | Кол-во сцен | Макс. quality | Сумма sample_count |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in summary_rows:
        lines.append(
            f"| {row['domain_family']} | {row['status']} | {row['candidate_count']} | "
            f"{row['max_quality'] or 0} | {row['sample_total'] or 0} |"
        )
    lines.append("")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["domain_family"])].append(row)

    for domain_family, domain_rows in grouped.items():
        lines.append(f"## {domain_family}")
        lines.append("")
        for status in ("suggested", "review", "rejected", "new"):
            status_rows = [row for row in domain_rows if str(row["status"]) == status]
            if not status_rows:
                continue
            lines.append(f"### {status}")
            lines.append("")
            for row in status_rows:
                notes = ", ".join(row.get("quality_notes") or []) or "-"
                lines.append(
                    f"- `#{row['id']}` [{row['quality_score']}] "
                    f"`{row['case_type_code'] or '-'}` {row['incident_title']}"
                )
                lines.append(f"  Проблема: {row['problem_event']}")
                lines.append(f"  Следующий шаг: {row['expected_step']}")
                lines.append(
                    f"  Sample count: {row['sample_count']}; quality notes: {notes}; "
                    f"last seen: {row['last_seen_at']}"
                )
            lines.append("")

    return "\n".join(lines)


def export_scene_candidate_review(output_path: Path, *, domain_family: str | None = None) -> Path:
    with get_connection() as connection:
        cur = connection.cursor()
        cur.execute(SUMMARY_SQL)
        summary_rows = cur.fetchall()
        cur.execute(DETAIL_SQL, (domain_family, domain_family))
        rows = cur.fetchall()

    report_text = _render_report(rows, summary_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export domain case scene candidate review report.")
    parser.add_argument(
        "--output",
        required=True,
        help="Absolute path to the markdown output file.",
    )
    parser.add_argument(
        "--domain-family",
        default=None,
        help="Optional domain family filter.",
    )
    args = parser.parse_args()
    output_path = Path(args.output).expanduser().resolve()
    result = export_scene_candidate_review(output_path, domain_family=args.domain_family)
    print(result)


if __name__ == "__main__":
    main()
