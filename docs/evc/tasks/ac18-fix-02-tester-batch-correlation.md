# AC18-FIX-02 / P2-AC01 — корреляция результатов tester-batch

## Результат и границы

Ветка `codex/ac18-fix02-tester-correlation` от `157d77d1` (`origin/main`):
результат проверки учитывается только в той пачке `required_check_ids`, для которой
был запрошен. Возврат `check_id` из другой пачки больше не может закрыть отсутствующий
результат и ошибочно допустить AS. То же правило применяется к challenger. Дополнительно
проверены оба терминальных отказа через очередь, изолированную PostgreSQL и HTTP-readback.
Это техническое исправление и регрессия P2-AC02, но не закрытие всего P2-AC01.

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
  регрессии: `tests/unit/test_m5_functional_generation_service.py`,
  `tests/integration/test_m10_product_path_db.py`.
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
- `TEST_DATABASE_URL=postgresql://postgres:***@127.0.0.1:55000/ac18_pytest ... python -m pytest --run-integration -q tests/integration/test_m10_product_path_db.py -k functional_catalog` — 8 PASS, 10 deselected. Синтетические `INCOMPLETE` и `FAIL` проверены после worker: сохранены `result_json.generated.tester`, обязательный `common.confidentiality`, профиль; `m5_assessment_situations=0`, нет `started_at` и dialogue turns. Два HTTP GET той же операции не увеличивают счётчик provider calls и не переписывают диагностический результат.
- `npm run test:backend` из worktree — NOT_RUN: там нет `.venv/bin/python`; тот же pytest-набор выполнен абсолютным путём к venv репозитория.
- CI, browser, real provider — NOT_RUN. Историческая операция не воспроизведена; полный P2-AC01 остаётся открыт из-за отсутствия первичного trace и нерешённой корреляции кандидата.

## Состояние и откат

Изменены `Api/m5_functional_generation_service.py` и адресные unit/integration-тесты;
этот файл отчёта — документация шага. Push/PR/merge/deploy/version bump не
выполнены. Откат — revert локальных коммитов до включения в main; данные не
мигрируются. Следующий зависимый шаг — решение владельца о новом контракте
корреляции кандидата. Для
создания draft PR нужна отдельная команда пользователя; Ready/merge/deploy этим
шагом не разрешаются.
