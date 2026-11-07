# AC18-FIX-02 / P2-AC01 — корреляция результатов tester-batch

## Результат и границы

Ветка `codex/ac18-fix02-tester-correlation` от `157d77d1` (`origin/main`):
результат проверки учитывается только в той пачке `required_check_ids`, для которой
был запрошен. Возврат `check_id` из другой пачки больше не может закрыть отсутствующий
результат и ошибочно допустить AS. То же правило применяется к challenger. Это
локальное техническое исправление, а не закрытие всего P2-01/P2-AC01/P2-AC02.

Не меняются: применимость, статусы и агрегация, frozen prompts, версия протокола,
repair policy, схема БД, публичный API и данные. Реальный провайдер не вызывается.

## Источники, решение и стоп-условие

- Процесс: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`,
  `docs/evc/review-checklist.md`; архитектурный контекст/Registry, Change 01,
  task manifest и адресные M5-контракты прочитаны ранее в этом чате.
- Действующий tester protocol v2: `docs/evc/protocols/m5-functional-personalization-tester-v2.json`;
  frozen addendum: `assessment_definitions/prompts/m5_functional_protocol/v1/tester-addendum.md`;
  код: `Api/m5_functional_generation_service.py`, `Api/m5_functional_tester.py`;
  регрессия: `tests/unit/test_m5_functional_generation_service.py`.
- `tester-addendum.md` требует один JSON-объект с единственным верхнеуровневым
  полем `checks`. Поэтому явный `candidate_checksum` в ответе нельзя требовать
  без новой версии артефакта и согласованного контракта. Попытка такой локальной
  правки отменена до фиксации результата. Существующие input checksum/routing key
  связывают вызов и вход, но не доказывают, что модель содержательно оценила именно
  этот кандидат. Тест «review другого кандидата» остаётся открытым.
- Для операции `64344f28-e9de-4bcc-9173-27376a33ea0b` доступно сообщение об
  отказе, но не первичные provider responses/trace. Причина именно того инцидента
  не установлена. Исторический `PREP-DIAG-01` не объединяется с ним.
- Стоп-условия: предметный смысл/публичный контракт/новый артефакт — **да** только
  для требования нового поля ответа, эта зависимая работа остановлена;
  миграция/секреты/развёртывание/несогласованный откат — **нет** для текущего
  технического исправления. Владелец должен отдельно решить, нужен ли новый
  versioned tester output contract для явной кандидатной корреляции.

## Проверки и доказательство дефекта

Синтетический gateway возвращает первый `check_id` не в запрошенной первой пачке,
а один раз в последующей. На исходной логике объединения всех пачек тест
`test_tester_rejects_check_returned_by_wrong_batch` дал **FAIL**:
`admitted_for_participant=True`. После фильтрации по `required_check_ids` —
**PASS**, отсутствующий check имеет `NOT_RUN`, admission закрыт.

- `git diff --check` — PASS.
- `PYTHON_DOTENV_DISABLED=1 /Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -q tests/unit/test_m5_functional_generation_service.py` — 20 PASS.
- `PYTHON_DOTENV_DISABLED=1 /Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -q -m 'not integration and not e2e and not llm'` — 957 PASS, 354 deselected; один существующий Starlette deprecation warning.
- `npm run test:backend` из worktree — NOT_RUN: там нет `.venv/bin/python`; тот же pytest-набор выполнен абсолютным путём к venv репозитория.
- CI, integration/HTTP на изолированной PostgreSQL, browser, real provider — NOT_RUN для этого локального шага. P2-AC02 и полный P2-AC01 пока не закрыты.

## Состояние и откат

Изменены только `Api/m5_functional_generation_service.py` и адресный unit-тест;
этот файл отчёта — документация шага. Push/PR/merge/deploy/version bump не
выполнены. Откат — revert локального коммита до включения в main; данные не
мигрируются. Следующий независимый шаг — P2-AC02 на изолированной PostgreSQL;
зависимый — решение владельца о новом контракте корреляции кандидата. Для
создания draft PR нужна отдельная команда пользователя; Ready/merge/deploy этим
шагом не разрешаются.
