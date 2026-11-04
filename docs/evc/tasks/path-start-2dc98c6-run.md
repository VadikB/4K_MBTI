# PATH-START-2DC — один контролируемый real-provider прогон

## Результат и допуск

04.11.2026 владелец явно ответил «Да, один контролируемый прогон» на предложение
одного платного PATH на main `2dc98c6b5b2637c6c505a90686e82f5e4274e763` / 2.0.64:
новая owned-БД, exact published-pilot input, generation/tester/challenger и только
штатный repair; при admission — явный первый start/AS при 0 ответов, при отказе —
evidence и остановка без повторов. Предыдущие 20 operations / 1 505 441 tokens —
ориентир, не гарантированный потолок. Политики/промпты/методология не меняются.

Ожидаемый результат — достоверный PASS согласованного runner либо точный текущий
блокер на выпущенном коде после исправления frozen contract во входе repair.
Новый PASS сам по себе не доказывает причину прежних пяти FAIL. Исторический
PREP-DIAG-01 сохраняет root_cause=UNKNOWN.

## База, источники, проверенное основание

Исполняемый код — неизменённый clean detached checkout exact main 2dc98c6.
Локальная ветка `codex/path-start-2dc98c6-run` содержит только план/отчёт/evidence,
не меняет исполняемый код. Root имеет три пользовательских untracked документа;
они не переносятся и не изменяются. Main/test/CI выпуска уже подтверждены отдельно
в [итоге PR #169](https://github.com/VadikB/4K_MBTI/pull/169#issuecomment-6641283379).

Повторно использованы прочитанные неизменённые README/CONTRIBUTING/AGENTS,
EVC workflow/matrix/artifact recipe/review/context/Registry/Change01/manifest,
ADR-002 C-23/C-24/C-34, PM03 repair task, профиль assessment-first-case/1.1,
точный PATH blocker и первичные receipts. Дополнительно проверены runner,
test_stand ownership/environment/cleanup и browser terminal export/start.
M1 v1.4 FROZEN/CURRENT=NO, M5 v1.1, M7 v1.3 — применимость как в PATH-задаче;
нового нормативного допуска и реализации M6–M8 нет.

Связь: исходная specialist_pilot@1.1 / specialist-pilot@1.0 и оригинальные 27 QA
→ exact source fixture/seed → ProgramDefinition/config/catalog/CaseVersions
→ PM-02 frozen profile → PM-03 functional preparation/admission → PM-04 explicit
start/предъявление → strict receipt validator. Статические/synthetic QA inputs
диагностического однокейсового каталога не используются. Исходное human review
переиспользуется с его origin/checksum, не выдается за новое согласование.

Идентичности: fixture SHA-256
`a3175dda9675c476ae8636d26449e5ed17e0ef7940ea0412b7431882933ae1e6`;
repair service `14fdedf1f0e12eb1c5f0e740fece0a03b49a18070edb94ce59fcaae4193836f6`;
Generation_contract_v0.2
`4fc3cd1dd14e9f5a548266179e28706732cb9fd6034493b432fd67cad5718d2b`.
Техническое исправление PR #169 передаёт тот же frozen contract в repair;
новые prompts/admission/число repair отсутствуют.

Старые handoff/profile/blocker содержат исторические указания базы 7221671/
11b2a94 и pending release. Они не применяются как текущая база после состоявшихся
squash releases: актуальная база подтверждена Git и test readback как 2dc98c6.
Полной старой AS в переданном evidence нет; недоступные данные не реконструируются.

## План, безопасность, проверки

1. DONE: проверка main/test SHA и бесплатный machine preflight — 8/8 READY,
   включая Chromium, maintenance PostgreSQL connect/CREATEDB privilege и порт18861.
   Provider configuration проверена на наличие, не вызовом. LLM_CALLS=0 до запуска.
2. ACTIVE: чистый отдельный server checkout; существующий частный test venv и
   node dependencies того же lock; один существующий runner, новая evidence dir.
3. WAIT: первый результат → сохранить safe receipts/check IDs/статусы/причины/
   candidate links/unique operations/tokens; проверить terminal export до cleanup.
4. WAIT: независимо сверить lineage, допустимый admission, actual explicit start/
   presentation и 0 answers либо отрицательный шаг; безопасная передача evidence.

Команда из server worktree (не из checkout сервиса):

```sh
/home/vadim_bogachev/worktrees/path-start-01/.venv/bin/python \
  scripts/assessment_first_case.py --program-source published-pilot \
  --db-admin-port 55432 --port 18861 \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/worktrees/path-start-01/.venv/bin/python \
  --directory /home/vadim_bogachev/evidence/path-start-2dc98c6-controlled
```

Защищённый .env читает штатный runner только по allowlist; значения/state/password/
tokens/raw prompts не печатаются и не передаются. Контексты superadmin/admin/member
разделены; mail sink только example.test. Maintenance target только localhost
postgres:55432; тестовая БД `product4k_pytest_<run_id>` с exact owner marker,
AGENT4K_ISOLATED_STAND=1. Permanent agent4k_test не seed/test/cleanup target.
Нельзя исправлять продукт или подменять AS/admission по ходу эксперимента.

Cleanup — только существующий owned destroy после terminal receipt fsync/readback,
без FORCE. При неуспешном terminal export DB/state сохраняются, причина фиксируется;
не обходить guard. Откат эксперимента — остановка своего приложения и штатный owned
cleanup после evidence, без отката/удаления постоянных данных. Code rollback N/A.

Стоп-условия EVC 1–8: нет нового смысла; нет изменения контракта/схемы; нет
неразрешённой миграции/чужого удаления; источники точные, mismatch блокирует seed;
нового контура нет; права/PII/границы deployment не расширяются; откат определён;
один real run явно согласован. Нет открытого решения для запуска внутри границ.

Флаги `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. Запись плана/отчёта не новый выпуск.
Локальный минимум этого шага — docs diff/links и проверка evidence; код 2dc98c6
не меняется, его backend763/HTTP108/frontend139, обязательные full CI и deployed
readback переиспользуются в их области. Настоящий PATH — отдельная llm проверка,
не входит в стандартный CI и не подменяется прежними unit/gateway PASS.

## Итог

RUNNING/PENDING. Единственный реальный запуск ещё не завершён. Здесь будут
зафиксированы фактические run/operation/AS IDs, итог, tokens, cleanup, первичные
evidence и непроверенное. Любой второй платный запуск требует нового решения.
