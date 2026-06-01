from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from Api.config import settings
from Api.database import get_connection

RU_POSITION_ALIASES: list[tuple[tuple[str, ...], list[str]]] = [
    (("клиентск", "поддерж"), ["customer support manager", "customer service manager", "customer support specialist"]),
    (("техническ", "поддерж"), ["ICT help desk manager", "ICT support technician", "technical support specialist"]),
    (("обучен", "развит", "персонал"), ["training and development manager", "learning and development manager", "training specialist"]),
    (("инженер", "конструкт"), ["design engineer", "mechanical design engineer", "drafting engineer"]),
    (("бизнес", "аналит"), ["business analyst", "requirements analyst", "systems analyst"]),
    (("логист",), ["logistics specialist", "supply chain specialist"]),
    (("hr", "подбор"), ["recruitment specialist", "human resources specialist"]),
    (("проект", "менедж"), ["project manager", "delivery manager"]),
]

RU_DUTY_ALIASES: list[tuple[tuple[str, ...], list[str]]] = [
    (("чертеж", "кд", "спецификац"), ["design documentation", "technical drawings", "engineering specifications"]),
    (("обращен", "жалоб", "сервис"), ["customer support", "service quality", "customer escalations"]),
    (("обучен", "курс", "эксперт", "подрядчик"), ["training program coordination", "learning needs analysis", "training provider coordination"]),
    (("vpn", "принтер", "почт"), ["IT support", "help desk", "end-user support"]),
]

DOMAIN_ENGLISH_MARKERS: dict[str, list[str]] = {
    "client_service": [
        "customer support",
        "customer service",
        "contact centre",
        "contact center",
        "aftersales service",
        "client service",
        "service quality",
        "customer escalations",
    ],
    "learning_and_development": [
        "training",
        "learning and development",
        "corporate training",
        "education programme",
        "staff development",
        "learning needs",
    ],
    "engineering": [
        "design engineer",
        "engineering specifications",
        "design documentation",
        "technical drawings",
        "mechanical design",
        "drafting",
    ],
    "it_support": [
        "ict help desk",
        "help desk",
        "technical support",
        "it support",
        "end-user support",
    ],
    "business_analysis": [
        "business analyst",
        "requirements analyst",
        "systems analyst",
        "process analysis",
    ],
    "logistics": [
        "logistics",
        "supply chain",
        "shipment",
        "warehouse",
    ],
    "hr": [
        "human resources",
        "recruitment",
        "talent acquisition",
        "personnel",
    ],
}


@dataclass(slots=True)
class ExternalOccupationCandidate:
    source: str
    external_id: str
    label: str
    description: str
    skills: list[str]
    broader_domain: str | None
    match_score: float
    raw_payload: dict[str, Any]


