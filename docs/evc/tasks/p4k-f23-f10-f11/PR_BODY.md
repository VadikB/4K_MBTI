# P4K-F23-F10-F11: идемпотентные права администратора и сквозная проверка программы

## Результат

Повторное назначение уже действующего администратора больше не обновляет
`admitted_at`/`updated_at`; повторное снятие прав сохраняет первоначальную запись
`configured_access_suppressions`. После grant/revoke UI заново читает список
организаций перед сообщением об успехе: в сквозном тесте был воспроизведён
пустой список администраторов при подтверждённом сервером grant.
Участие, личная оценка и сохранённые источники остаются независимыми.
Добавлены actual HTTP/PG, publisher lifecycle и сквозной
browser/HTTP/PG сценарии на owned синтетических данных.

## Область

- `Api/routes.py`: только повторные admin grant/revoke.
- `web/js/screens/admin/organizations.js` и производный `web/dist`: точный
  readback после grant/revoke.
- `tests/integration/test_f01_role_isolation_db.py`: повторные команды и участие.
- `tests/integration/test_f10_publisher_db.py`: dry-run, недопустимые зависимости,
  синтетическая публикация.
- `tests/integration/test_arch30_program_definition_db.py`: A→B, replay,
  история, отказ draft/retired, контрольная B.
- `tests/browser/f23-f10-f11-combined.spec.mjs` и
  `tests/f23_f10_f11_browser_fixture.py`: один owned сценарий S→U→A→B→revoke,
  сохранённые binding и синтетический Cycle A.
- `docs/evc/tasks/p4k-f23-f10-f11/{TASK,STATE,CHECKS,PR_BODY}.md`: основания,
  статусы AC, доказательства и передача.

Публичный API, схема, runtime-артефакты, published definitions и существующие
данные не изменены. Обратная совместимость: да. Откат: revert этого diff без
миграции и cleanup только marker-owned тестовых ресурсов.

## Проверки и остаток

Точные команды, результаты и SHA — `CHECKS.md`. До merge требуются актуальные
обязательные CI `frontend`, `pytest`, `full-verification`, человеческое review,
релизная подготовка по `ready:prepare` после согласования версии и отдельная
визуальная приёмка на разрешённом TEST после readback deployed SHA/версии.
Рабочая публикация общей программы не выполнялась: `artifact_publish=false`.
Реальные письма/LLM и полный EXEC не выполнялись по границе задачи.

После создания draft PR #212 владелец утвердил PATCH `2.0.100` и перевод в
`Ready for review`. Штатный `ready:prepare` прошёл на свежем `origin/main`
(`2.0.99`) с четырьмя файлами версии и пересборкой `web/dist`. На исходном
head draft CI `frontend` и `pytest` прошли; `full-verification` запустится
после перевода PR в review. Итог release head и CI сверяются перед merge.

Первый полный CI на release head выявил гонку в новом combined browser-тесте:
он принимал текст `<option>` за завершённое подключение. Ожидание A/B исправлено
на точный UI readback `Подключено`; адресный повтор на owned PG — PASS. Полный
CI на commit исправления обязателен до merge.

## Риски

- Конфиг: нет новых параметров.
- Схема/миграция: нет.
- Безопасность: серверная авторизация сохраняется; synthetic data без реальных
  персональных данных и секретов; cleanup проверен.
- Деплой: отдельный этап; этот PR сам по себе не доказывает TEST.
- Откат: revert собственных файлов, без перепривязки исторических назначений.
