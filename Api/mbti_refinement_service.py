from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from Api.config import settings
from Api.deepseek_client import deepseek_client


@dataclass
class RefinementQuestion:
    code: str
    text: str
    gap: str


class MbtiRefinementService:
    LEGACY_GENERIC_QUESTION = (
        'Уточните, пожалуйста, как вы обычно действуете в подобных неоднозначных ситуациях и что для вас является главным критерием выбора?'
    )

    GAP_QUESTION_MAP: list[tuple[tuple[str, ...], str, str]] = [
        (("хаос", "неопредел"), "reaction_to_chaos", "Представьте, что план сорвался, данных мало, а команда предлагает несколько противоречивых путей. Как вы будете действовать в первые 30 минут?"),
        (("людей", "stress", "стресс", "feeling"), "people_vs_result_under_stress", "Если ради дедлайна нужно принять решение, которое может демотивировать часть команды, что для вас будет главным при выборе?"),
        (("idealist", "идеалист", "естествен", "выученн"), "idealist_natural_or_learned", "Когда вы действуете мягко и с акцентом на отношения, это ваш естественный стиль или осознанная рабочая стратегия? Почему?"),
        (("sensing", "intuition", "детал", "концепц"), "sensing_vs_intuition", "Когда времени мало, вы скорее опираетесь на детали и проверяемые факты или на общую концепцию и гипотезу? Как это выглядит на практике?"),
    ]

    REFINE_SUMMARY_PROMPT = """Ниже исходная сводка MBTI-анализа и ответы пользователя на уточняющие вопросы.
Обнови только раздел 'общий_итог', повысив или сохранив уверенность без искусственного завышения.
Если данных всё ещё недостаточно, честно оставь неоднозначность.
Верни только JSON-объект итоговой сводки в том же формате, что и исходная summary.

Исходная summary:
{{source_summary_json}}

Ответы на уточнение:
{{answers_json}}
"""

    def _parse_json_object(self, raw: str) -> dict[str, Any] | None:
        text = str(raw or '').strip()
        if not text:
            return None
        if text.startswith('```'):
            text = text.strip('`')
            text = text.replace('json', '', 1).strip()
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except Exception:
            start = text.find('{')
            end = text.rfind('}')
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                payload = json.loads(text[start : end + 1])
                return payload if isinstance(payload, dict) else None
            except Exception:
                return None

    def _render(self, template: str, values: dict[str, str]) -> str:
        result = template
        for key, value in values.items():
            result = result.replace('{{' + key + '}}', value)
        return result.strip()

    def _get_session_row(self, connection, *, user_id: int, session_id: int):
        return connection.execute(
            """
            SELECT id, user_id, status, mbti_summary_json
            FROM user_sessions
            WHERE id = %s AND user_id = %s
            """,
            (session_id, user_id),
        ).fetchone()

    def _extract_overall(self, summary: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        overall = summary.get('общий_итог') or summary.get('overall_result') or summary.get('overall')
        return overall if isinstance(overall, dict) else {}

    def _extract_confidence(self, summary: dict[str, Any] | None) -> int:
        overall = self._extract_overall(summary)
        try:
            return max(0, min(100, int(overall.get('оценка') or overall.get('score') or 0)))
        except Exception:
            return 0

    def _extract_gaps(self, summary: dict[str, Any] | None) -> list[str]:
        overall = self._extract_overall(summary)
        raw = overall.get('недостающая_информация') or []
        if not isinstance(raw, list):
            return []
        result: list[str] = []
        for item in raw:
            text = str(item or '').strip()
            if text and text not in result:
                result.append(text)
        return result

    def _build_contextual_fallback_question_text(self, gap: str) -> str:
        gap_text = str(gap or '').strip().rstrip('.')
        return (
            f"Нам нужно уточнить такой момент профиля: «{gap_text}». "
            "Опишите одну конкретную рабочую ситуацию, где это проявилось: "
            "что происходило, как вы действовали и какой критерий выбора был для вас главным?"
        ) if gap_text else (
            "Опишите одну конкретную рабочую ситуацию, где это проявилось: "
            "что происходило, как вы действовали и какой критерий выбора был для вас главным?"
        )

    def _question_for_gap(self, gap: str, used_codes: set[str]) -> RefinementQuestion:
        normalized = gap.lower()
        for markers, code, text in self.GAP_QUESTION_MAP:
            if code in used_codes:
                continue
            if any(marker in normalized for marker in markers):
                return RefinementQuestion(code=code, text=text, gap=gap)
        fallback_index = len(used_codes) + 1
        return RefinementQuestion(
            code=f'gap_followup_{fallback_index}',
            text=self._build_contextual_fallback_question_text(gap),
            gap=gap,
        )

    def _is_legacy_generic_question(self, text: str | None) -> bool:
        return str(text or '').strip() == self.LEGACY_GENERIC_QUESTION

    def _refresh_legacy_active_refinement(self, connection, row):
        if row is None or row.get('status') != 'active':
            return row
        asked_questions = row.get('asked_questions_json') or []
        if not isinstance(asked_questions, list) or not asked_questions:
            return row

        changed = False
        refreshed_questions: list[dict[str, Any]] = []
        current_code = str(row.get('current_question_code') or '').strip()
        current_text = str(row.get('current_question_text') or '').strip()
        refreshed_current_text = current_text

        for item in asked_questions:
            payload = dict(item) if isinstance(item, dict) else {}
            gap = str(payload.get('gap') or '').strip()
            question_text = str(payload.get('text') or '').strip()
            question_code = str(payload.get('code') or '').strip()
            if self._is_legacy_generic_question(question_text):
                payload['text'] = self._build_contextual_fallback_question_text(gap)
                question_text = payload['text']
                changed = True
            if question_code and question_code == current_code and self._is_legacy_generic_question(current_text):
                refreshed_current_text = question_text
            refreshed_questions.append(payload)

        if not changed and refreshed_current_text == current_text:
            return row

        updated_row = connection.execute(
            """
            UPDATE session_mbti_refinements
            SET asked_questions_json = %s::jsonb,
                current_question_text = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                json.dumps(refreshed_questions, ensure_ascii=False),
                refreshed_current_text,
                row['id'],
            ),
        ).fetchone()
        connection.commit()
        return updated_row or row

    def _build_question_plan(self, summary: dict[str, Any]) -> list[dict[str, str]]:
        gaps = self._extract_gaps(summary)
        max_questions = max(1, settings.mbti_refinement_max_questions)
        used_codes: set[str] = set()
        questions: list[dict[str, str]] = []
        for gap in gaps:
            question = self._question_for_gap(gap, used_codes)
            used_codes.add(question.code)
            questions.append({'code': question.code, 'text': question.text, 'gap': question.gap})
            if len(questions) >= max_questions:
                break
        if not questions:
            questions.append({
                'code': 'general_reflection',
                'text': 'Какой ваш способ принятия решений лучше всего отражает ваш естественный стиль в сложных рабочих ситуациях?',
                'gap': 'Требуется дополнительное подтверждение профиля.'
            })
        return questions

    def _row_to_state(self, row) -> dict[str, Any]:
        updated_summary = row.get('updated_summary_json') or row.get('source_summary_json') or {}
        asked_questions = row.get('asked_questions_json') or []
        answers = row.get('answers_json') or []
        current_question = None
        if row.get('status') == 'active' and row.get('current_question_text'):
            current_question = {
                'code': row.get('current_question_code') or '',
                'text': row.get('current_question_text') or '',
            }
        return {
            'active': row.get('status') == 'active',
            'completed': row.get('status') == 'completed',
            'refinement_id': int(row['id']) if row.get('id') is not None else None,
            'question_index': len(answers) + (1 if current_question else 0),
            'question_total': len(asked_questions),
            'current_confidence': int(row.get('current_confidence') or 0),
            'target_confidence': int(row.get('target_confidence') or settings.mbti_refinement_target_confidence),
            'current_question': current_question,
            'remaining_gaps': [str(item) for item in (row.get('gaps_json') or [])],
            'resolved_gaps': [str(item) for item in (row.get('resolved_gaps_json') or [])],
            'updated_mbti_summary': updated_summary if row.get('status') == 'completed' else None,
        }

    def _get_active_refinement(self, connection, *, session_id: int):
        return connection.execute(
            """
            SELECT *
            FROM session_mbti_refinements
            WHERE session_id = %s AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()

    def _get_latest_refinement(self, connection, *, session_id: int):
        return connection.execute(
            """
            SELECT *
            FROM session_mbti_refinements
            WHERE session_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()

    def start(self, connection, *, user_id: int, session_id: int) -> dict[str, Any]:
        session_row = self._get_session_row(connection, user_id=user_id, session_id=session_id)
        if session_row is None:
            raise ValueError('Assessment session not found')
        if str(session_row.get('status') or '').strip().lower() != 'completed':
            raise ValueError('MBTI-уточнение доступно только после завершения основного ассессмента.')
        summary = session_row.get('mbti_summary_json') or {}
        if not isinstance(summary, dict) or not summary:
            raise ValueError('Для этой сессии пока нет MBTI summary.')

        active_row = self._get_active_refinement(connection, session_id=session_id)
        if active_row is not None:
            active_row = self._refresh_legacy_active_refinement(connection, active_row)
            return self._row_to_state(active_row)

        gaps = self._extract_gaps(summary)
        current_confidence = self._extract_confidence(summary)
        questions = self._build_question_plan(summary)
        first_question = questions[0]
        row = connection.execute(
            """
            INSERT INTO session_mbti_refinements (
                session_id, user_id, status, target_confidence, current_confidence,
                question_count, max_questions, source_summary_json, updated_summary_json,
                gaps_json, resolved_gaps_json, current_question_code, current_question_text,
                asked_questions_json, answers_json, created_at, updated_at
            )
            VALUES (
                %s, %s, 'active', %s, %s,
                0, %s, %s::jsonb, %s::jsonb,
                %s::jsonb, '[]'::jsonb, %s, %s,
                %s::jsonb, '[]'::jsonb, NOW(), NOW()
            )
            RETURNING *
            """,
            (
                session_id,
                user_id,
                settings.mbti_refinement_target_confidence,
                current_confidence,
                settings.mbti_refinement_max_questions,
                json.dumps(summary, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False),
                json.dumps(gaps, ensure_ascii=False),
                first_question['code'],
                first_question['text'],
                json.dumps(questions, ensure_ascii=False),
            ),
        ).fetchone()
        connection.commit()
        return self._row_to_state(row)

    def get_state(self, connection, *, user_id: int, session_id: int) -> dict[str, Any]:
        session_row = self._get_session_row(connection, user_id=user_id, session_id=session_id)
        if session_row is None:
            raise ValueError('Assessment session not found')
        row = self._get_latest_refinement(connection, session_id=session_id)
        if row is None:
            return {
                'active': False,
                'completed': False,
                'refinement_id': None,
                'question_index': 0,
                'question_total': 0,
                'current_confidence': self._extract_confidence(session_row.get('mbti_summary_json') or {}),
                'target_confidence': settings.mbti_refinement_target_confidence,
                'current_question': None,
                'remaining_gaps': self._extract_gaps(session_row.get('mbti_summary_json') or {}),
                'resolved_gaps': [],
                'updated_mbti_summary': None,
            }
        row = self._refresh_legacy_active_refinement(connection, row)
        return self._row_to_state(row)

    def _refine_summary(self, *, source_summary: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
        current_confidence = self._extract_confidence(source_summary)
        if not deepseek_client.enabled:
            updated = deepcopy(source_summary)
            overall = updated.setdefault('общий_итог', {})
            overall['оценка'] = min(100, max(current_confidence, current_confidence + min(len(answers) * 6, 20)))
            conclusion = str(overall.get('краткий_вывод') or '').strip()
            suffix = ' После уточняющих вопросов уверенность повышена, но часть неоднозначностей всё ещё оценивается по ответам пользователя.'
            overall['краткий_вывод'] = (conclusion + suffix).strip() if conclusion else suffix.strip()
            if 'недостающая_информация' in overall and isinstance(overall['недостающая_информация'], list):
                overall['недостающая_информация'] = []
            return updated

        prompt = self._render(
            self.REFINE_SUMMARY_PROMPT,
            {
                'source_summary_json': json.dumps(source_summary, ensure_ascii=False, indent=2),
                'answers_json': json.dumps(answers, ensure_ascii=False, indent=2),
            },
        )
        try:
            raw = deepseek_client._post_chat(
                [
                    {'role': 'system', 'content': 'Ты уточняешь уже существующую MBTI-сводку и возвращаешь только JSON.'},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.0,
                timeout_sec=60,
                routing_key='mbti::refinement::summary',
            )
            parsed = self._parse_json_object(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        return deepcopy(source_summary)

    def submit_answer(self, connection, *, user_id: int, session_id: int, refinement_id: int, answer: str) -> dict[str, Any]:
        session_row = self._get_session_row(connection, user_id=user_id, session_id=session_id)
        if session_row is None:
            raise ValueError('Assessment session not found')
        row = connection.execute(
            """
            SELECT *
            FROM session_mbti_refinements
            WHERE id = %s AND session_id = %s AND user_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (refinement_id, session_id, user_id),
        ).fetchone()
        if row is None:
            raise ValueError('MBTI refinement not found')
        if row.get('status') != 'active':
            raise ValueError('MBTI refinement already completed')
        row = self._refresh_legacy_active_refinement(connection, row)
        answer_text = str(answer or '').strip()
        if not answer_text:
            raise ValueError('Введите ответ на уточняющий вопрос.')

        asked_questions = row.get('asked_questions_json') or []
        answers = row.get('answers_json') or []
        if not row.get('current_question_text'):
            raise ValueError('Текущий уточняющий вопрос не найден.')

        answers.append({
            'question_code': row.get('current_question_code') or '',
            'question_text': row.get('current_question_text') or '',
            'answer_text': answer_text,
            'answered_at': 'now',
        })
        resolved = [str(item) for item in (row.get('resolved_gaps_json') or [])]
        remaining = [str(item) for item in (row.get('gaps_json') or [])]
        current_gap = next((item.get('gap') for item in asked_questions if item.get('code') == row.get('current_question_code')), None)
        if current_gap and current_gap in remaining:
            remaining = [item for item in remaining if item != current_gap]
            if current_gap not in resolved:
                resolved.append(current_gap)

        next_question = None
        if len(answers) < len(asked_questions) and len(answers) < int(row.get('max_questions') or settings.mbti_refinement_max_questions):
            next_question = asked_questions[len(answers)]

        current_confidence = int(row.get('current_confidence') or 0)
        new_confidence = min(100, max(current_confidence, current_confidence + 6))

        if next_question is not None and new_confidence < int(row.get('target_confidence') or settings.mbti_refinement_target_confidence):
            updated_row = connection.execute(
                """
                UPDATE session_mbti_refinements
                SET current_confidence = %s,
                    question_count = %s,
                    gaps_json = %s::jsonb,
                    resolved_gaps_json = %s::jsonb,
                    current_question_code = %s,
                    current_question_text = %s,
                    answers_json = %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_confidence,
                    len(answers),
                    json.dumps(remaining, ensure_ascii=False),
                    json.dumps(resolved, ensure_ascii=False),
                    next_question['code'],
                    next_question['text'],
                    json.dumps(answers, ensure_ascii=False),
                    refinement_id,
                ),
            ).fetchone()
            connection.commit()
            return self._row_to_state(updated_row)

        source_summary = row.get('source_summary_json') or session_row.get('mbti_summary_json') or {}
        updated_summary = self._refine_summary(source_summary=source_summary, answers=answers)
        final_confidence = max(new_confidence, self._extract_confidence(updated_summary))
        updated_summary_overall = self._extract_overall(updated_summary)
        if updated_summary_overall and isinstance(updated_summary_overall.get('недостающая_информация'), list):
            updated_summary_overall['недостающая_информация'] = remaining

        completed_row = connection.execute(
            """
            UPDATE session_mbti_refinements
            SET status = 'completed',
                current_confidence = %s,
                question_count = %s,
                gaps_json = %s::jsonb,
                resolved_gaps_json = %s::jsonb,
                current_question_code = NULL,
                current_question_text = NULL,
                answers_json = %s::jsonb,
                updated_summary_json = %s::jsonb,
                updated_at = NOW(),
                completed_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                final_confidence,
                len(answers),
                json.dumps(remaining, ensure_ascii=False),
                json.dumps(resolved, ensure_ascii=False),
                json.dumps(answers, ensure_ascii=False),
                json.dumps(updated_summary, ensure_ascii=False),
                refinement_id,
            ),
        ).fetchone()
        connection.execute(
            """
            UPDATE user_sessions
            SET mbti_summary_json = %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(updated_summary, ensure_ascii=False), session_id),
        )
        connection.commit()
        return self._row_to_state(completed_row)


mbti_refinement_service = MbtiRefinementService()