class EscoOccupationSource:
    """
    ESCO adapter for occupation candidate retrieval.

    The adapter is intentionally isolated from the main profiling pipeline.
    This lets us validate external occupation suggestions before we start using
    them as a first-class input for profile generation.
    """

    def __init__(self) -> None:
        self.enabled = settings.esco_api_enabled
        self.base_url = settings.esco_api_base_url.rstrip("/")
        self.version = settings.esco_api_version
        self.language = settings.esco_api_language

    def search_candidates(
        self,
        *,
        position: str | None,
        duties: str | None,
        limit: int = 5,
    ) -> list[ExternalOccupationCandidate]:
        queries = self._build_queries(position=position, duties=duties)
        if not self.enabled or not queries:
            return []
        preferred_domain_hint = self._infer_preferred_domain_hint(position=position, duties=duties)

        collected: list[ExternalOccupationCandidate] = []
        seen_ids: set[str] = set()
        for query in queries:
            payload = self._request_search(query=query, limit=limit)
            if not payload:
                continue
            for candidate in self._parse_candidates(payload, query=query, limit=limit):
                if candidate.external_id in seen_ids:
                    continue
                seen_ids.add(candidate.external_id)
                collected.append(candidate)
            if len(collected) >= limit:
                break
        reranked = sorted(
            collected,
            key=lambda item: self._rerank_candidate_score(item=item, preferred_domain_hint=preferred_domain_hint),
            reverse=True,
        )
        return reranked[: max(1, min(limit, 10))]

    def _build_queries(self, *, position: str | None, duties: str | None) -> list[str]:
        position_text = self._normalize_text(position)
        duties_text = self._normalize_text(duties)
        queries: list[str] = []
        if position_text and duties_text:
            queries.append(f"{position_text} {duties_text}")
        if position_text:
            queries.append(position_text)
        if duties_text:
            queries.append(duties_text)

        normalized_ru = f"{position_text} {duties_text}".lower()
        if re.search(r"[а-яА-Я]", normalized_ru):
            for patterns, aliases in RU_POSITION_ALIASES:
                if all(pattern in normalized_ru for pattern in patterns):
                    queries.extend(aliases)
            for patterns, aliases in RU_DUTY_ALIASES:
                if any(pattern in normalized_ru for pattern in patterns):
                    queries.extend(aliases)

        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            cleaned = re.sub(r"\s+", " ", query).strip()
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped[:8]

    def _request_search(self, *, query: str, limit: int) -> dict[str, Any] | None:
        params = parse.urlencode(
            {
                "text": query,
                "language": self.language,
                "type": "occupation",
                "limit": max(1, min(limit, 10)),
                "selectedVersion": self.version,
                "full": "true",
            }
        )
        url = f"{self.base_url}/search?{params}"
        req = request.Request(url, headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError):
            return None

    def _infer_preferred_domain_hint(self, *, position: str | None, duties: str | None) -> str | None:
        normalized_ru = f"{self._normalize_text(position)} {self._normalize_text(duties)}".lower()
        if re.search(r"[а-яА-Я]", normalized_ru):
            if "клиентск" in normalized_ru and "поддерж" in normalized_ru:
                return "client_service"
            if "обучен" in normalized_ru and ("развит" in normalized_ru or "персонал" in normalized_ru):
                return "learning_and_development"
            if "инженер" in normalized_ru and "конструкт" in normalized_ru:
                return "engineering"
            if "техническ" in normalized_ru and "поддерж" in normalized_ru:
                return "it_support"
        return None

    def _rerank_candidate_score(self, *, item: ExternalOccupationCandidate, preferred_domain_hint: str | None) -> float:
        score = item.match_score
        if not preferred_domain_hint:
            return score
        candidate_text = " ".join([item.label, item.description, item.broader_domain or "", " ".join(item.skills)]).lower()
        positive_markers = DOMAIN_ENGLISH_MARKERS.get(preferred_domain_hint, [])
        if any(marker in candidate_text for marker in positive_markers):
            score += 0.75
        negative_markers = []
        if preferred_domain_hint == "client_service":
            negative_markers = DOMAIN_ENGLISH_MARKERS.get("it_support", [])
        elif preferred_domain_hint == "it_support":
            negative_markers = DOMAIN_ENGLISH_MARKERS.get("client_service", [])
        if any(marker in candidate_text for marker in negative_markers):
            score -= 0.5
        return score

    def _normalize_text(self, value: str | None) -> str:
        text = str(value or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _parse_candidates(
        self,
        payload: dict[str, Any],
        *,
        query: str,
        limit: int,
    ) -> list[ExternalOccupationCandidate]:
        embedded = payload.get("_embedded") if isinstance(payload, dict) else None
        raw_items = []
        if isinstance(embedded, dict):
            for key in ("results", "items", "occupations"):
                value = embedded.get(key)
                if isinstance(value, list):
                    raw_items = value
                    break
        if not raw_items and isinstance(payload.get("results"), list):
            raw_items = payload["results"]

        candidates: list[ExternalOccupationCandidate] = []
        for item in raw_items[: max(1, min(limit, 10))]:
            if not isinstance(item, dict):
                continue
            label = self._extract_label(item)
            if not label:
                continue
            description = self._extract_description(item)
            skills = self._extract_skills(item)
            broader_domain = self._extract_broader_domain(item)
            external_id = str(
                item.get("uri")
                or item.get("id")
                or item.get("code")
                or label
            )
            candidates.append(
                ExternalOccupationCandidate(
                    source="ESCO",
                    external_id=external_id,
                    label=label,
                    description=description,
                    skills=skills,
                    broader_domain=broader_domain,
                    match_score=self._estimate_match_score(query=query, label=label, description=description, skills=skills),
                    raw_payload=item,
                )
            )
        return sorted(candidates, key=lambda item: item.match_score, reverse=True)

    def _extract_label(self, item: dict[str, Any]) -> str:
        title = item.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        preferred = item.get("preferredLabel")
        if isinstance(preferred, dict):
            for value in preferred.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(preferred, str) and preferred.strip():
            return preferred.strip()
        return ""

    def _extract_description(self, item: dict[str, Any]) -> str:
        for key in ("description", "snippet", "scopeNote"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
        return ""

    def _extract_skills(self, item: dict[str, Any]) -> list[str]:
        skills: list[str] = []
        for key in ("skills", "essentialSkills", "optionalSkills"):
            value = item.get(key)
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, str) and entry.strip():
                        skills.append(entry.strip())
                    elif isinstance(entry, dict):
                        label = self._extract_label(entry)
                        if label:
                            skills.append(label)
        return skills[:10]

    def _extract_broader_domain(self, item: dict[str, Any]) -> str | None:
        for key in ("broaderConcepts", "broaderHierarchyConcepts"):
            value = item.get(key)
            if isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, str) and first.strip():
                    return first.strip()
                if isinstance(first, dict):
                    label = self._extract_label(first)
                    if label:
                        return label
        return None

    def _estimate_match_score(
        self,
        *,
        query: str,
        label: str,
        description: str,
        skills: list[str],
    ) -> float:
        query_terms = {term for term in re.split(r"\W+", query.lower()) if len(term) > 2}
        haystack = " ".join([label, description, " ".join(skills)]).lower()
        if not query_terms:
            return 0.0
        matched = sum(1 for term in query_terms if term in haystack)
        return round(matched / max(len(query_terms), 1), 4)


