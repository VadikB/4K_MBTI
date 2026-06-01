from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Api.database import get_connection


CANDIDATE_SELECT_SQL = """
SELECT
    id,
    domain_family,
    case_type_code,
    incident_title,
    problem_event,
    expected_step,
    risk,
    constraint_text,
    source_payload,
    quality_score,
    quality_notes,
    status,
    sample_count
FROM domain_case_scene_candidates
WHERE (%s::int[] IS NULL OR id = ANY(%s::int[]))
  AND (%s::text IS NULL OR domain_family = %s::text)
  AND (%s::text IS NULL OR status = %s::text)
ORDER BY quality_score DESC, sample_count DESC, id ASC
LIMIT %s
"""


def _derive_keywords(candidate: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    for source in (
        candidate.get("incident_title"),
        candidate.get("problem_event"),
        *(candidate.get("source_payload") or {}).get("work_items", []),
    ):
        for token in str(source or "").lower().replace("«", " ").replace("»", " ").split():
            token = token.strip(".,:;!?()[]{}\"'")
            if len(token) < 4:
                continue
            parts.append(token[:24])
    deduped: list[str] = []
    seen: set[str] = set()
    for token in parts:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped[:8]


def _derive_situation_code(candidate: dict[str, Any]) -> str:
    family = str(candidate["domain_family"]).strip().lower()
    title = str(candidate["incident_title"]).strip().lower()
    digest = hashlib.sha1(f"{family}|{title}".encode("utf-8")).hexdigest()[:10]
    prefix = family[:18].rstrip("_")
    return f"{prefix}_cand_{digest}"


def promote_scene_candidates(
    *,
    candidate_ids: list[int] | None,
    domain_family: str | None,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    promoted: list[dict[str, Any]] = []
    with get_connection() as connection:
        cur = connection.cursor()
        ids_param = candidate_ids if candidate_ids else None
        cur.execute(
            CANDIDATE_SELECT_SQL,
            (
                ids_param,
                ids_param,
                domain_family,
                domain_family,
                status,
                status,
                max(1, limit),
            ),
        )
        candidates = cur.fetchall()
        for candidate in candidates:
            situation_code = _derive_situation_code(candidate)
            keywords = _derive_keywords(candidate)
            priority = max(10, 100 - int(candidate.get("quality_score") or 0))
            connection.execute(
                """
                INSERT INTO domain_case_situations (
                    domain_family,
                    situation_code,
                    priority,
                    keywords,
                    problem_event,
                    expected_step,
                    risk,
                    constraint_text,
                    is_active,
                    version,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, TRUE, 1, NOW(), NOW())
                ON CONFLICT (domain_family, situation_code) DO UPDATE
                SET
                    priority = EXCLUDED.priority,
                    keywords = EXCLUDED.keywords,
                    problem_event = EXCLUDED.problem_event,
                    expected_step = EXCLUDED.expected_step,
                    risk = EXCLUDED.risk,
                    constraint_text = EXCLUDED.constraint_text,
                    is_active = TRUE,
                    updated_at = NOW()
                """,
                (
                    candidate["domain_family"],
                    situation_code,
                    priority,
                    json.dumps(keywords, ensure_ascii=False),
                    candidate["problem_event"],
                    candidate["expected_step"],
                    candidate["risk"],
                    candidate["constraint_text"],
                ),
            )
            case_type_code = str(candidate.get("case_type_code") or "").strip().upper()
            if case_type_code:
                connection.execute(
                    """
                    INSERT INTO case_type_domain_situations (
                        type_code,
                        domain_family,
                        situation_code,
                        is_active,
                        version,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, TRUE, 1, NOW(), NOW())
                    ON CONFLICT (type_code, domain_family, situation_code) DO UPDATE
                    SET is_active = TRUE,
                        updated_at = NOW()
                    """,
                    (case_type_code, candidate["domain_family"], situation_code),
                )
            connection.execute(
                """
                UPDATE domain_case_scene_candidates
                SET status = 'promoted',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (candidate["id"],),
            )
            promoted.append(
                {
                    "candidate_id": candidate["id"],
                    "domain_family": candidate["domain_family"],
                    "case_type_code": case_type_code or None,
                    "incident_title": candidate["incident_title"],
                    "situation_code": situation_code,
                    "quality_score": candidate["quality_score"],
                }
            )
        connection.commit()
    return promoted


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote scene candidates into domain_case_situations.")
    parser.add_argument("--candidate-id", dest="candidate_ids", action="append", type=int, default=[])
    parser.add_argument("--domain-family", default=None)
    parser.add_argument("--status", default="suggested")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    promoted = promote_scene_candidates(
        candidate_ids=args.candidate_ids or None,
        domain_family=args.domain_family,
        status=args.status,
        limit=args.limit,
    )
    for item in promoted:
        print(
            f"#{item['candidate_id']} | {item['domain_family']} | "
            f"{item['case_type_code'] or '-'} | {item['situation_code']} | "
            f"{item['incident_title']} | q={item['quality_score']}"
        )


if __name__ == "__main__":
    main()
