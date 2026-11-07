# PATH-AC02/05-R1 — кандидат2.0.68, PR/CI/review

## Основание и границы

06.11.2026 владелец ответил «да» на отдельный вопрос: «Подтверждаете2.0.68 PATCH
→ PR/CI/review, пока без merge/deploy, активации программы и платного LLM?».
Разрешены согласованный bump, branch push, Ready PR и обязательный CI. Это не
человеческое code review нового head и не автоматическая приёмка18 AC.

Ветка `codex/path-ac02-ac05-coverage`, реализация
`ffca29c22050c08c9673662ef7763d01a47cabdd`, base/main
`bb3b5cb34696af8a8a2bdaa1999dd8a795786085` /2.0.67.
Один результат — оставшаяся AC02/05 regression matrix и исправление ложного
«не подключена» при неизвестном readback, с сохранением exact refs/operation_id.
История/остатки: [рабочая карточка](path-ac02-ac05-coverage.md).

## Источники, план, стоп-условия

README/AGENTS/CONTRIBUTING, workflow/matrix/recipe/review checklist,
architecture context/Registry/M1v1.4 FROZEN/CURRENT=NO/Change01 и manifest из
предыдущего неизменённого scope переиспользованы. Заново прочитаны текущие
task/STATE, release-раздел CONTRIBUTING, package.json, prepare_ready_release.py,
prepare_release.py и матрица; release tests/CI contract используются из того же
неизменённого выпуска2.0.67. Управляющие документы не меняются.
Api/scripts/assessment_definitions/schema/prompts/admission/repair не меняются.
Все8 stop categories — нет в данном scope; источник/права/контур/потери/новая
норма не вводятся, откат — revert UI/version/build, не данные/программа.

1. Свежий main + штатный `npm run ready:prepare -- --candidate 2.0.68`, второй
   идемпотентный вызов; не выполнять иной повторный bump.
2. Локальный минимум на новых assets: lint/frontend140/release+CI22/full
   auth-admin browser115/build45/diff/ссылки. Sterile environment, без .env/БД/LLM.
   HTTP25/owned PG2 переиспользовать только для неизменённых backend/SQL тестов.
3. Commit/push точного candidate и Ready PR через существующий browser login;
   gh не авторизован, токены/пароли не читать и не запрашивать.
4. Дождаться `frontend`, `pytest`, `full-verification` актуального head/base и
   всех lanes; не объявлять skipped deploy тестом или deployment.
5. Передать код/self-review/evidence владельцу на человеческий review.
   После CI использовать PR comments для статуса, не новый commit ради WAITING.

## Проверки, применимость и открытый риск

На ffca29c: targeted17/browser control115/frontend140/HTTP25/real PG2 PASS,
lint/build-idempotency/diff/hash45+50 PASS; bundle восстановлен независимо.
Исторические `path-ac02-ac05/FILES.sha256` и `code-sha256.txt` относятся только
к immutable ffca29c/его пакету. Новый bump/dist и STATE намеренно не совпадут;
не ослаблять/не переписывать старые manifests ради нового номера.

Первый полный browser был114 PASS/1 auth FAIL, причина UNKNOWN; отдельно5 PASS
на baseline +5 на working UI, затем неизменённый контроль115 PASS. Это не
доказательство исправления auth-сбоя и не доказанный дефект AC05. Сохранить
этот риск в новом PR, новый failure сначала локализовать, не скрывать retries.
PREP-DIAG-01 отдельно UNKNOWN; прежний real-provider PASS только e63/2.0.66.
Новой генерации и нового full PATH для выпуска UI не требуется/не разрешено.

## Действия и передача

branch_push=true, pr=true, version_bump=true(2.0.68 PATCH), merge=false,
deploy=false, artifact_publish=false, program_activation=false,
paid_llm_run=false, working_database_access=false. Никакого DB/retirement/cleanup.
Main и последнее подтверждённое test пока bb3b5cb /2.0.67; новый live readback
не выполняется в этом PR scope. Baseline не присваивается.

## Локальная проверка кандидата

Штатный preflight против свежего main bb3b5cb и повтор с тем же номером — PASS;
четыре metadata-файла и 45 assets побайтово совпали до/после повтора. Lint PASS,
frontend **140 PASS**, release/CI **22 PASS**, полный auth/admin browser
**115 PASS**, 142.242 s, retries=0, skipped=0, flaky=0, exit=0. Это новая
бесплатная проверка 2.0.68, не новый real-provider PATH.

UI fix, browser/SQL tests и Api/scripts/assessment_definitions совпадают с ffca29c;
применимость прежних HTTP25/owned PostgreSQL2 ограничена неизменёнными файлами.
54 SHA256 фиксируют проверенные source/metadata/45 assets. Новые browser PNG и
JSON сохранены отдельно; два автоматически перезаписанных исторических PNG
восстановлены из ffca29c после сохранения текущих снимков. Сырые stdout сжаты
lossless gzip, без удаления whitespace или скрытия исторических FAIL.

Команды/первичные результаты: [evidence](../evidence/path-ac02-ac05-release-2068/README.md).
Self-review: scoped UNKNOWN не заменяет серверный readback, exact refs и прежний
operation_id сохранены; synthetic HTTP явно отделён от real PostgreSQL/LLM.
Новый обязательный CI и человеческое review на момент commit ещё NOT_RUN;
точный финальный head и результаты CI передаются в PR без status-only commit.
Следующий шаг — push/Ready PR/CI и человеческое review; merge/deploy отдельно.
