from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from Api.config import settings


_TOKEN_PATTERN = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_PROFILE_FIELDS = {
    "domain": ("user_domain", "domain_profile"),
    "tasks_processes": ("user_tasks", "user_processes"),
    "stakeholders": ("user_stakeholders",),
    "systems_artifacts": ("user_systems", "user_artifacts"),
    "constraints_risks": ("user_constraints", "user_risks"),
}
_WEIGHTS = {
    "domain": 0.25,
    "tasks_processes": 0.30,
    "stakeholders": 0.15,
    "systems_artifacts": 0.15,
    "constraints_risks": 0.15,
}


@dataclass(frozen=True, slots=True)
class ProfileSimilarity:
    score: float
    components: dict[str, float]
    compatible: bool


@dataclass(frozen=True, slots=True)
class CaseSetReuseDecision:
    mode: str
    verdict: str
    reason: str
    score: float | None
    components: dict[str, float]
    source_session_id: int | None
    source_profile_id: int | None


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        items: list[str] = []
        for key, nested in value.items():
            items.append(str(key))
            items.extend(_flatten(nested))
        return items
    if isinstance(value, (list, tuple, set)):
        items = []
        for nested in value:
            items.extend(_flatten(nested))
        return items
    return [str(value)]


def _tokens(profile: dict[str, Any], fields: tuple[str, ...]) -> set[str]:
    text = " ".join(part for field in fields for part in _flatten(profile.get(field)))
    return {token.lower() for token in _TOKEN_PATTERN.findall(text) if len(token) > 1}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        # Missing data is not evidence of similarity.
        return 0.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def calculate_profile_similarity(
    current_profile: dict[str, Any],
    candidate_profile: dict[str, Any],
) -> ProfileSimilarity:
    current_role = current_profile.get("role_id")
    candidate_role = candidate_profile.get("role_id")
    if current_role is None or candidate_role is None or int(current_role) != int(candidate_role):
        return ProfileSimilarity(score=0.0, components={}, compatible=False)

    components = {
        name: round(
            _jaccard(_tokens(current_profile, fields), _tokens(candidate_profile, fields)),
            6,
        )
        for name, fields in _PROFILE_FIELDS.items()
    }
    score = sum(components[name] * _WEIGHTS[name] for name in _WEIGHTS)
    return ProfileSimilarity(score=round(score, 6), components=components, compatible=True)


