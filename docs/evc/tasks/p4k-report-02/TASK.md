# P4K-REPORT-02 — права на отчёт и удаление выбора получателей

## Результат и границы

Владелец читает сохранённый Report после обычного прекращения членства; действующий администратор читает отчёты сохранённой организации Cycle. Выбор получателей не влияет на права и отсутствует в действующих формах и API. Изменяются только доступ к M8, проекции, связанный questionnaire/административный переход и адресная схема. REPORT-08 (новый список) и процедуры удаления аккаунта не входят.

## Основания и прослеживаемость

- Запрос владельца и `P4K_REPORT_02_Access_Recipients.txt` 1.0 от 15.11.2026; решения 4–5 из `reference/CURRENT_PRODUCT_DECISIONS.txt` того же пакета.
- Product Architecture v1.0 + Change 01 WORKING, И-1/5–7, PM-06/07, LU-07.2; M1 v1.4 FROZEN/CURRENT=NO; M8 v1.2 FROZEN/CURRENT=NO, §§7.1–7.2, 9; `docs/adr/002-cycle-as-dialogue-contracts.md` C-46/C-56/C-67. Выбранные файлы и SHA — `docs/methodology/source-sets/2026-10-01/manifest.json`. Глоссарий WORKING 30.09.2026 — `reference/sources/GLOSSARY_WORKING_2026-09-30_extracted.txt`.
- Правило → сохранённые `m5_cycles.owner_user_id/organization_id` и C-67 → `Api/m8_results.py`, `Api/m8_report_access.py`, `Api/routes.py` → HTTP/PostgreSQL matrix. Не повышает статусы источников и не меняет M6.
- SHA256 выбранных входов: `P4K_REPORT_02_Access_Recipients.txt` — `9bda13d183749d681359773dfcb0871f66e7b2702978c11f38b6b8e180851087`; `P4K_REPORT_REFERENCE_2026-11-15.zip` — `887f7200a85bb4f97a52b2035efd72e234ca42919460fb8f0b5ea30c458a346a`; Change 01 README — `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`; source-set manifest — `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`; ADR-002 — `4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f`.

## План и проверки

1. Зафиксировать карту recipient-ссылок, разрешённую публичную проекцию и безопасный откат.
2. Исправить scope и списки/list/detail/PDF/comparison, добавить SQL/HTTP регрессию на смену членства и подмену ID.
3. Удалить действующий выбор и записи recipient, выполнить адресную миграцию с сохранением исторического аудита; проверить пустую и заполненную схемы.
4. Проверить действующие формы в браузере 1440/390, выполнить локальный минимум матрицы, собрать diff/отчёт и подготовить один PR.

Исходные адресные тесты: `tests/integration/test_m8_report_access_db.py`, `tests/e2e/test_m8_report_access_http.py`, `tests/e2e/test_m8_report_comparison_http.py`, frontend `rel01-report-access`/`f22-recipient-projection`. Полный backend, integration на собственной БД, lint/build, `git diff --check`; CI `frontend`/`pytest`/`full-verification` на точном head.

## Решения, риски, откат

Base `32a13d3da6c7c63f33f13b126773aeb8861099e6` (`origin/main` локально); ветка `codex/p4k-report-02`. У основного checkout есть чужой незавершённый diff; используется отдельный worktree. Актуальность remote требует повторной проверки при восстановлении сети. Стоп-условия EVC: изменения смысла оценки, PM/LU, прав сверх указанного решения, новый предметный артефакт — нет; схема меняется по явному заданию с планом совместимости и восстановления. Исторические immutable snapshots и audit не перезаписывать. Откат приложения — revert ветки; миграция должна содержать отдельный восстановительный путь без уничтожения сохранённых данных.

Флаги: `branch_push=false`, `pr=false` до проверенного кандидата; `merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`. Выпуск PATCH готовится `ready:prepare` перед Ready при доступной актуальной базе.
