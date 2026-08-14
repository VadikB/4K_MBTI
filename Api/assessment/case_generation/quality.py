from __future__ import annotations

import re
import zlib
from typing import Any

import psycopg
from psycopg.rows import dict_row

from Api.case_text_cleanup import cleanup_case_list, cleanup_case_text, join_case_list
from Api.config import settings
from Api.assessment.case_generation.specificity import CaseSpecificityMixin
from Api.assessment.case_generation.scene_builder import CaseSceneBuilderMixin
from Api.assessment.case_generation.text_pipeline import CaseTextPipelineMixin

CASE_TEXT_GENERIC_PATTERNS = (
    r"\bоперационн(?:ая|ый|ое)\s+команд",
    r"\bключев(?:ой|ая|ое)\s+рабоч(?:ий|ая|ее)\s+процесс",
    r"\bрабоч(?:ая|ий|ее)\s+систем",
    r"\bрабоч(?:ий|ая|ее)\s+объект",
    r"\bтипов(?:ой|ая|ое)\s+участник",
    r"\bтипов(?:ой|ая|ое)\s+процесс",
    r"\bтипов(?:ой|ая|ое)\s+артефакт",
    r"\bтекущая\s+операционная\s+работа\s+команд",
    r"\bпервом\s+источнике\s+данных\s+и\s+в\s+втором\s+источнике",
)