class CaseReuseService:
    VALID_MODES = {"off", "shadow", "on"}

    @property
    def mode(self) -> str:
        configured = str(settings.case_set_reuse_mode or "off").strip().lower()
        return configured if configured in self.VALID_MODES else "off"

    def evaluate(
        self,
        *,
        connection,
        session_id: int,
        user_id: int,
        role_id: int,
        profile_id: int | None,
        profile: dict[str, Any] | None,
    ) -> CaseSetReuseDecision:
        mode = self.mode
        if mode == "off":
            return CaseSetReuseDecision(mode, "skipped", "feature_disabled", None, {}, None, None)
        if not profile_id or not profile:
            return CaseSetReuseDecision(mode, "miss", "profile_missing", None, {}, None, None)

        cutoff = datetime.utcnow() - timedelta(days=max(1, settings.case_set_reuse_max_age_days))
        rows = connection.execute(
            """
            SELECT
                us.id AS source_session_id,
                urp.id AS source_profile_id,
                urp.*,
                ARRAY_AGG(
                    CONCAT_WS(':',
                        sc.case_registry_id,
                        COALESCE(sc.case_registry_version, 0),
                        COALESCE(sc.case_text_version, 0),
                        COALESCE(sc.case_type_passport_version, 0),
                        COALESCE(sc.required_blocks_version, 0),
                        COALESCE(sc.red_flags_version, 0),
                        COALESCE(sc.skill_evidence_version, 0),
                        COALESCE(sc.difficulty_modifiers_version, 0),
                        COALESCE(sc.personalization_fields_version, 0)
                    )
                    ORDER BY sc.case_registry_id
                ) AS case_signature
            FROM user_sessions us
            JOIN users source_user ON source_user.id = us.user_id
            JOIN user_role_profiles urp ON urp.id = source_user.active_profile_id
            JOIN session_cases sc ON sc.session_id = us.id
            JOIN session_prompts sp
              ON sp.session_case_id = sc.id
             AND sp.prompt_type = 'case_dialog'
            WHERE us.user_id <> %s
              AND us.role_id = %s
              AND us.created_at >= %s
              AND COALESCE(sp.quality_verdict, 'ok') NOT IN ('reject', 'failed')
            GROUP BY us.id, urp.id
            ORDER BY us.created_at DESC
            LIMIT %s
            """,
            (user_id, role_id, cutoff, max(1, settings.case_set_reuse_candidate_limit)),
        ).fetchall()

        target_signature = self._load_case_signature(connection, session_id)
        best: tuple[ProfileSimilarity, dict[str, Any]] | None = None
        for row in rows:
            candidate = dict(row)
            if list(candidate.get("case_signature") or []) != target_signature:
                continue
            similarity = calculate_profile_similarity(profile, candidate)
            if not similarity.compatible:
                continue
            if best is None or similarity.score > best[0].score:
                best = (similarity, candidate)

        if best is None:
            return CaseSetReuseDecision(mode, "miss", "compatible_case_set_not_found", None, {}, None, None)

        similarity, candidate = best
        meets_threshold = similarity.score >= max(0.0, min(1.0, settings.case_set_reuse_min_score))
        if not meets_threshold:
            verdict, reason = "miss", "similarity_below_threshold"
        elif mode == "shadow":
            verdict, reason = "shadow_hit", "candidate_found"
        else:
            # Reuse remains deliberately gated until prompts are stored without user PII.
            verdict, reason = "shadow_hit", "live_reuse_not_enabled_for_personalized_prompts"
        return CaseSetReuseDecision(
            mode=mode,
            verdict=verdict,
            reason=reason,
            score=similarity.score,
            components=similarity.components,
            source_session_id=int(candidate["source_session_id"]),
            source_profile_id=int(candidate["source_profile_id"]),
        )

    def record(self, *, connection, session_id: int, profile_id: int | None, decision: CaseSetReuseDecision) -> None:
        connection.execute(
            """
            INSERT INTO case_set_reuse_audits (
                session_id, profile_id, mode, verdict, reason, similarity_score,
                similarity_components, source_session_id, source_profile_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                profile_id = EXCLUDED.profile_id,
                mode = EXCLUDED.mode,
                verdict = EXCLUDED.verdict,
                reason = EXCLUDED.reason,
                similarity_score = EXCLUDED.similarity_score,
                similarity_components = EXCLUDED.similarity_components,
                source_session_id = EXCLUDED.source_session_id,
                source_profile_id = EXCLUDED.source_profile_id,
                created_at = NOW()
            """,
            (
                session_id,
                profile_id,
                decision.mode,
                decision.verdict,
                decision.reason,
                decision.score,
                json.dumps(decision.components, ensure_ascii=False),
                decision.source_session_id,
                decision.source_profile_id,
            ),
        )

    @staticmethod
    def _load_case_signature(connection, session_id: int) -> list[str]:
        rows = connection.execute(
            """
            SELECT CONCAT_WS(':',
                case_registry_id,
                COALESCE(case_registry_version, 0),
                COALESCE(case_text_version, 0),
                COALESCE(case_type_passport_version, 0),
                COALESCE(required_blocks_version, 0),
                COALESCE(red_flags_version, 0),
                COALESCE(skill_evidence_version, 0),
                COALESCE(difficulty_modifiers_version, 0),
                COALESCE(personalization_fields_version, 0)
            ) AS signature
            FROM session_cases
            WHERE session_id = %s
            ORDER BY case_registry_id
            """,
            (session_id,),
        ).fetchall()
        return [str(row["signature"]) for row in rows]


case_reuse_service = CaseReuseService()