class ExternalKnowledgeService:
    def __init__(self) -> None:
        self.esco = EscoOccupationSource()

    def search_professional_candidates(
        self,
        *,
        position: str | None,
        duties: str | None,
        limit: int = 5,
    ) -> list[ExternalOccupationCandidate]:
        return self.esco.search_candidates(position=position, duties=duties, limit=limit)

    def resolve_candidates_to_domains(
        self,
        *,
        candidates: list[ExternalOccupationCandidate],
    ) -> list[dict[str, Any]]:
        domain_rows = self._load_domain_rows()
        resolved: list[dict[str, Any]] = []
        for candidate in candidates:
            match = self._match_candidate_to_domain(candidate=candidate, domain_rows=domain_rows)
            resolved.append(
                {
                    "candidate": candidate,
                    "resolved_domain_code": match.get("domain_code") if match else None,
                    "resolved_family_name": match.get("family_name") if match else None,
                    "resolved_display_name": match.get("display_name") if match else None,
                    "mapping_confidence": match.get("mapping_confidence", 0.0) if match else 0.0,
                }
            )
        return resolved

    def select_best_resolved_candidate(
        self,
        *,
        resolved_candidates: list[dict[str, Any]],
        preferred_domain_code: str | None = None,
    ) -> dict[str, Any] | None:
        ranked = [
            item
            for item in resolved_candidates
            if item.get("resolved_domain_code")
        ]
        if not ranked:
            return None
        preferred = str(preferred_domain_code or "").strip().lower()
        if preferred:
            preferred_ranked = [
                item for item in ranked
                if str(item.get("resolved_domain_code") or "").strip().lower() == preferred
            ]
            if preferred_ranked:
                ranked = preferred_ranked
        ranked.sort(
            key=lambda item: (
                float(item.get("mapping_confidence") or 0.0),
                float(getattr(item.get("candidate"), "match_score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return ranked[0]

    def persist_mapping(
        self,
        *,
        candidate: ExternalOccupationCandidate,
        domain_code: str,
        confidence_score: float,
        is_verified: bool = False,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO domain_external_mappings (
                    domain_code,
                    source_name,
                    external_id,
                    external_label,
                    external_description,
                    external_broader_domain,
                    external_skills,
                    confidence_score,
                    is_verified,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW(), NOW())
                ON CONFLICT (source_name, external_id) DO UPDATE
                SET
                    domain_code = EXCLUDED.domain_code,
                    external_label = EXCLUDED.external_label,
                    external_description = EXCLUDED.external_description,
                    external_broader_domain = EXCLUDED.external_broader_domain,
                    external_skills = EXCLUDED.external_skills,
                    confidence_score = EXCLUDED.confidence_score,
                    is_verified = domain_external_mappings.is_verified OR EXCLUDED.is_verified,
                    updated_at = NOW()
                """,
                (
                    domain_code,
                    candidate.source,
                    candidate.external_id,
                    candidate.label,
                    candidate.description,
                    candidate.broader_domain,
                    json.dumps(candidate.skills, ensure_ascii=False),
                    confidence_score,
                    is_verified,
                ),
            )

    def _load_domain_rows(self) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    domain_code,
                    family_name,
                    display_name,
                    description,
                    typical_keywords
                FROM domain_catalog
                WHERE is_active = TRUE
                ORDER BY domain_code
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _match_candidate_to_domain(
        self,
        *,
        candidate: ExternalOccupationCandidate,
        domain_rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        best_match: dict[str, Any] | None = None
        best_score = 0.0
        candidate_text = " ".join(
            [
                candidate.label,
                candidate.description,
                candidate.broader_domain or "",
                " ".join(candidate.skills),
            ]
        ).lower()
        for row in domain_rows:
            keywords = row.get("typical_keywords") or []
            if not isinstance(keywords, list):
                keywords = []
            score = 0.0
            for keyword in keywords:
                if not isinstance(keyword, str):
                    continue
                normalized = keyword.strip().lower()
                if normalized and normalized in candidate_text:
                    score += 1.0
            display_name = str(row.get("display_name") or "").lower()
            if display_name and display_name in candidate_text:
                score += 1.5
            description = str(row.get("description") or "").lower()
            if description:
                overlap = sum(1 for token in re.split(r"\W+", description) if len(token) > 4 and token in candidate_text)
                score += min(overlap * 0.1, 1.0)
            domain_code = str(row.get("domain_code") or "")
            for marker in DOMAIN_ENGLISH_MARKERS.get(domain_code, []):
                if marker in candidate_text:
                    score += 1.25
            if score > best_score:
                best_score = score
                best_match = {
                    "domain_code": domain_code,
                    "family_name": row.get("family_name"),
                    "display_name": row.get("display_name"),
                    "mapping_confidence": round(score, 4),
                }
        if best_match is None or best_score <= 0:
            return None
        return best_match


external_knowledge_service = ExternalKnowledgeService()