class CaseQualityMixin(CaseSceneBuilderMixin, CaseTextPipelineMixin, CaseSpecificityMixin):























































    def _light_polish_template_locked_context(self, text: str, *, role_name: str | None) -> str:
        result = self._sanitize_user_case_text(text, role_name=role_name)
        if not result:
            return ""
        result = self._remove_template_guidance_blocks(result)
        result = re.sub(r"\bот\s+пользователь\b", "от пользователя", result, flags=re.IGNORECASE)
        result = re.sub(r"\bот\s+пользователи\b", "от пользователей", result, flags=re.IGNORECASE)
        result = re.sub(r"\bчерез\s+в\s+", "в ", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bкарточка заявки,\s*истори(?:й|и)\s+комментариев\s+и\s+статус(?:а|у)\s+в\s+Service\s+Desk\b",
            "карточке заявки, истории комментариев и статусу в Service Desk",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bподход\s+к\s+обновление\b", "подход к обновлению", result, flags=re.IGNORECASE)
        result = re.sub(r"\bподход\s+к\s+изменение\b", "подход к изменению", result, flags=re.IGNORECASE)
        result = re.sub(r"\bподход\s+к\s+подготовка\b", "подход к подготовке", result, flags=re.IGNORECASE)
        result = re.sub(r"\bклиентской поддержки и 1 смежный координатор на эскалациях\b", "2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях", result, flags=re.IGNORECASE)
        result = re.sub(r"\bклиентская поддержка и сопровождение обращений к клиент ждет\b", "в процессе клиентской поддержки клиент ждет", result, flags=re.IGNORECASE)
        result = re.sub(r"\bвокруг обновление клиента\b", "вокруг обновления клиента", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result).strip()
        if result and result[-1] not in ".!?":
            result += "."
        return result



































    def enforce_user_case_quality(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        case_context: str,
        case_task: str,
        role_name: str | None,
        company_industry: str | None,
        case_specificity: dict[str, Any] | None,
        existing_contexts: list[str] | None = None,
    ) -> tuple[str, str]:
        current_context = self._restore_minimum_case_context(
            (case_context or "").strip(),
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        current_task = (case_task or "").strip()
        if not current_context:
            return current_context, current_task

        locked_context = self._build_template_locked_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        if locked_context and not self._should_bypass_template_locked_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        ) and not self._should_use_strict_scene_narrative(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        ):
            current_context = self._light_polish_template_locked_context(locked_context, role_name=role_name)
            current_context = self._build_structured_user_case_context(
                context_text=current_context,
                case_specificity=case_specificity,
            )
            current_context = self._proofread_user_case_text(current_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
            current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
            return current_context.strip(), current_task

        prior_contexts = [str(item).strip() for item in (existing_contexts or []) if str(item).strip()]
        if not prior_contexts:
            current_context = self._proofread_user_case_text(current_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
            current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
            return current_context, current_task

        if self._case_text_is_too_similar(current_context, prior_contexts):
            rebuilt = self._rebuild_context_from_type(
                case_type_code=case_type_code,
                case_title=case_title,
                case_specificity=case_specificity,
            )
            if rebuilt and rebuilt != current_context:
                current_context = rebuilt
            if self._case_text_is_too_similar(current_context, prior_contexts):
                current_context = self._diversify_case_context(
                    current_context,
                    case_type_code=case_type_code,
                    case_title=case_title,
                    case_specificity=case_specificity,
                )

        current_context = self._sanitize_user_case_text(current_context, role_name=role_name)
        current_context = self._polish_user_case_context(
            current_context,
            role_name=role_name,
            case_title=case_title,
            company_industry=company_industry,
        )
        current_context = self._build_structured_user_case_context(
            context_text=current_context,
            case_specificity=case_specificity,
        )
        current_task = cleanup_case_text(current_task)
        if len(current_task) < 40:
            current_task = self._polish_user_case_task(
                current_task,
                case_title=case_title,
                context_text=current_context,
                case_type_code=case_type_code,
            )
            current_task = cleanup_case_text(current_task)
        quality = self._evaluate_user_case_quality(
            case_context=current_context,
            case_task=current_task,
            case_specificity=case_specificity,
        )
        if quality["passed"]:
            current_context = self._proofread_user_case_text(current_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
            current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
            return current_context.strip(), current_task

        rebuilt = self._rebuild_context_from_type(
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        if rebuilt and rebuilt != current_context:
            rebuilt = self._sanitize_user_case_text(rebuilt, role_name=role_name)
            rebuilt = self._polish_user_case_context(
                rebuilt,
                role_name=role_name,
                case_title=case_title,
                company_industry=company_industry,
            )
            rebuilt = self._build_structured_user_case_context(
                context_text=rebuilt,
                case_specificity=case_specificity,
            )
            rebuilt_quality = self._evaluate_user_case_quality(
                case_context=rebuilt,
                case_task=current_task,
                case_specificity=case_specificity,
            )
            if rebuilt_quality["passed"]:
                rebuilt = self._proofread_user_case_text(rebuilt, role_name=role_name, is_task=False, case_type_code=case_type_code)
                current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
                return rebuilt.strip(), current_task

        minimum_context = self._restore_minimum_case_context(
            current_context,
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        minimum_context = self._sanitize_user_case_text(minimum_context, role_name=role_name)
        minimum_context = self._polish_user_case_context(
            minimum_context,
            role_name=role_name,
            case_title=case_title,
            company_industry=company_industry,
        )
        minimum_context = self._build_structured_user_case_context(
            context_text=minimum_context,
            case_specificity=case_specificity,
        )
        if len(current_task) < 40:
            current_task = self._polish_user_case_task(
                current_task,
                case_title=case_title,
                context_text=minimum_context,
                case_type_code=case_type_code,
            )
            current_task = cleanup_case_text(current_task)
        minimum_context = self._proofread_user_case_text(minimum_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
        current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
        return minimum_context.strip(), current_task













    def _evaluate_user_case_quality(
        self,
        *,
        case_context: str,
        case_task: str,
        case_specificity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        context = cleanup_case_text(case_context)
        task = cleanup_case_text(case_task)
        issues: list[str] = []
        specificity = dict(case_specificity or {})

        if not context or len(context) < 140:
            issues.append("context_too_short")
        if "{" in context or "}" in context or "{" in task or "}" in task:
            issues.append("placeholder_leak")
        if ".." in context or ". ." in context:
            issues.append("punctuation_noise")
        if any(re.search(pattern, context, flags=re.IGNORECASE) for pattern in CASE_TEXT_GENERIC_PATTERNS):
            issues.append("too_generic")

        problem_markers = [
            str(specificity.get("bottleneck") or "").strip(),
            str(specificity.get("business_impact") or "").strip(),
            str(specificity.get("primary_stakeholder") or "").strip(),
            str(specificity.get("critical_step") or "").strip(),
        ]
        matched_markers = 0
        lowered_context = context.lower()
        for marker in problem_markers:
            if marker and marker.lower() in lowered_context:
                matched_markers += 1
        if matched_markers < 2 and len(context) < 220:
            issues.append("not_specific_enough")

        if not any(word in lowered_context for word in ("риск", "огранич", "следующ", "срок", "этап", "шаг")):
            issues.append("missing_case_anchor")
        if not task or len(task) < 30:
            issues.append("task_too_short")

        return {
            "passed": not issues,
            "issues": issues,
        }

    def _rebuild_context_from_type(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        type_code = str(case_type_code or "").upper()
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title=case_title,
                case_context="",
                case_task="",
            ),
        )
        if type_code not in {"F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}:
            return ""
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            return str(
                self._build_strict_scene_narrative(
                    case_type_code=type_code,
                    case_specificity=specificity,
                ) or ""
            ).strip()
        if self._should_bypass_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            return str(
                self._apply_plot_skeleton(
                    "",
                    case_type_code=type_code,
                    case_title=case_title,
                    case_specificity=specificity,
                ) or ""
            ).strip()
        locked_context = self._build_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        )
        if locked_context:
            return locked_context.strip()
        return str(
            self._apply_plot_skeleton(
                "",
                case_type_code=type_code,
                case_title=case_title,
                case_specificity=specificity,
            ) or ""
        ).strip()

    def _diversify_case_context(
        self,
        text: str,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        current = (text or "").strip()
        if not current:
            return ""
        type_code = str(case_type_code or "").upper()
        title_source = str(case_title or "").lower()
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title="",
                case_context=current,
                case_task="",
            ),
        )
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            strict = self._build_strict_scene_narrative(
                case_type_code=type_code,
                case_specificity=specificity,
            )
            return strict.strip() if strict else current
        title_specific_addition = ""
        if type_code == "F05":
            if any(word in title_source for word in ("роли", "состав", "групп")):
                title_specific_addition = (
                    "Здесь важно заранее договориться о ролях, спорных решениях и координации."
                )
            else:
                title_specific_addition = (
                    "Здесь нужно быстро разложить задачи по людям и не допустить провисания следующего шага."
                )
        elif type_code == "F08":
            if any(word in title_source for word in ("перегруз", "главного", "приоритет")):
                title_specific_addition = (
                    "Здесь нужно выбрать главный приоритет, потому что ошибка в первом действии задержит остальные задачи."
                )
            else:
                title_specific_addition = (
                    "Ключевая сложность в том, что задачи срочные по-разному, и первый выбор влияет на остальные."
                )
        additions = {
            "F05": "Важно не только распределить загрузку, но и договориться, кто держит контроль и когда команда возвращается с обновлением.",
            "F08": "Ошибка в приоритете здесь приведет к лишней задержке и повторной работе.",
            "F09": "Важно увидеть, на каком шаге процесса команда теряет время и где появляется повторная работа.",
            "F10": self._describe_current_idea(specificity),
            "F11": "Результат уже хотят передавать дальше, хотя критичный шаг проверки еще не закрыт.",
            "F12": "Разговор нужен, чтобы закрепить новый порядок действий и не повторить ту же ошибку.",
        }
        extra = str(title_specific_addition or additions.get(type_code) or "").strip()
        if not extra or extra in current:
            return current
        return f"{current} {extra}".strip()

    def _normalize_case_similarity_text(self, text: str) -> set[str]:
        cleaned = re.sub(r"[^a-zA-Zа-яА-Я0-9\s]", " ", str(text or "").lower())
        tokens = [token for token in cleaned.split() if len(token) > 2]
        stop_words = {
            "это", "как", "что", "где", "для", "при", "или", "уже", "нужно", "сейчас",
            "если", "часть", "этом", "такой", "когда", "после", "между", "чтобы",
            "будет", "также", "который", "которые", "процессу", "процессе",
        }
        return {token for token in tokens if token not in stop_words}

    def _case_text_similarity_score(self, left: str, right: str) -> float:
        left_tokens = self._normalize_case_similarity_text(left)
        right_tokens = self._normalize_case_similarity_text(right)
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = left_tokens & right_tokens
        union = left_tokens | right_tokens
        if not union:
            return 0.0
        return len(intersection) / len(union)

    def _case_text_is_too_similar(self, current: str, existing_contexts: list[str]) -> bool:
        current_clean = (current or "").strip()
        if not current_clean:
            return False
        current_head = current_clean[:180].lower()
        for previous in existing_contexts:
            prev_clean = (previous or "").strip()
            if not prev_clean:
                continue
            if current_head == prev_clean[:180].lower():
                return True
            if self._case_text_similarity_score(current_clean, prev_clean) >= 0.72:
                return True
        return False

    def _restore_minimum_case_context(
        self,
        text: str,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        current = (text or "").strip()
        type_code = str(case_type_code or "").upper()
        if not current:
            return current

        sentence_count = len([part for part in re.split(r"(?<=[.!?])\s+", current) if part.strip()])
        if sentence_count >= 3 and len(current) >= 220:
            return current

        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title=case_title,
                case_context=current,
                case_task="",
            ),
        )
        if type_code not in {"F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}:
            return current
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            strict = self._build_strict_scene_narrative(
                case_type_code=type_code,
                case_specificity=specificity,
            )
            return strict.strip() or current
        if self._should_bypass_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            rebuilt = self._apply_plot_skeleton(
                current,
                case_type_code=type_code,
                case_title=case_title,
                case_specificity=specificity,
            ).strip()
            return rebuilt or current
        locked_context = self._build_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        )
        if locked_context:
            return locked_context.strip()
        rebuilt = self._apply_plot_skeleton(
            current,
            case_type_code=type_code,
            case_title=case_title,
            case_specificity=specificity,
        ).strip()
        return rebuilt or current
