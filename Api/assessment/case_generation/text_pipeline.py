from __future__ import annotations

import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from Api.case_text_cleanup import cleanup_case_text
from Api.config import settings


class CaseTextPipelineMixin:
    def _humanize_role_name(self, role_name: str | None, position: str | None = None) -> str:
        role = (role_name or position or "").strip()
        lowered = role.lower()
        if not lowered:
            return "специалист"
        if lowered in {"l", "linear", "line"} or "линей" in lowered:
            return "линейный сотрудник"
        if lowered in {"m", "manager"} or "менедж" in lowered or "руковод" in lowered:
            return "менеджер"
        if lowered == "leader" or "лидер" in lowered or "дир" in lowered or "стратег" in lowered:
            return "лидер"
        return lowered

    def _proofread_user_case_text(
        self,
        text: str,
        *,
        role_name: str | None,
        is_task: bool,
        case_type_code: str | None = None,
    ) -> str:
        result = cleanup_case_text(text)
        result = self._apply_case_prompt_grammar_rules(result)
        result = self._humanize_generated_case_language(result)
        result = self._apply_instruction_driven_case_text_cleanup(
            result,
            case_type_code=case_type_code,
            is_task=is_task,
        )
        result = re.sub(r"\bв процессе\s+обработк([аиуыое])\b", "в процессе обработки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+сбоя\b", "по вопросу сбоя", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+отсутствия\b", "по вопросу отсутствия", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(эта|это) может улучшить\b", "Это может улучшить", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпока неясно, стоит ли запускать изменение сразу и как сделать это безопасно\b", "Пока неясно, стоит ли запускать изменение сразу и как сделать это безопасно", result, flags=re.IGNORECASE)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        result = re.sub(r"([,.;:!?])([^\s\n])", r"\1 \2", result)
        result = re.sub(r"\.\s*\.", ".", result)
        result = re.sub(r":\s*\.", ":", result)
        result = re.sub(r"\bлинейный сотрудник\b", "линейный сотрудник", result, flags=re.IGNORECASE)
        result = self._dedupe_case_text_repetitions(result, is_task=is_task)
        result = self._normalize_prompt_sentences(result)
        if not is_task:
            result = re.sub(r"^(Ситуация:\s*\*\*[^*]+\*\*)\s+([А-ЯЁA-Z])", r"\1\n\n\2", result, count=1)
            result = re.sub(r"\s+(\*\*Что известно\*\*)", r"\n\n\1", result, flags=re.IGNORECASE)
            result = re.sub(r"\s+(\*\*Что ограничивает\*\*)", r"\n\n\1", result, flags=re.IGNORECASE)
            result = re.sub(r"(\*\*Что известно\*\*)\s*-", r"\1\n-", result, flags=re.IGNORECASE)
            result = re.sub(r"(\*\*Что ограничивает\*\*)\s*-", r"\1\n-", result, flags=re.IGNORECASE)
            result = re.sub(r"\n{3,}", "\n\n", result)
        if role_name:
            result = result.replace("в роли линейного аналитика", f"в роли {self._resolve_role_scope(role_name).split(':')[0].strip().lower()}")
        if is_task and result and not result.lower().startswith("что нужно сделать"):
            result = f"Что нужно сделать: {result[0].upper() + result[1:] if result else result}"
        if is_task and result and not result.endswith((".", "!", "?")):
            result += "."
        result = result.replace("потому что Это может", "потому что это может")
        result = result.replace(", но Пока неясно", ", но пока неясно")
        result = re.sub(
            r"^\s*2 специалиста\s+В распоряжении команды сейчас 2 специалиста\s+2 специалиста\s+клиентской поддержки and 1 смежный координатор на эскалациях\.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*2 специалиста\s+В распоряжении команды сейчас 2 специалиста\s+2 специалиста\s+клиентской поддержки и 1 смежный координатор на эскалациях\.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            result,
            flags=re.IGNORECASE,
        )
        result = result.replace(
            "2 специалиста В распоряжении команды сейчас 2 специалиста 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
        )
        result = result.replace(
            "В распоряжении команды сейчас 2 специалиста 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
        )
        return result.strip()

    def _apply_instruction_driven_case_text_cleanup(
        self,
        text: str,
        *,
        case_type_code: str | None,
        is_task: bool,
    ) -> str:
        result = cleanup_case_text(text)
        if not is_task:
            result = self._restore_case_section_spacing(result)
        result = self._repair_case_text_fragments(result, is_task=is_task)
        result = self._strip_unresolved_case_placeholders(result, is_task=is_task)
        if not is_task:
            result = self._restore_case_section_spacing(result)
        return cleanup_case_text(result)

    def _repair_case_text_fragments(self, text: str, *, is_task: bool) -> str:
        result = str(text or "").strip()
        if not result:
            return ""

        phrase_replacements = (
            (
                r"\bКлиентской поддержки и 1 смежный координатор на эскалациях;\s*горизонт работы\s*—\s*([0-9: ]+до[0-9: ]+|[^.]+)\.",
                r"В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях. Горизонт работы — \1.",
            ),
            (
                r"\bКлиентской поддержки и 1 смежный координатор на эскалациях\b",
                "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях",
            ),
            (
                r"\bВ доступе сейчас только В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях\b",
                "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях",
            ),
            (
                r"\bСтавки высокие:\s*на кону\s+стабильность работы на этом участке:\s*стабильность работы:\s*",
                "Ставки высокие: на кону стабильность работы на этом участке — ",
            ),
            (
                r"\bприв[её]л к повторная жалоба клиента, эскалация и снижение доверия к сервису\b",
                "привел к повторной жалобе клиента, эскалации и снижению доверия к сервису",
            ),
            (
                r"\bиз клиентская поддержка, смежная сервисная команда и руководитель направления\b",
                "из клиентской поддержки, смежной сервисной команды и руководителя направления",
            ),
            (
                r"\bесть данные из карточка обращения, история коммуникации в CRM и внутренние комментарии команды\b",
                "есть данные из карточки обращения, истории коммуникации в CRM и внутренних комментариев команды",
            ),
            (
                r"\n?Сейчас\.\s*$",
                "",
            ),
            (
                r"\bКлиентская поддержка и сопровождение обращений к клиент ждет обновление\b",
                "В процессе клиентской поддержки клиент ждет обновление",
            ),
            (
                r"\bЭто касается \*\*дневная сервисная смена\b",
                "Это касается **дневной сервисной смены",
            ),
            (
                r"\bбудут заметны для клиент\b",
                "будут заметны для клиента",
            ),
            (
                r"\bвокруг обновление клиента\b",
                "вокруг обновления клиента",
            ),
            (
                r"\bэто может улучшить\b",
                "Это может улучшить",
            ),
            (
                r"\bно пока неясно\b",
                "Но пока неясно",
            ),
            (
                r"\bпотому что Это может\b",
                "потому что это может",
            ),
            (
                r"\bно Пока неясно\b",
                "но пока неясно",
            ),
            (
                r"\bдля клиент\b",
                "для клиента",
            ),
            (
                r"\bКлючевой стейкхолдер\b",
                "Ключевой участник",
            ),
            (
                r"\bключевой стейкхолдер\b",
                "ключевой участник",
            ),
            (
                r"\b1:\s+1\b",
                "1:1",
            ),
            (
                r"Что нужно сделать:\s*Что нужно сделать:\s*",
                "Что нужно сделать:\n",
            ),
        )
        for pattern, replacement in phrase_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        result = re.sub(
            r"(?:\b2 специалиста\s+){2,}",
            "2 специалиста ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"В распоряжении команды сейчас\s+(?:2 специалиста\s+){2,}клиентской поддержки",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:В распоряжении команды сейчас 2 специалиста\s+){2,}",
            "В распоряжении команды сейчас 2 специалиста ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях\.\s*){2,}",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях. ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*2 специалиста\s+В распоряжении команды сейчас 2 специалиста\s+",
            "В распоряжении команды сейчас 2 специалиста ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*В распоряжении команды сейчас 2 специалиста\s+2 специалиста\s+клиентской поддержки",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bклиента{2,}\b", "клиента", result, flags=re.IGNORECASE)
        result = re.sub(r",\s*Но пока неясно\b", ", но пока неясно", result)
        result = re.sub(r"\bпотому что\s+Это может\b", "потому что это может", result)
        result = re.sub(r"\bвокруг обновления клиента по обращению и фиксация следующего шага\b", "вокруг обновления клиента по обращению и фиксации следующего шага", result, flags=re.IGNORECASE)
        result = re.sub(r"\b([А-ЯЁа-яё]+)\s+ждет обновление\b", lambda m: f"{m.group(1)} ждет обновления", result)
        result = re.sub(r"\bв процессе \*\*([^*]+)\*\* команда снова и снова возвращается к одним и тем же вопросам вокруг ([^.,]+)", r"В процессе **\1** команда снова и снова возвращается к одним и тем же вопросам вокруг \2", result)
        result = re.sub(r"\bпо обращениям клиентов часть статусов уже обновлена, но подтверждение результата и следующий шаг по обращению фиксируются не до конца\b", "По обращениям клиентов часть статусов уже обновлена, но подтвержденный результат и следующий шаг фиксируются не полностью", result, flags=re.IGNORECASE)
        result = re.sub(r"\bобращение закрывают или передают дальше раньше, чем подтвержден фактический результат, следующий шаг и обновление пользователя\b", "обращение закрывают или передают дальше раньше, чем подтверждены фактический результат, следующий шаг и обновление клиента", result, flags=re.IGNORECASE)
        result = re.sub(r"\bрешение по запуску идеи будут обсуждать\b", "Решение по запуску идеи будут обсуждать", result, flags=re.IGNORECASE)
        result = re.sub(
            r"(?:^|\s)Оцениваемый\s*[—:-]\s*[^.?!]*(?:\{[^}]+\}[^.?!]*)[.?!]?",
            " ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:^|\s)Оцениваемый\s*[—:-]\s*[^.?!]*(?:;[^.?!]*){0,6}[.?!]?",
            " ",
            result,
            flags=re.IGNORECASE,
        )
        result = self._strip_unresolved_case_placeholders(result, is_task=is_task)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def _strip_unresolved_case_placeholders(self, text: str, *, is_task: bool) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        result = re.sub(r"\{[^{}]{1,80}\}", "", result)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s+([,.;:])", r"\1", result)
        result = re.sub(r"([,.;:])(?=[^\s])", r"\1 ", result)
        result = re.sub(r"(?:\s*;\s*){2,}", "; ", result)
        result = re.sub(r"\s+\.", ".", result)
        if not is_task:
            result = re.sub(r"(?:^|\s)[;,:-]\s*(?=[А-ЯЁа-яё])", " ", result)
        return cleanup_case_text(result).strip()

    def _restore_case_section_spacing(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        value = re.sub(r"^\s*(Ситуация:\s*\*\*[^*]+\*\*)\s*", r"\1\n\n", value, count=1, flags=re.IGNORECASE)
        value = re.sub(r"\s*(\*\*Что известно\*\*)", r"\n\n\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*(\*\*Что ограничивает\*\*)", r"\n\n\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*(Что нужно сделать:)", r"\n\n\1", value, flags=re.IGNORECASE)
        value = re.sub(r"(\*\*Что известно\*\*)\s*[-•]", r"\1\n- ", value, flags=re.IGNORECASE)
        value = re.sub(r"(\*\*Что ограничивает\*\*)\s*[-•]", r"\1\n- ", value, flags=re.IGNORECASE)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    def _humanize_generated_case_language(self, text: str) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        replacements = (
            (r"(\d+),\s+(\d+)", r"\1,\2"),
            (r"(\d{1,2}):\s+(\d{2})", r"\1:\2"),
            (r"([0-9%])\s+(Проверить детали можно по)\b", r"\1. \2"),
            (r"([0-9%])\s+(Если ничего не сделать сейчас)\b", r"\1. \2"),
            (r"([0-9%])\s+(Одновременно внимания требуют)\b", r"\1. \2"),
            (r"\bи пишет, что\b", "и сообщает, что"),
            (r"\bне складываются в одну картину\b", "дают противоречивую картину"),
            (r"\bдругая часть предупреждает о рисках\b", "другая часть указывает на риски"),
            (r"\bа по нескольким вопросам данных все еще недостаточно\b", "а по нескольким вопросам данных пока недостаточно"),
            (r"\bв контуре рабочая группа участка\b", "на этом участке"),
            (r"\bв контуре команды ([^.,;\n]+)\b", r"в работе команды \1"),
            (r"\bнужно быстро принять решение по ситуации:\s*что\b", "нужно быстро решить, что"),
            (r"\bНужно быстро принять решение по ситуации\s+что\b", "Нужно быстро решить, что"),
            (r"\bпоследствия будут такими:\s*срыв\b", "последствия будут такими: возможен срыв"),
            (r"\bпоследствия будут такими:\s*перенос\b", "последствия будут такими: возможен перенос"),
            (r"\bпоследствия будут такими:\s*повторное согласование\b", "последствия будут такими: возможно повторное согласование"),
            (r"\bпоследствия будут такими:\s*ошибки\b", "последствия будут такими: возможны ошибки"),
            (r"\bна кону ([^.,;\n]+) на этом участке\b", r"на кону \1 на этом участке"),
        )
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def _dedupe_case_text_repetitions(self, text: str, *, is_task: bool) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        value = re.sub(r"(?:Что нужно сделать:\s*){2,}", "Что нужно сделать: ", value, flags=re.IGNORECASE)
        value = re.sub(
            r"(?:^|\n)Сейчас в фокусе ситуация\s+«[^»]+»\.\s*",
            "\n",
            value,
            flags=re.IGNORECASE,
        )
        if is_task:
            value = re.sub(r"^(?:Что нужно сделать:\s*)+", "Что нужно сделать: ", value, flags=re.IGNORECASE)

        def _line_key(line: str) -> str:
            normalized = re.sub(r"\*\*", "", line or "")
            normalized = re.sub(r"[.:!?]+$", "", normalized.strip(), flags=re.IGNORECASE)
            return normalized.lower()

        def _value_signature(line: str) -> set[str]:
            payload = re.sub(r"^-\s*(?:Проверка идет по|Доступно|В фокусе):\s*", "", line, flags=re.IGNORECASE)
            payload = payload.replace(" и ", ", ")
            chunks = [
                re.sub(r"\s+", " ", chunk.strip().lower())
                for chunk in re.split(r",", payload)
                if chunk.strip()
            ]
            if chunks:
                return set(chunks)
            tokens = re.findall(r"[а-яёa-z0-9-]{4,}", payload.lower())
            return set(tokens)

        deduped_lines: list[str] = []
        seen_line_keys: set[str] = set()
        last_check_signature: set[str] = set()
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            key = _line_key(line)
            if key and key in seen_line_keys:
                continue
            if re.match(r"^-\s*Проверка идет по:", line, flags=re.IGNORECASE):
                last_check_signature = _value_signature(line)
            elif re.match(r"^-\s*Доступно:", line, flags=re.IGNORECASE):
                available_signature = _value_signature(line)
                if last_check_signature and available_signature:
                    overlap = len(last_check_signature & available_signature)
                    baseline = max(len(last_check_signature), len(available_signature), 1)
                    if overlap / baseline >= 0.6:
                        continue
            if key:
                seen_line_keys.add(key)
            deduped_lines.append(line)

        value = "\n".join(deduped_lines)

        normalized_rows: list[str] = []
        seen_sentence_keys: set[str] = set()
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            sentences = re.split(r"(?<=[.!?])\s+", line)
            deduped_sentences: list[str] = []
            for raw_sentence in sentences:
                sentence = raw_sentence.strip()
                if not sentence:
                    continue
                key = re.sub(r"\s+", " ", re.sub(r"[.:!?]+$", "", sentence)).strip().lower()
                if len(key) >= 18 and key in seen_sentence_keys:
                    continue
                if len(key) >= 18:
                    seen_sentence_keys.add(key)
                deduped_sentences.append(sentence)
            if deduped_sentences:
                normalized_rows.append(" ".join(deduped_sentences))

        value = "\n".join(normalized_rows) if normalized_rows else value
        value = re.sub(r"\s+\n", "\n", value)
        value = re.sub(r"\n\s+", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"\s{2,}", " ", value)
        return value.strip()

    def _sanitize_user_case_text(self, text: str | None, *, role_name: str | None) -> str:
        result = str(text or "").strip()
        if not result:
            return ""

        human_role = self._humanize_role_name(role_name)
        role_phrase = f"в роли {human_role}"

        replacements = {
            "в роли Линейный сотрудник": role_phrase if human_role == "линейный сотрудник" else f"в роли {human_role}",
            "в роли линейный сотрудник": role_phrase if human_role == "линейный сотрудник" else f"в роли {human_role}",
            "в роли Менеджер": f"в роли {human_role}" if human_role == "менеджер" else role_phrase,
            "в роли Лидер": f"в роли {human_role}" if human_role == "лидер" else role_phrase,
            "в роли M": f"в роли {human_role}",
            "в роли L": f"в роли {human_role}",
            "в роли Leader": f"в роли {human_role}",
            "для M": "для управленческой роли",
            "для L": "для роли исполнителя",
            "для Leader": "для лидерской роли",
            "L/M": "роли пользователя",
            "часть работы действительно велась": "часть работы действительно была выполнена",
            "ему обещали вернуться с ответом": "ему обещали предоставить ответ",
            "к текущему моменту": "к настоящему моменту",
            "тем человеком, кому нужно первым ответить": "тем сотрудником, которому нужно первым ответить",
        }
        for source, target in replacements.items():
            result = result.replace(source, target)

        result = re.sub(r"\bесли\s+кейс\s+персонализирован\s+под\s+L\b.*?(?:[.!?]|$)", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bесли\s+под\s+M\b.*?(?:[.!?]|$)", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bесли\s+кейс\s+персонализирован\s+под\s+M\b.*?(?:[.!?]|$)", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+L\s*[—-]\s*[^.]+", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+M\s*[—-]\s*[^.]+", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+Leader\s*[—-]\s*[^.]+", "", result, flags=re.IGNORECASE)
        result = re.sub(
            r"(пишет,\s+что\s+по\s+вопросу\s+.+?)\s+(ему\s+обещали\s+(?:предоставить\s+ответ|вернуться\s+с\s+ответом))",
            r"\1, \2",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bпо\s+вопросу\s+([^.,!?]+?)\s+было\s+отмечено\s+как\s+выполненное\b",
            r"по вопросу «\1» было отмечено как выполненное",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"по вопросу «тикет «([^»]+)»", r"по вопросу «\1»", result, flags=re.IGNORECASE)
        result = re.sub(r"\bориентир\s+к\s+до\s+(\d{1,2}:\d{2})\b", r"ориентир до \1", result, flags=re.IGNORECASE)
        result = re.sub(r"««\s*", "«", result)
        result = re.sub(r"\s*»»", "»", result)
        result = re.sub(r"(?:,\s*|\s+)и\s+сейчас\.$", ".", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпоявилось\s+узкое\s+место\s+появилось\s+узкое\s+место\b", "появилось узкое место", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо\s+какой\s+показателях\b", "по каким показателям", result, flags=re.IGNORECASE)
        result = re.sub(r"(%|\bчас(?:ов|а)?|\bдней?|\bминут)\s+Основн(?:ая|ое)\s+проблем", r"\1. Основная проблем", result, flags=re.IGNORECASE)
        result = re.sub(
            r"В распоряжении команды сейчас\s+(?:2 специалиста\s+){2,}клиентской поддержки",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:\b2 специалиста\s+){3,}клиентской поддержки",
            "2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )

        result = re.sub(r"\bв роли\s+(?:L|M|Leader)\b", role_phrase, result, flags=re.IGNORECASE)
        result = re.sub(r"\b(изменений нет|нет изменений|нет измеенний|не изменилось|не изменений|без изменений)\b", human_role, result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\n\s*\n+", "\n\n", result)
        result = re.sub(r"\.\.", ".", result)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        result = self._apply_case_prompt_grammar_rules(result)
        if result:
            result = result[0].upper() + result[1:]
        return result.strip()

    def _polish_user_case_context(
        self,
        text: str,
        *,
        role_name: str | None,
        case_title: str,
        company_industry: str | None,
    ) -> str:
        result = (text or "").strip()
        if not result:
            return ""

        human_role = self._humanize_role_name(role_name)
        replacements = {
            "Вы работаете в роли": "Вы работаете как",
            "и участвуете в процессе": "и участвуете в работе по",
            "пишет, что": "сообщает, что",
            "теряет доверие к вашей стороне": "теряет доверие к вашей команде",
            "У вас есть доступ": "У вас есть доступ",
            "Сейчас именно вы оказались тем сотрудником": "Сейчас именно вам нужно",
            "кому нужно первым ответить на жалобу": "первым ответить на жалобу",
            "инициатор запроса": "клиент",
            "карточке тикета": "внутренней карточке обращения",
            "карточке запроса": "внутренней карточке обращения",
        }
        for source, target in replacements.items():
            result = result.replace(source, target)

        result = re.sub(r"\bв контуре\s+операционн(?:ая|ой)\s+команд[аы]\b", "в группе операционного сопровождения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв контуре\s+([^,.]+?)\s+команд[аы]\b", r"в команде \1", result, flags=re.IGNORECASE)
        result = re.sub(r"\bнужно выполнить обработка\b", "нужно выполнить обработку", result, flags=re.IGNORECASE)
        result = re.sub(r"\bриски нарушение\b", "риски нарушения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bнеполные входные данные и ограничения работа\b", "неполные входные данные и ограничения по работе", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкак\s+линейного\s+сотрудника\b", "как линейный сотрудник", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкак\s+менеджера\b", "как менеджер", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкак\s+лидера\b", "как лидер", result, flags=re.IGNORECASE)
        result = result.replace("ограничения по работе по скриптам", "обязательная работа по скриптам")
        result = re.sub(r"\bклиенты написал\b", "клиент написал", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка обращения\b", "карточке обращения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка задачи\b", "карточке задачи", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка заявки,\s*истори(?:й|и)\s+комментариев\s+и\s+статус(?:а|у)\s+в\s+Service\s+Desk\b", "карточке заявки, истории комментариев и статусу в Service Desk", result, flags=re.IGNORECASE)
        result = re.sub(r"\bистория комментариев и база требований\b", "истории комментариев и базе требований", result, flags=re.IGNORECASE)
        result = re.sub(r"\bиз\s+ваша\s+смена\s+поддержки\s+и\s+вторая\s+линия\b", "из вашей смены поддержки и второй линии", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдоступный\s+сотрудник\s+и\s+ограниченное\s+рабочее\s+время\b", "два сотрудника и ограниченное время смены", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо\s+каналу\s+очередь\s+обращений\s+и\s+служебный\s+чат\s+смены\b", "через очередь обращений и служебный чат смены", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо\s+каналу\s+очередь\s+задач\s+и\s+комментарии\s+в\s+jira\b", "в комментариях к задаче в Jira", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв\s+процессе\s+подготовка\s+требований\b", "в процессе подготовки требований", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкоманда\s+второй\s+линии\s+поддержки\b", "смежная команда второй линии поддержки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+срыв\s+sla\b", "по вопросу срыва SLA", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+неверная\s+трактовка\s+требований\b", "по вопросу неверной трактовки требований", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bпо вопросу\s+подтверждение статуса судовой операции и следующего шага экипажа\b",
            "по вопросу подтверждения статуса судовой операции и следующего шага экипажа",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bизвестно о\s+неполная запись следующего маневра в судовом журнале\b",
            "известно о неполной записи следующего маневра в судовом журнале",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bв процесс вовлечены\s+вахта «Браво» и старший помощник\b",
            "в процесс вовлечены вахта «Браво» и старший помощник капитана",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bпо его словам,\s+обращение\s+по вопросу\s+неверной\s+трактовки\s+требований\s+было\s+отмечено\s+как\s+выполненное,\s+но\s+нужный\s+результат\s+он\s+так\s+и\s+не\s+получил\b",
            "По его словам, задача уже отмечена как выполненная, но согласованного ТЗ и финального результата он так и не получил",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bчерез\s+в\s+комментариях\b", "в комментариях", result, flags=re.IGNORECASE)
        result = re.sub(r"\bограничения\s+закрытию\s+заявок\b", "ограничения по закрытию заявок", result, flags=re.IGNORECASE)
        result = re.sub(r"\bесть\s+закрытию\s+заявок\b", "есть ограничения по закрытию заявок", result, flags=re.IGNORECASE)
        result = re.sub(r"\bошибок в процессе обслуживание гостей и работа бара\b", "ошибок в процессе обслуживания гостей и работы бара", result, flags=re.IGNORECASE)
        result = re.sub(r"\bможет привести к обслуживание гостей и работа бара\b", "может привести к сбоям в обслуживании гостей и работе бара", result, flags=re.IGNORECASE)
        result = re.sub(r"\bна\s+показателях\b", "на показатели", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдополнительные\s+срыва\s+сроков\b", "дополнительным срывам сроков", result, flags=re.IGNORECASE)
        result = re.sub(r"\bЭто\s+касается\s+вечерняя\s+смена\b", "Это касается вечерней смены", result, flags=re.IGNORECASE)
        result = re.sub(r"\bЭто\s+касается\s+линия\b", "Это касается линии", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв\s+процессе\s+поддержка\s+рабочих\s+мест\s+и\s+заявок\s+пользователей\b", "в процессе поддержки рабочих мест и заявок пользователей", result, flags=re.IGNORECASE)
        result = re.sub(r"\bможет\s+привести\s+к\s+поддержка\s+рабочих\s+мест\s+и\s+обработка\s+заявок\s+пользователей\b", "может привести к сбоям в поддержке рабочих мест и обработке заявок пользователей", result, flags=re.IGNORECASE)
        result = re.sub(r"\bВ этом контуре уже вовлечены\b", "В распределении работы уже участвуют", result, flags=re.IGNORECASE)
        result = re.sub(r"\bПо ситуации уже вовлечены\b", "В согласовании по этой ситуации уже участвуют", result, flags=re.IGNORECASE)
        result = re.sub(r"\bНа этот участок уже смотрят\b", "На результаты этого участка уже ориентируются", result, flags=re.IGNORECASE)
        result = re.sub(r"\bо\s+пользователях/клиентах\s+пользователь\b", "о пользователях и клиентах", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпользователях/клиентах\s+пользователь\b", "пользователях и клиентах", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв системе видно,\s+что статус обращения уже изменён\b", "В системе видно, что статус обращения уже изменён", result, flags=re.IGNORECASE)
        result = re.sub(r"\bметрике\s+время\s+обработки\b", "метрике времени обработки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bот\s+смежная\s+команда\s+второй\s+линии\s+поддержки\b", "от смежной команды второй линии поддержки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bинцидент\s+типа\s+некорректное\s+закрытие\s+обращения\b", "инцидент, связанный с некорректным закрытием обращения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bповторная\s+жалоба\s+клиента\s+и\s+задержка\s+следующего\s+шага\s+по\s+обращению\b", "повторная жалоба клиента и задержка следующего шага по обращению", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+обращение\s+закрывается\s+по\s+статусу\s+раньше,?\s+чем\s+клиент\s+действительно\s+получает\s+решение\b", "потому что обращения закрываются по статусу раньше, чем клиент действительно получает решение", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bПоведение\s+(.+?)\s+повторяется\s+и\s+уже\s+влияет\s+на\b",
            r"Проблема повторяется: \1. Это уже влияет на",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bНужно\s+назвать\s+факты,\s+услышать\s+собеседника,\s+согласовать\s+план\s+развития\s+на\s+([^,]+),\s+определить\s+([^,]+?)\s+и\s+зафиксировать\b",
            r"Нужно назвать факты, услышать собеседника и согласовать план развития. Контрольную точку стоит назначить на \1. Отдельно нужно определить, кто именно отвечает за следующие действия. Учитывайте текущий состав: \2. Договоренности важно зафиксировать",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bУчитывайте\s+текущий\s+состав:\s+3\s+человека\s+на\s+мостике\s+и\s+старший\s+помощник\s+капитана\s+на\s+подтверждении\s+и\s+зафиксировать\b",
            "Учитывайте текущий состав: 3 человека на мостике и старший помощник капитана на подтверждении. Договоренности важно зафиксировать",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bот вас ожидают короткий постмортем по локальному инциденту: что случилось, какие вероятные причины лежат в основе, какие меры нужно принять сейчас и что поменять, чтобы это не повторилось\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bлинейная роль здесь валидна только на локальном уровне\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bлинейная роль здесь валидна только как координация мини-группы\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bлинейная роль не должна брать на себя изменение внешних обязательств, чужих приоритетов или финальных сроков за пределами своего мандата\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bу линейной роли нет права угрожать санкциями, менять чужие приоритеты или обещать решения за руководителя\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bхороший ответ должен показывать рабочий способ договориться и при необходимости корректно эскалировать вопрос\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bхороший ответ должен показать реалистичный план, а не формальное распределение «всем поровну»\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bможно опираться на факты, обозначать влияние, предлагать правила взаимодействия и при необходимости зафиксировать, что следующий шаг — эскалация по правилу\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпри нехватке данных нужно уточнять и при необходимости эскалировать, а не домысливать или обещать лишнее\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв разбор уже входят конкретные элементы:\b", "Для разбора уже доступны конкретные материалы:", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв работе уже есть конкретные задачи:\b", "Сейчас в работе уже есть конкретные задачи:", result, flags=re.IGNORECASE)
        result = re.sub(r"\bсейчас нужно провести личный разговор так, чтобы не сорваться в обвинения, сохранить рабочие отношения и добиться ясной договорённости\b", "Сейчас важно провести разговор спокойно, сохранить рабочие отношения и прийти к ясной договоренности", result, flags=re.IGNORECASE)
        result = re.sub(r"\bОпирайтесь на факты, обозначайте влияние и предлагайте понятный следующий шаг\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bДля разговора уже есть конкретный контекст:\b", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bСейчас важно провести разговор спокойно, сохранить рабочие отношения и прийти к ясной договоренности\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bСитуация:\s*", "", result, flags=re.IGNORECASE)

        result = re.sub(r"^вы\s+работаете\s+как\s+(?:линейный\s+сотрудник|менеджер|лидер)\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"^вы\s+работаете\s+(?:линейным\s+сотрудником|менеджером|лидером)\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"^вы\s*—\s*(?:линейный\s+сотрудник|менеджер|лидер)\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"^\s*и\s+отвечаете\s+за\s+[^.]+?\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\.\s*и\s+отвечаете\s+за\s+[^.]+?\.\s*", ". ", result, flags=re.IGNORECASE)

        result = re.sub(r"\bименно вам нужно первым ответить на жалобу\b", "вам нужно первым ответить клиенту", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпервого ответа клиенту\b", "первого ответа заказчику", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпервым ответить клиенту\b", "первым ответить заказчику", result, flags=re.IGNORECASE)
        result = re.sub(r"\bчасть работы действительно была выполнена, однако клиент этого не видит\b", "часть работы уже выполнена, но клиент этого не видит", result, flags=re.IGNORECASE)
        result = re.sub(r"\bследующий шаг нигде явно не зафиксирован\b", "следующий шаг нигде явно не зафиксирован", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо его обращению обещали вернуться с ответом\b", "по его обращению обещали дать ответ", result, flags=re.IGNORECASE)
        result = re.sub(r"\bэтого не произошло\b", "этого не случилось", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо внутренней карточке обращения видно\b", "Во внутренней карточке обращения видно", result, flags=re.IGNORECASE)
        result = re.sub(r"\bно клиент этого не видит\b", "но клиент об этом не знает", result, flags=re.IGNORECASE)
        result = re.sub(r"\bа следующий шаг по обращению нигде явно не зафиксирован\b", "а следующий шаг по обращению нигде явно не зафиксирован", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bЗадержки в обработке обращений напрямую влияют на рабочие процессы клиентов\.\s*",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"([.!?])\s*,\s*работающ(?:ий|ая|ее|его|ему|ем)\s+[^.]+?\.",
            r"\1",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*,\s*работающ(?:ий|ая|ее|его|ему|ем)\s+[^.]+?\.\s*",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"([^.]{170,}?),\s+но\s+", r"\1. Но ", result)
        result = re.sub(r"([^.]{170,}?),\s+а\s+", r"\1. А ", result)
        result = re.sub(r"([^.]{170,}?),\s+и\s+при\s+этом\s+", r"\1. При этом ", result, flags=re.IGNORECASE)
        result = re.sub(r"\bПри этом цена ошибки уже заметна, но\.", "При этом цена ошибки уже заметна.", result, flags=re.IGNORECASE)
        result = re.sub(r"\.\s*,", ".", result)
        result = re.sub(r"\.\s+\.", ".", result)
        result = re.sub(r"\s{2,}", " ", result).strip()
        if result and result[-1] not in ".!?":
            result += "."
        return result

    def _get_case_text_build_instruction(self, case_type_code: str | None) -> dict[str, Any] | None:
        code = str(case_type_code or "").strip().upper()
        cache_key = code or "*"
        if cache_key in self._case_text_build_instruction_cache:
            return self._case_text_build_instruction_cache[cache_key]
        try:
            with psycopg.connect(
                host=settings.db_host,
                port=settings.db_port,
                dbname=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                row_factory=dict_row,
            ) as connection:
                row = connection.execute(
                    """
                    SELECT instruction_code, instruction_name, applies_to_type_code, structure_mode,
                           instruction_text, priority, version
                    FROM case_text_build_instructions
                    WHERE is_active = TRUE
                      AND (applies_to_type_code = %s OR applies_to_type_code IS NULL)
                    ORDER BY
                        CASE WHEN applies_to_type_code = %s THEN 0 ELSE 1 END,
                        priority ASC,
                        version DESC
                    LIMIT 1
                    """,
                    (code or None, code or None),
                ).fetchone()
        except Exception:
            row = None
        instruction = dict(row) if row else None
        self._case_text_build_instruction_cache[cache_key] = instruction
        return instruction

    def _get_case_template_requirements(self, case_type_code: str | None) -> dict[str, Any]:
        return {}

    def _build_user_visible_case_task(
        self,
        *,
        case_type_code: str | None,
        context_text: str,
        case_title: str,
    ) -> str:
        requirements = self._get_case_template_requirements(case_type_code)
        task_style = str(requirements.get("task_style") or "").strip().lower()
        if not task_style:
            instruction = self._get_case_text_build_instruction(case_type_code)
            task_style = str((instruction or {}).get("structure_mode") or "").strip().lower()
        if not task_style:
            task_style = {
                "F01": "answer_message",
                "F02": "clarification",
                "F03": "conversation",
                "F04": "alignment_action",
                "F05": "coordination_plan",
                "F06": "message_or_ticket",
                "F07": "structured_decision",
                "F08": "prioritization",
                "F09": "improvement_ideas",
                "F10": "idea_evaluation",
                "F11": "message_or_ticket",
                "F12": "development_conversation",
            }.get(str(case_type_code or "").strip().upper(), "")
        lower_context = f"{case_title} {context_text}".lower()
        if task_style == "answer_message" and "заказчик" in lower_context and any(word in lower_context for word in ("jira", "тз", "разработ", "проект")):
            return "Как вы ответите заказчику в этой ситуации?"
        return self._build_user_visible_task_from_style(task_style=task_style)

    def _build_user_visible_task_from_style(self, *, task_style: str) -> str:
        style = str(task_style or "").strip().lower()
        mapping = {
            "answer_message": "Как вы ответите в этой ситуации?",
            "clarification": "Что вы сделаете, чтобы уточнить запрос и зафиксировать понимание задачи?",
            "conversation": "Как вы проведете этот разговор и о чем договоритесь по его итогам?",
            "alignment_action": "Как вы будете согласовывать следующий шаг в этой ситуации?",
            "coordination_plan": "Как вы организуете работу команды в этой ситуации?",
            "structured_decision": "Какое решение вы примете в этой ситуации и что будете проверять дальше?",
            "prioritization": "Что вы сделаете в первую очередь и почему?",
            "improvement_ideas": "Какие улучшения вы предложите для этой ситуации?",
            "idea_evaluation": "Как вы оцените эту идею и какое решение по ней примете?",
            "message_or_ticket": "Как вы будете действовать перед передачей работы дальше?",
            "development_conversation": "Как вы проведете эту развивающую беседу?",
        }
        return mapping.get(style) or "Что вы будете делать в этой ситуации?"

    def _polish_user_case_task(self, text: str, *, case_title: str, context_text: str, case_type_code: str | None = None) -> str:
        result = (text or "").strip()
        if not result:
            result = ""
        type_code = str(case_type_code or "").strip().upper()
        requirements = self._get_case_template_requirements(type_code)
        required_task_text = str(requirements.get("required_task_text") or "").strip()
        user_visible_task = self._build_user_visible_case_task(
            case_type_code=type_code,
            context_text=context_text,
            case_title=case_title,
        )
        generic_task_markers = {
            "как вы ответите?",
            "как вы будете действовать?",
            "что вы сделаете в первую очередь и почему?",
            "составьте рабочий план действий.",
            "предложите решение.",
            "разберите проблему и предложите, что нужно сделать сейчас и что изменить, чтобы она не повторилась.",
        }
        if (
            required_task_text
            and type_code in {"F01", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}
            and (not result or len(result) < 70 or result.strip().lower() in generic_task_markers)
        ):
            return user_visible_task
        if result == required_task_text:
            return user_visible_task
        if result and len(result) >= 70:
            return result
        lower_context = f"{case_title} {context_text} {result}".lower()
        if type_code in {"F07", "F09", "F10", "F12"} and user_visible_task:
            return user_visible_task
        if (
            any(actor in lower_context for actor in ("клиент", "заказчик"))
            and any(
                phrase in lower_context
                for phrase in (
                    "ответ клиент",
                    "ответить клиент",
                    "сообщение клиент",
                    "письмо клиент",
                    "первого ответа",
                    "первым ответить клиенту",
                    "ответ заказчик",
                    "ответить заказчик",
                    "сообщение заказчик",
                    "письмо заказчик",
                    "жалоб",
                    "комментариях к задаче",
                    "чат поддержки",
                )
            )
            and not any(word in lower_context for word in ("разговор", "бесед", "коллег", "личный разговор"))
        ):
            if "заказчик" in lower_context and any(word in lower_context for word in ("jira", "тз", "требован", "разработ")):
                return "Как вы ответите заказчику в этой ситуации?"
            return "Как вы ответите в этой ситуации?"
        if any(word in lower_context for word in ("выбор действия", "противоречив", "неопределен", "неопределён", "неполных данных")):
            return "Какое решение вы примете в этой ситуации и что будете проверять дальше?"
        if any(word in lower_context for word in ("приоритизац", "что делать в первую очередь", "главное", "конфликт срочности", "перегруз")):
            return "Что вы сделаете в первую очередь и почему?"
        if any(word in lower_context for word in ("разговор", "бесед", "коллег", "развивающ", "личный разговор")):
            return "Как вы проведете этот разговор и о чем договоритесь по его итогам?"
        if any(word in lower_context for word in ("согласован", "смежн", "эскалац", "инцидент", "сбой")):
            return "Как вы будете действовать в этой ситуации?"
        if any(word in lower_context for word in ("план", "распредел", "команд", "групп", "смен", "координац", "роли")):
            return "Как вы организуете работу команды в этой ситуации?"
        if any(word in lower_context for word in ("иде", "вариант", "решени", "гипотез")):
            return user_visible_task
        return user_visible_task

    def _resolve_role_scope(self, role_name: str | None) -> str:
        role = (role_name or "").lower()
        if "линей" in role:
            return "уровень участка"
        if "manager" in role or "менедж" in role or "руковод" in role:
            return "уровень команды или процесса"
        if "leader" in role or "дир" in role or "стратег" in role:
            return "уровень направления или нескольких команд"
        return "масштаб, соответствующий роли пользователя"

    def _apply_case_prompt_grammar_rules(self, text: str) -> str:
        result = text or ""
        phrase_replacements = {
            "в роли Линейный сотрудник": "в роли линейного сотрудника",
            "в роли Менеджер": "в роли менеджера",
            "в роли Лидер": "в роли лидера",
            "в роли линейный аналитик": "в роли линейного сотрудника",
            "в роли линейный сотрудник": "в роли линейного сотрудника",
            "в процессе обработка ": "в процессе обработки ",
            "по вопросу сбой ": "по вопросу сбоя ",
            "по вопросу отсутствие ": "по вопросу отсутствия ",
            "не может вовремя продвинуть завершить": "не может вовремя завершить",
            "к карточка тикета": "к карточке тикета",
            "к карточка запроса": "к карточке запроса",
            "У вас есть доступ к карточка тикета": "У вас есть доступ к карточке тикета",
            "У вас есть доступ к карточка запроса": "У вас есть доступ к карточке запроса",
            "часть работы действительно велась": "часть работы действительно была выполнена",
            "ему обещали вернуться с ответом": "ему обещали предоставить ответ",
            "к текущему моменту": "к настоящему моменту",
            "тем человеком, кому нужно первым ответить": "тем сотрудником, которому необходимо первым ответить",
            "Сейчас именно вы оказались тем сотрудником, которому нужно первым ответить на жалобу": "Сейчас именно вам нужно первым ответить на жалобу",
            "Сейчас именно.": "Сейчас именно вам нужно первым ответить на жалобу.",
            "по каналу через почта": "по электронной почте",
            "Проверять ситуацию приходится по": "Проверить детали можно по",
            "не может завершить согласовать": "не может согласовать",
            "не может вовремя продвинуть согласовать": "не может вовремя согласовать",
            "продвинуть согласовать": "согласовать",
            "как распределить следующий шаг по программе": "что делать со следующим шагом по программе",
            "Перед вами стоит дилемма: нужно быстро принять решение по ситуации": "Нужно быстро принять решение по ситуации",
            "Что бы вы предложили?": "Что вы предложите?",
            "Клиентской поддержки и 1 смежный координатор на эскалациях": "клиентской поддержки и 1 смежный координатор на эскалациях",
            "От клиент, руководитель клиентской поддержки и смежная сервисная команда поступило резкое письмо": "От клиента поступило резкое письмо, копия ушла руководителю клиентской поддержки и смежной сервисной команде",
            "От заказчик поступило резкое письмо": "От заказчика поступило резкое письмо",
            "под угрозой оказывается конструкторского блока": "под угрозой оказываются показатели конструкторского блока",
            "уже известно о работа в рамках регламента": "уже известно, что часть действий выполнялась по регламенту",
            "не может завершить проверку фактического результата, фиксацию следующего шага и обновление пользователя": "не может дождаться подтверждения фактического результата, следующего шага и обновления по обращению",
            "Клиентская поддержка и сопровождение обращений к клиент ждет обновление": "В процессе клиентской поддержки клиент ждет обновление",
            "Это касается **дневная сервисная смена": "Это касается **дневной сервисной смены",
            "будут заметны для клиент": "будут заметны для клиента",
            "вокруг обновление клиента": "вокруг обновления клиента",
        }
        for source, target in phrase_replacements.items():
            result = result.replace(source, target)

        regex_replacements = (
            (r"\bв роли\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)\b", self._normalize_role_phrase),
            (r"\bв процессе\s+обработк([аиуыое])\b", "в процессе обработки"),
            (r"\bпо вопросу\s+сбой\b", "по вопросу сбоя"),
            (r"\bпо вопросу\s+отсутствие\b", "по вопросу отсутствия"),
            (r"\bне может вовремя\s+продвинуть\s+завершить\b", "не может вовремя завершить"),
            (r"\bне может(?:\s+вовремя)?\s+завершить\s+согласовать\b", "не может согласовать"),
            (r"\bне может(?:\s+вовремя)?\s+продвинуть\s+согласовать\b", "не может согласовать"),
            (r"\bк карточка тикета\b", "к карточке тикета"),
            (r"\bк карточка запроса\b", "к карточке запроса"),
            (r"\bпо вопросу отсутствие обратной связи\b", "по вопросу отсутствия обратной связи"),
            (r"\bсбой в отображении данных\b", "сбоя в отображении данных"),
            (r"\bв течение\s+(\d+)\s+рабочих?\s+часов\b", r"в течение \1 рабочих часов"),
            (r"(\d+),\s+(\d+)", r"\1,\2"),
            (r"\bименно вы оказались тем человеком, кому нужно первым ответить\b", "именно вы оказались тем сотрудником, которому необходимо первым ответить"),
            (r"\bвопросу\s+сбоя\b", "вопросу сбоя"),
            (r"\bему обещали предоставить ответ до старта программы осталось (\d+) рабочих дня\b", r"ему обещали предоставить ответ в течение ближайших \1 рабочих дней"),
            (r"\bориентир до старта программы осталось (\d+) рабочих дня\b", r"ориентир: до старта программы осталось \1 рабочих дня"),
            (r"\bПеред вами стоит дилемма:\s*нужно быстро принять решение по ситуации\s*", "Нужно быстро принять решение по ситуации: "),
            (r"\bПроверять ситуацию приходится по\b", "Проверить детали можно по"),
            (r"([0-9%])\s+(Проверить детали можно по)\b", r"\1. \2"),
            (r"([0-9%])\s+(Если ничего не сделать сейчас)\b", r"\1. \2"),
            (r"([0-9%])\s+(Одновременно внимания требуют)\b", r"\1. \2"),
            (r"\bПроверить детали можно по бриф на обучение, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта\b", "Проверить детали можно по брифу на обучение, ТЗ подрядчику, программе курса и комментариям внутреннего эксперта"),
            (r"\bсерь[её]зных срыва сроков, повторных доработок и ошибок в процессе клиентская поддержка и сопровождение обращений\b", "срыва сроков, повторных доработок и ошибок в процессе клиентской поддержки и сопровождения обращений"),
            (r"\bСтавки высокие: на кону клиентская поддержка и сопровождение обращений в контуре рабочая группа участка\b", "Ставки высокие: на кону стабильность клиентской поддержки и сопровождения обращений на этом участке"),
            (r"\bДанные из ([^.]+) не складываются в одну картину: одни сигналы поддерживают более быстрый и выгодный курс, другие предупреждают о ([^.]+), а третьи оставляют зону неопредел[её]нности\b", r"Данные из \1 не складываются в одну картину: часть сигналов говорит в пользу более быстрого решения, другая часть предупреждает о рисках — \2, а по нескольким вопросам данных все еще недостаточно"),
            (r"\bОт клиент, руководитель клиентской поддержки и смежная сервисная команда поступило резкое письмо\b", "От клиента поступило резкое письмо, копия ушла руководителю клиентской поддержки и смежной сервисной команде"),
            (r"\bпод угрозой оказывается клиентского сервиса:\s*([^.]+)\b", r"под угрозой оказываются показатели клиентского сервиса: \1"),
            (r"\bпод угрозой оказывается конструкторского блока:\s*([^.]+)\b", r"под угрозой оказываются показатели конструкторского блока: \1"),
            (r"\bуже известно о работа в рамках регламента, фиксация действий в системе и обязательная эскалация спорных решений\b", "уже известно, что часть действий выполнялась по регламенту, фиксировалась в системе и при необходимости эскалировалась"),
            (r"\bпо вопросу ([^,]+), ему обещали\b", r"по вопросу «\1», ему обещали"),
            (r"по вопросу ««([^»]+)»»", r"по вопросу «\1»"),
            (r"Сейчас именно\.", "Сейчас именно вам нужно первым ответить на жалобу."),
            (r"\bдо\s+(\d{1,2}):\s+(\d{2})\b", r"до \1:\2"),
            (r"\bне может завершить проверку фактического результата, фиксацию следующего шага и обновление пользователя\b", "не может дождаться подтверждения фактического результата, следующего шага и обновления по обращению"),
            (r"\bНужно быстро принять решение по ситуации что делать в первую очередь, если\b", "Нужно быстро решить, что делать в первую очередь, если"),
            (r"\bПо одним данным из брифы на обучение, карточки программ в LMS/HRM, календарь обучения и обратная связь участников\b", "По одним данным из брифа на обучение, карточки программы в LMS/HRM, календаря обучения и обратной связи участников"),
            (r"\bв контуре команда обучения и развития персонала\b", "в контуре команды обучения и развития персонала"),
            (r"\bв контуре рабочая группа участка\b", "на этом участке"),
            (r"\bнужно не просто выбрать вариант, а показать управленческую логику\b", "нужно не просто выбрать вариант, а коротко объяснить логику решения"),
            (r"\bкак вы принимаете решение сейчас, что проверяете в первую очередь и по какому сигналу готовы пересмотреть курс\b", "какие факты вы проверяете в первую очередь, какое решение принимаете сейчас и в каком случае готовы его пересмотреть"),
            (r"\bПроверка идет по финальная версия программы, комментарии заказчика и карточка обучения в LMS/HRM\b", "Проверка идет по финальной версии программы, комментариям заказчика и карточке обучения в LMS/HRM"),
            (r"\bПроверка идет по бриф на обучение, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта\b", "Проверка идет по брифу на обучение, ТЗ подрядчику, программе курса и комментариям внутреннего эксперта"),
            (r"\bПроверка идет по список участников, комментарии руководителя подразделения и карточка запуска программы\b", "Проверка идет по списку участников, комментариям руководителя подразделения и карточке запуска программы"),
            (r"\bПроверка идет по календарь обучения, график подразделения и подтверждения руководителя по датам\b", "Проверка идет по календарю обучения, графику подразделения и подтверждениям руководителя по датам"),
            (r"\bПроверка идет по анкеты обратной связи, комментарии участников и карточка результатов пилота\b", "Проверка идет по анкетам обратной связи, комментариям участников и карточке результатов пилота"),
            (r"\bПроверка идет по карточка обучения, комментарии заказчика и история договоренностей по следующему шагу\b", "Проверка идет по карточке обучения, комментариям заказчика и истории договоренностей по следующему шагу"),
            (r"\bДоступно: финальная программа курса, комментарии заказчика и карточка обучения и дата старта в LMS/HRM\b", "Доступно: финальная программа курса, комментарии заказчика, карточка обучения и дата старта в LMS/HRM"),
            (r"\bДоступно: список участников, карточка программы и календарь обучения и комментарии руководителя подразделения\b", "Доступно: список участников, карточка программы, календарь обучения и комментарии руководителя подразделения"),
            (r"\bДоступно: анкеты обратной связи и карточка результатов пилота и комментарии участников и эксперта\b", "Доступно: анкеты обратной связи, карточка результатов пилота и комментарии участников и эксперта"),
            (r"\bДоступно: карточка обучения, история договоренностей и комментарии заказчика и журнал задач по программе\b", "Доступно: карточка обучения, история договоренностей, комментарии заказчика и журнал задач по программе"),
            (r"\bпривед[её]т к планирование и организация обучения сотрудников\b", "может сорвать планирование и организацию обучения сотрудников"),
            (r"\bне получил ни решения, ни обновления статуса\b", "не получил ни решения, ни обновления статуса"),
            (r"\bчасть работы действительно была выполнена, но клиент этого не видит\b", "часть работы действительно была выполнена, однако клиент этого не видит"),
            (r"\bа следующий шаг никем явно не зафиксирован\b", "а следующий шаг нигде явно не зафиксирован"),
        )
        for pattern, replacement in regex_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        result = re.sub(r"\bпо вопросу отсутствия обратной связи после обещанного срока\b", "по вопросу отсутствия обратной связи после обещанного срока", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка тикета\b", "карточке тикета", result)
        result = re.sub(r"\bкарточка запроса\b", "карточке запроса", result)
        result = re.sub(r"\bне может вовремя завершить анализ\b", "не может вовремя завершить анализ", result)
        result = re.sub(r"\bне может вовремя завершить переход\b", "не может вовремя перейти", result)
        return result.strip()

    def _normalize_role_phrase(self, match: re.Match[str]) -> str:
        phrase = match.group(1).strip().lower()
        mapping = {
            "линейный сотрудник": "в роли линейного сотрудника",
            "менеджер": "в роли менеджера",
            "лидер": "в роли лидера",
        }
        return mapping.get(phrase, match.group(0))
