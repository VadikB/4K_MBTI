# BC-01/02: полный bundle до нового запуска

Основание: владелец одобрил первый шаг аудита backward-compatibility-audit.md.
База: d68a34b1e77edde9406a6cb5701e7f0ba98148e2; текущая ветка
codex/t08-3-prompt-lab-c54. AGENTS.md и отчёт аудита были изменены ранее.

Результат: новый запуск читает только полный опубликованный bundle с верным
checksum; отсутствующие dimensions методологии не достраиваются из legacy.
Область: PM-02/03/04/05, публикация → конфигурация → snapshot → очередь/старт.
Источники: README, CONTRIBUTING, рабочий цикл/матрица, Change01 И-6,
manifest 2026-10-01, ADR-002 и источники/хеши в отчёте аудита. CURRENT не меняется.
Прочитаны assessment_configuration, authoring_service, prompt_resolver,
preparation_queue, потребитель ролей Agent и authoring integration-тесты.

План: общая проверка публикации/загрузки; регрессия отказа без записи и без чтения
active prompts; backend, HTTP и integration на новой изолированной test-БД.
Критерии: отсутствующий/повреждённый bundle отклоняется; полная конфигурация
работает; изменение active prompts не меняет snapshot; отсутствующие роли/уровни
не восстанавливаются. Для schema v2 отсутствие roles допустимо по её контракту.
Обязательные коды prompts взяты из вызовов текущего интервьюера, не новые нормы.

Не входят: миграция/удаление данных, bootstrap BC-04, PR-B с переносом встроенных
prompts, смена оценщиков, публикация в средах, merge/deploy. Стоп-условия: нет
открытого решения для этой реализации; отказ совместимости уже одобрен.
Схема/владение/PM и права не меняются. Новых предметных значений нет.
Риск выпуска: неполный текущий default перестанет запускаться. До выпуска создать
и опубликовать новый полный configuration через действующий authoring lifecycle;
старый published не править на месте. Точные данные среды не проверялись.
Откат кода — revert изменений шага; новые/исторические snapshots не переписывать.

Проверки и итог будут дополнены после выполнения.

## Итог реализации

Выполнено и проверено локально; по последующему поручению владельца подготовлено к фиксации отдельным коммитом. PR/merge/deploy не выполнялись. Изменены:

- `Api/assessment_configuration.py`: удалён complete_legacy_methodology_definition;
  чтение ролей валидирует определение. Загрузка execution configuration проверяет
  сохранённый checksum и bundle; больше нет load_active_prompt_bundle или UPDATE.
- `Api/assessment_authoring_service.py`: единая validate_execution_bundle для
  публикации и нового исполнения; обязательные dimensions/версия методологии,
  структура bundle, три существующих кода интервьюера, refs/версии/checksum и
  executor вложенных agent definitions. Публикация отклоняется до смены default.
- `tests/unit/test_assessment_configuration.py`: неполные dimensions/bundle,
  повреждённые checksum, отсутствие agent/prompt, отсутствие чтений active/UPDATE.
- `tests/integration/test_assessment_authoring_workflow_db.py`: полный fixture
  публикуется штатно; проверяются отказ без ремонта и сохранность default,
  независимость snapshot от изменённых active prompts.

Прослеживаемость: M1/Change01 И-6 → фиксированные версии C-24/34/45 и execution
snapshot → load_default_execution_configuration/validate_execution_bundle →
unit test_incomplete_bundle_rejected_without_active_reads_or_updates,
integration test_start_rejects_incomplete_configuration_without_repair и
test_execution_uses_published_bundle_after_active_prompts_change.

Полнота здесь — контракт входного bundle текущего execution loader. Это не
объявление устранения всех предметных fallback: case_generation_instructions
может быть пустым списком по существующему формату; встроенные инструкции диалога
и fallback потребителей — BC-03/PR-B. Bootstrap по-прежнему создаёт старую
конфигурацию без bundle; она намеренно не допускается к новому исполнению до
публикации полной конфигурации. BC-04 остаётся открытым. Автоматической миграции нет.

## Фактические проверки

| Команда | Результат |
| --- | --- |
| `npm run test:backend` | PASS: 243 passed, 63 deselected |
| `npm run test:backend:http` | PASS: 22 passed |
| `TEST_DATABASE_URL=postgresql://bc01_test@127.0.0.1:55439/agent4k_bc01_pytest npm run test:backend:integration` | PASS: 38 passed, 268 deselected |
| Адресный integration `tests/integration/test_assessment_authoring_workflow_db.py` | PASS: 13 passed; затем включён в полный набор |
| `git diff --check` | PASS |
| CI / frontend lint/build / LLM / deploy | NOT_RUN: локальное backend-изменение, frontend не менялся; CI обязателен перед merge |

PostgreSQL 15: новый кластер `/tmp/agent4k-bc01-pytest-pg`, отдельный порт 55439,
база с pytest в имени. Рабочие БД не использовались. Первый initdb из libpq не
содержал postgres; установленный PostgreSQL потребовал разрешения shared memory
вне sandbox. После разрешения кластер создан и проверки выполнены, пропусков
integration нет. В тестах есть прежнее предупреждение Starlette/httpx.

Ревью по review-checklist выполнено: новых предметных текстов в runtime не
добавлено, опубликованные записи не исправляются, схема/права не меняются.
Остаточный риск: фактическая полнота default в средах неизвестна; перед выпуском
проверить и создать новый published через lifecycle. Развёртывание без этого
может закрыть новые запуски. Миграцию/сброс не выполнять автоматически.

Следующий шаг: BC-03 — обязательные prompts интервью из версионированного пакета
и snapshot, с явной ошибкой вместо встроенного содержания. До выпуска текущего
шага — отдельный commit/PR, CI и подготовка полной конфигурации. Управляющая
поправка AGENTS.md и аудит остаются отдельными ранее согласованными изменениями.

## Фиксация

По поручению владельца изменения фиксируются в отдельной ветке
`codex/strict-execution-bundle` от проверенной базы d68a34b. Правило AGENTS и
аудит — отдельный коммит, реализация с тестами и этим отчётом — следующий.
Точные SHA выдаются в итоговом ответе после коммитов. Результаты тестов выше
переиспользованы: после прогонов код и тесты не менялись.
