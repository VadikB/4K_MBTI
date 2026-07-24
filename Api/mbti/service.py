from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Api.config import BASE_DIR, settings
from Api.database import get_active_llm_prompt, get_connection
from Api.deepseek_client import deepseek_client
from Api.mbti.prompts import FOLLOWUP_PROMPT, PAIR_EVALUATION_PROMPT, SUMMARY_PROMPT, SYSTEM_PROMPT


class MbtiAssessmentService:
    def __init__(self) -> None:
        self._store = None
        self._store_load_attempted = False

    @property
    def enabled(self) -> bool:
        return bool(settings.mbti_enabled and deepseek_client.enabled)

    def _resolve_index_dir(self) -> Path | None:
        candidates: list[Path] = []
        configured = str(settings.mbti_faiss_index_dir or "").strip()
        if configured:
            candidates.append(Path(configured).expanduser())
        candidates.append(BASE_DIR / "mbti_data" / "faiss")
        candidates.append(BASE_DIR.parent / "mbti_rag" / "data" / "faiss")
        for candidate in candidates:
            if (candidate / "metadata.json").exists() and (candidate / "index.faiss").exists():
                return candidate
        return None

    def _get_store(self):
        if self._store is not None:
            return self._store
        if self._store_load_attempted:
            return None
        self._store_load_attempted = True
        index_dir = self._resolve_index_dir()
        if index_dir is None:
            return None
        try:
            from Api.mbti.faiss_store import FaissRagStore
            self._store = FaissRagStore(index_dir=index_dir)
        except Exception:
            self._store = None
        return self._store

    def _render(self, template: str, values: dict[str, str]) -> str:
        result = template
        for key, value in values.items():
            result = result.replace("{{" + key + "}}", value)
        return result.strip()

    def _prompt(self, prompt_code: str, fallback: str) -> str:
        try:
            with get_connection() as connection:
                stored = get_active_llm_prompt(connection, prompt_code)
        except Exception:
            stored = None
        return str(stored or fallback or "").strip()

    def _parse_json_object(self, raw: str) -> dict[str, Any] | None:
        text = str(raw or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                payload = json.loads(text[start : end + 1])
                return payload if isinstance(payload, dict) else None
            except Exception:
                return None

    def _format_context(self, results: list[Any]) -> str:
        blocks: list[str] = []
        for number, result in enumerate(results, start=1):
            chunk = result.chunk
            blocks.append(
                f"[{number}] source={chunk.source}, pages={chunk.page_start}-{chunk.page_end}, similarity={result.score:.3f}\n{chunk.text}"
            )
        return "\n\n---\n\n".join(blocks)

    def _normalize_case_result(
        self,
        payload: dict[str, Any] | None,
        *,
        session_case_id: int,
        case_title: str,
        case_number: int,
        total_cases: int,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        result = dict(payload)
        result["идентификатор_пары"] = int(result.get("идентификатор_пары") or case_number or session_case_id)
        result["тип_пары"] = str(result.get("тип_пары") or "кейс-ответ")
        result["session_case_id"] = session_case_id
        result["case_title"] = case_title
        result["case_number"] = case_number
        result["total_cases"] = total_cases
        result.setdefault("вероятные_сигналы_темперамента", [])
        result.setdefault("доказательства", [])
        result.setdefault("недостающая_информация", [])
        result.setdefault("качество_поиска", "low")
        result.setdefault("краткий_вывод", "")
        return result

    def _should_generate_followups(self, case_result: dict[str, Any]) -> bool:
        mode = settings.mbti_followup_mode
        if mode == "off":
            return False
        if mode == "strict":
            return True
        score = int(case_result.get("оценка") or 0)
        missing = case_result.get("недостающая_информация") or []
        retrieval_quality = str(case_result.get("качество_поиска") or "").strip().lower()
        return bool(missing) or score < settings.mbti_followup_score_threshold or retrieval_quality in {"low", "medium"}

    def evaluate_case(
        self,
        *,
        session_case_id: int,
        case_title: str,
        case_number: int,
        total_cases: int,
        case_context: str,
        case_task: str,
        user_answer: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        if not self.enabled:
            return None, []
        store = self._get_store()
        answer_text = str(user_answer or "").strip()
        if store is None or not answer_text:
            return None, []

        query = "\n".join(part for part in [case_title, case_context, case_task, answer_text] if str(part or "").strip())
        results = store.search(query, top_k=settings.mbti_top_k)
        prompt = self._render(
            self._prompt("mbti.case_evaluation", PAIR_EVALUATION_PROMPT),
            {
                "case_title": case_title,
                "case_context": case_context,
                "case_task": case_task,
                "user_answer": answer_text,
                "context": self._format_context(results),
            },
        )
        try:
            raw = deepseek_client._post_chat(
                [
                    {"role": "system", "content": self._prompt("mbti.system", SYSTEM_PROMPT)},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                timeout_sec=60,
                routing_key=f"mbti::case::{session_case_id}",
            )
        except Exception:
            return None, []

        case_result = self._normalize_case_result(
            self._parse_json_object(raw),
            session_case_id=session_case_id,
            case_title=case_title,
            case_number=case_number,
            total_cases=total_cases,
        )
        if case_result is None:
            return None, []
        followups = self.generate_followup_questions(
            case_title=case_title,
            case_task=case_task,
            user_answer=answer_text,
            case_result=case_result,
        )
        return case_result, followups

    def generate_followup_questions(
        self,
        *,
        case_title: str,
        case_task: str,
        user_answer: str,
        case_result: dict[str, Any],
    ) -> list[str]:
        if not self.enabled or not self._should_generate_followups(case_result):
            return []
        max_questions = max(0, settings.mbti_followup_max_per_case)
        if max_questions <= 0:
            return []
        prompt = self._render(
            self._prompt("mbti.followup", FOLLOWUP_PROMPT),
            {
                "case_title": case_title,
                "case_task": case_task,
                "user_answer": user_answer,
                "evaluation_json": json.dumps(case_result, ensure_ascii=False, indent=2),
                "max_questions": str(max_questions),
            },
        )
        try:
            raw = deepseek_client._post_chat(
                [
                    {"role": "system", "content": self._prompt("mbti.system", SYSTEM_PROMPT)},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                timeout_sec=45,
                routing_key=f"mbti::followup::{case_result.get('session_case_id')}",
            )
        except Exception:
            return []
        payload = self._parse_json_object(raw) or {}
        questions = payload.get("уточняющие_вопросы") or []
        if not isinstance(questions, list):
            return []
        normalized: list[str] = []
        for item in questions:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized[:max_questions]

    def save_case_result(self, connection, *, session_case_id: int, case_result: dict[str, Any] | None, followup_questions: list[str]) -> None:
        if case_result is None:
            return
        connection.execute(
            """
            UPDATE session_case_results
            SET mbti_case_json = %s::jsonb,
                mbti_followup_questions = %s::jsonb,
                mbti_followup_answers = '[]'::jsonb
            WHERE session_case_id = %s
            """,
            (
                json.dumps(case_result, ensure_ascii=False),
                json.dumps(followup_questions or [], ensure_ascii=False),
                session_case_id,
            ),
        )

    def summarize_session(self, connection, *, session_id: int) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        rows = connection.execute(
            """
            SELECT mbti_case_json
            FROM session_case_results
            WHERE session_id = %s
              AND mbti_case_json IS NOT NULL
              AND mbti_case_json::text <> '{}'::text
            ORDER BY session_case_id ASC
            """,
            (session_id,),
        ).fetchall()
        case_results: list[dict[str, Any]] = []
        for row in rows:
            payload = row.get("mbti_case_json") if isinstance(row, dict) else None
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = None
            if isinstance(payload, dict):
                case_results.append(payload)
        if not case_results:
            return None

        prompt = self._render(
            self._prompt("mbti.session_summary", SUMMARY_PROMPT),
            {"case_results_json": json.dumps(case_results, ensure_ascii=False, indent=2)},
        )
        try:
            raw = deepseek_client._post_chat(
                [
                    {"role": "system", "content": self._prompt("mbti.system", SYSTEM_PROMPT)},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                timeout_sec=60,
                routing_key=f"mbti::summary::{session_id}",
            )
            summary_payload = self._parse_json_object(raw)
        except Exception:
            summary_payload = None

        if not isinstance(summary_payload, dict):
            scores = [int(item.get("оценка") or 0) for item in case_results]
            summary_payload = {
                "структура_интервью": {
                    "количество_пар": len(case_results),
                    "типы_пары": [str(item.get("тип_пары") or "кейс-ответ") for item in case_results],
                },
                "результаты_по_парам": case_results,
                "общий_итог": {
                    "оценка": round(sum(scores) / len(scores)) if scores else 0,
                    "вероятные_сигналы_темперамента": [],
                    "доказательства": [],
                    "недостающая_информация": [],
                    "заметки_о_согласованности": [],
                    "качество_поиска": "medium",
                    "краткий_вывод": "Сводка собрана автоматически по кейсовым MBTI-оценкам.",
                },
            }

        connection.execute(
            """
            UPDATE user_sessions
            SET mbti_summary_json = %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(summary_payload, ensure_ascii=False), session_id),
        )
        return summary_payload


mbti_assessment_service = MbtiAssessmentService()
