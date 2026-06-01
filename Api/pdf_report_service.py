from __future__ import annotations

from collections import defaultdict

from Api.database import get_level_percent_map
from Api.report_growth_logic import (
    ZERO_SIGNAL_RECOMMENDATIONS,
    WEAK_SIGNAL_RECOMMENDATIONS,
    build_ai_insight_copy,
    build_competency_growth_recommendation,
    build_interpretation_basis_items,
    build_response_pattern_text,
)
from Api.typst_pdf_renderer import render_typst_competency_report


class PdfReportService:
    def _load_user(self, connection, user_id: int):
        row = connection.execute(
            """
            SELECT u.id, u.full_name, u.job_description, u.phone
            FROM users u
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def _load_assessments(self, connection, user_id: int, session_id: int) -> list[dict]:
        rows = connection.execute(
            """
            SELECT
                competency_name,
                skill_code,
                skill_name,
                assessed_level_code,
                assessed_level_name,
                rationale,
                evidence_excerpt,
                red_flags,
                found_evidence,
                block_coverage_percent,
                (
                    SELECT ROUND(AVG(scsa.artifact_compliance_percent))::int
                    FROM session_case_skill_analysis scsa
                    WHERE scsa.session_id = session_skill_assessments.session_id
                      AND scsa.user_id = session_skill_assessments.user_id
                      AND scsa.skill_id = session_skill_assessments.skill_id
                      AND scsa.artifact_compliance_percent IS NOT NULL
                ) AS artifact_compliance_percent
            FROM session_skill_assessments
            WHERE user_id = %s
              AND session_id = %s
            ORDER BY competency_name ASC, skill_code ASC NULLS LAST, skill_name ASC
            """,
            (user_id, session_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def _parse_json_array_field(self, value) -> list:
        if not value:
            return []
        if isinstance(value, list):
            return value
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def _build_signal_metrics(self, rows: list[dict]) -> dict[str, float]:
        if not rows:
            return {
                "evidence_hit_rate": 0.0,
                "avg_block_coverage": 0.0,
                "avg_artifact_compliance": 0.0,
                "avg_red_flag_count": 0.0,
            }

        evidence_hits = 0
        block_values: list[float] = []
        artifact_values: list[float] = []
        red_flag_total = 0

        for row in rows:
            if self._parse_json_array_field(row.get("found_evidence")):
                evidence_hits += 1
            if row.get("block_coverage_percent") is not None:
                block_values.append(float(row["block_coverage_percent"]))
            if row.get("artifact_compliance_percent") is not None:
                artifact_values.append(float(row["artifact_compliance_percent"]))
            red_flag_total += len(self._parse_json_array_field(row.get("red_flags")))

        return {
            "evidence_hit_rate": evidence_hits / len(rows),
            "avg_block_coverage": sum(block_values) / len(block_values) if block_values else 0.0,
            "avg_artifact_compliance": sum(artifact_values) / len(artifact_values) if artifact_values else 0.0,
            "avg_red_flag_count": red_flag_total / len(rows),
        }

    def _has_enough_interpretation_signal(self, grouped_rows: list[dict], rows: list[dict]) -> bool:
        if not grouped_rows or not any(item["avg_percent"] > 0 for item in grouped_rows):
            return False
        metrics = self._build_signal_metrics(rows)
        return (
            metrics["evidence_hit_rate"] >= 0.2
            and metrics["avg_block_coverage"] >= 25
            and metrics["avg_artifact_compliance"] >= 25
            and metrics["avg_red_flag_count"] <= 4
        )

    def _calculate_insight_score(self, item: dict) -> int:
        metrics = item.get("metrics", {})
        return round(
            item["avg_percent"] * 0.5
            + metrics.get("evidence_hit_rate", 0) * 100 * 0.2
            + metrics.get("avg_block_coverage", 0) * 0.15
            + metrics.get("avg_artifact_compliance", 0) * 0.15
            - min(metrics.get("avg_red_flag_count", 0) * 10, 40)
        )

    def _select_strongest_competency(self, grouped_rows: list[dict]) -> tuple[dict | None, bool]:
        if not grouped_rows:
            return None, False
        ranked = sorted(
            grouped_rows,
            key=lambda item: (self._calculate_insight_score(item), item["avg_percent"]),
            reverse=True,
        )
        strongest = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        gap = self._calculate_insight_score(strongest) - self._calculate_insight_score(second) if second else 999
        is_confident = self._calculate_insight_score(strongest) >= 35 and gap >= 5
        return strongest, is_confident

    def _group_by_competency(self, rows: list[dict], level_percent_map: dict[str, int]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row["competency_name"] or "Без категории"].append(row)

        result: list[dict] = []
        for competency_name, skills in grouped.items():
            avg_percent = round(
                sum(level_percent_map.get(skill["assessed_level_code"], 0) for skill in skills) / len(skills)
            )
            evidence_hits = sum(1 for skill in skills if self._parse_json_array_field(skill.get("found_evidence")))
            block_values = [float(skill["block_coverage_percent"]) for skill in skills if skill.get("block_coverage_percent") is not None]
            artifact_values = [float(skill["artifact_compliance_percent"]) for skill in skills if skill.get("artifact_compliance_percent") is not None]
            red_flag_total = sum(len(self._parse_json_array_field(skill.get("red_flags"))) for skill in skills)
            result.append(
                {
                    "competency_name": competency_name,
                    "skills": skills,
                    "avg_percent": avg_percent,
                    "metrics": {
                        "evidence_hit_rate": evidence_hits / len(skills),
                        "avg_block_coverage": sum(block_values) / len(block_values) if block_values else 0.0,
                        "avg_artifact_compliance": sum(artifact_values) / len(artifact_values) if artifact_values else 0.0,
                        "avg_red_flag_count": red_flag_total / len(skills),
                    },
                }
            )
        result.sort(key=lambda item: item["competency_name"])
        return result

    def _build_recommendations(self, grouped_rows: list[dict]) -> list[str]:
        if not any(item["avg_percent"] > 0 for item in grouped_rows):
            return list(ZERO_SIGNAL_RECOMMENDATIONS)
        weakest = sorted(grouped_rows, key=lambda item: item["avg_percent"])[:3]
        recommendations = [
            build_competency_growth_recommendation(item["competency_name"], item.get("metrics", {}))
            for item in weakest
        ]
        return recommendations or ["Завершите полный цикл оценки, чтобы получить персональные рекомендации."]

    def _is_meaningful_quote_candidate(self, value: str) -> bool:
        normalized = " ".join(str(value or "").split())
        if len(normalized) < 24:
            return False
        generic_markers = (
            "оценка сформирована",
            "структурным признакам",
            "по рубрике",
            "недостаточно данных",
        )
        return not any(marker in normalized.lower() for marker in generic_markers)

    def _build_strengths(
        self,
        *,
        strongest: dict | None,
        has_confident_strongest: bool,
        response_pattern: str,
    ) -> list[str]:
        strengths: list[str] = []
        if strongest and has_confident_strongest:
            strengths.append(
                f"Наиболее устойчиво проявлена компетенция «{strongest['competency_name']}»: "
                f"средний показатель составил {strongest['avg_percent']}%."
            )
        if response_pattern:
            strengths.append(response_pattern)
        return strengths or ["Выраженная сильная сторона пока не выделена: для этого нужны более устойчивые сигналы по сессии."]

    def _build_quotes(self, rows: list[dict]) -> list[str]:
        quotes: list[str] = []
        seen_quotes: set[str] = set()
        for row in rows:
            candidate = str(row.get("evidence_excerpt") or row.get("rationale") or "").strip()
            normalized_candidate = " ".join(candidate.split()).lower()
            if (
                candidate
                and normalized_candidate
                and normalized_candidate not in seen_quotes
                and self._is_meaningful_quote_candidate(candidate)
            ):
                seen_quotes.add(normalized_candidate)
                quotes.append(candidate)
            if len(quotes) >= 3:
                break
        return quotes

    def _build_typst_payload(
        self,
        *,
        user: dict,
        session_id: int,
        grouped_rows: list[dict],
        level_percent_map: dict[str, int],
        overall_score: int,
        insight_title: str,
        insight_text: str,
        basis_items: list[str],
        recommendations: list[str],
        strengths: list[str],
        growth_areas: list[str],
        quotes: list[str],
    ) -> dict:
        competencies = []
        for item in grouped_rows:
            avg_percent = int(item["avg_percent"])
            competencies.append(
                {
                    "name": str(item["competency_name"]),
                    "avg_percent": avg_percent,
                    "interpretation": (
                        "Высокий потенциал" if avg_percent >= 80 else
                        "Стабильный уровень" if avg_percent >= 55 else
                        "Требует развития"
                    ),
                    "skills": [
                        {
                            "name": str(skill.get("skill_name") or "Навык"),
                            "level": str(skill.get("assessed_level_name") or "Не определен"),
                            "percent": int(level_percent_map.get(skill.get("assessed_level_code"), 0)),
                            "rationale": str(
                                skill.get("rationale")
                                or "Оценка сформирована по рубрике и структурным признакам ответа."
                            ),
                        }
                        for skill in item["skills"]
                    ],
                }
            )

        return {
            "title": "Профиль компетенций 4K Assistant",
            "subtitle": "Глубокий анализ оценок по четырем направлениям и детализация результатов по каждому навыку пользователя.",
            "session_id": int(session_id),
            "overall_score": int(overall_score),
            "user": {
                "full_name": str(user.get("full_name") or "Не указан"),
                "job_description": str(user.get("job_description") or "Не указана"),
                "phone": str(user.get("phone") or "Не указан"),
            },
            "insight": {
                "title": insight_title,
                "text": insight_text,
            },
            "basis_items": [str(item) for item in basis_items],
            "recommendations": [str(item) for item in recommendations],
            "strengths": [str(item) for item in strengths],
            "growth_areas": [str(item) for item in growth_areas],
            "quotes": [str(item) for item in quotes],
            "competencies": competencies,
        }

    def build_pdf(self, connection, user_id: int, session_id: int) -> tuple[str, bytes]:
        user = self._load_user(connection, user_id)
        if user is None:
            raise ValueError("User not found")

        assessments = self._load_assessments(connection, user_id, session_id)
        if not assessments:
            raise ValueError("No skill assessments found for this session")

        level_percent_map = get_level_percent_map(connection)
        grouped_rows = self._group_by_competency(assessments, level_percent_map)
        overall_score = round(sum(item["avg_percent"] for item in grouped_rows) / len(grouped_rows))
        strongest, has_confident_strongest = self._select_strongest_competency(grouped_rows)
        has_manifested_results = any(item["avg_percent"] > 0 for item in grouped_rows)
        has_interpretation_signal = self._has_enough_interpretation_signal(grouped_rows, assessments)
        response_pattern = build_response_pattern_text(
            self._build_signal_metrics(assessments),
            has_interpretation_signal=has_interpretation_signal,
        )
        basis_items = build_interpretation_basis_items(self._build_signal_metrics(assessments))
        insight_title, insight_text = build_ai_insight_copy(
            strongest["competency_name"] if strongest else None,
            strongest["avg_percent"] if strongest else None,
            has_manifested_results=has_manifested_results,
            has_interpretation_signal=has_interpretation_signal,
            has_confident_strongest=has_confident_strongest,
            response_pattern=response_pattern,
        )
        recommendations = self._build_recommendations(grouped_rows)
        if not has_interpretation_signal:
            recommendations = list(WEAK_SIGNAL_RECOMMENDATIONS)
        strengths = self._build_strengths(
            strongest=strongest,
            has_confident_strongest=has_confident_strongest,
            response_pattern=response_pattern,
        )
        growth_areas = recommendations
        quotes = self._build_quotes(assessments)

        safe_name = (user.get("full_name") or f"user-{user_id}").replace(" ", "_")
        filename = f"competency_profile_{safe_name}_session_{session_id}.pdf"
        typst_payload = self._build_typst_payload(
            user=user,
            session_id=session_id,
            grouped_rows=grouped_rows,
            level_percent_map=level_percent_map,
            overall_score=overall_score,
            insight_title=insight_title,
            insight_text=insight_text,
            basis_items=basis_items,
            recommendations=recommendations,
            strengths=strengths,
            growth_areas=growth_areas,
            quotes=quotes,
        )
        return filename, render_typst_competency_report(typst_payload)


pdf_report_service = PdfReportService()
