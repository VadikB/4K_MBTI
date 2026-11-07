# PATH-AC05-R1 — кандидат приложения2.0.67, PR/CI/review

## Основание и результат

Владелец ответил «да» на конкретный вопрос: «Разрешаете2.0.67 PATCH → PR/CI/review,
пока без merge/deploy, активации и новых LLM-прогонов?». Это разрешение подготовить
кандидат, push и PR/обязательный CI; не человеческое review кода и не приёмка18 AC.

База: `e63eba67d77fb73f7fb9bb219bc3fe5d3807a909` /2.0.66.
Локальная реализация: `2509aa2b5ef713c64c21c80499a1f82fbdb64142`,
ветка `codex/pilot-1.2-path`. Предыдущие публикация1.2/bootstrap/один paid PATH и
их разрешения сохранены как история; этот PR не повторяет их в рабочей БД.
Один результат передачи — PATH до первой AS с evidence и узким AC05 guard.

## Применимость и прочитанные источники

README/AGENTS/CONTRIBUTING, workflow/matrix/recipe/review checklist, архитектурные
context/Registry/M1v1.4(FROZEN/CURRENT=NO)/Change01 из неизменённой подготовки
переиспользованы; заново прочитаны release-раздел CONTRIBUTING, prepare_ready_release,
prepare_release/check_release_version, PR template, текущие task/STATE и тесты release.
Источники предметной логики, prompts, M0–M8, admission/repair и pilot plan не меняются.
Новый UI guard только отвергает foreign organization readback с тем же program ID.

Все8 stop categories — нет в разрешённом PR scope: нет нового смысла/PM/API/схемы,
миграции/удаления/источника/контура/чувствительных данных; откат определён. Никаких
изменений управляющих документов. Неизменённые источники и проверки не переиздаются.

## План и проверки

1. Сверить свежий origin/main и выполнить единственный штатный
   `npm run ready:prepare -- --candidate 2.0.67`; сохранить вывод/состав bump.
2. Локальный минимум: lint, frontend140, release/CI Python22, build/diff/ссылки;
   browser auth/admin100 на версии2.0.67; без `.env`, рабочей БД и provider.
3. Commit/push точного кандидата; создать Ready PR в существующем браузерном сеансе.
   `gh` не авторизован, токены не запрашивать/не читать; git использует штатный credential helper.
4. Дождаться актуальных `frontend`, `pytest`, `full-verification`, включая все lanes.
   Не объявлять skip/старый CI новым PASS; ошибки локализовать по фактам.
5. Передать head/base/CI и self-review владельцу. Human review ожидается; auto-merge
   не включать. После CI не создавать новый head только ради отчёта — комментарий PR.

## Что уже проверено и ограничения

На2509aa2:100 browser/140 frontend/25 HTTP+M3 PASS; foreign readback2 FAIL before →
2 PASS after;6 BaseRoles и4 widths проверены. Подробно:
[карточка](path-final-acceptance.md), [raw evidence](../evidence/path-final-acceptance/README.md).
Bundle2509aa2 восстановлен в новой Git-БД на shallow immutable e63; оба offline CHECK
PASS. Сохранились original operator failures/fixtures, не объявленные дефектом продукта.

Исторический `path-final-acceptance/CHECK.py` привязан к **точному2509aa2** и dist2.0.66;
последующий согласованный bump/assets2.0.67 закономерно не совпадут с его FILES.
Для replay использовать immutable2509aa2/переданный пакет, не ослаблять старый checker.
Real-provider PASS относится только к e63/2.0.66; новый paid повтор не выполняется.
AC02 повтор создания организации/полная AC05 slow-error browser matrix остаются
явным ограничением доказательств, не автоматически новым дефектом и не закрыты CI.
PREP-DIAG-01 отдельно: root_cause UNKNOWN.

## Действия выпуска и откат

branch_push=true, pr=true, version_bump=true(2.0.67 PATCH), merge=false, deploy=false,
artifact_publish=false, program_activation=false, paid_llm_run=false,
working_database_writes=false. Никакого runtime publication/retirement/DB cleanup.

Совместимость/API/схема/источники и старые snapshots сохраняются; секреты/PII не входят.
Откат при необходимости — отдельный revert UI/version/build, не данные/опубликованная
программа. Ручная загрузка product code на сервер не используется. Baseline не присваивается.

## Передача состояния

Preflight2.0.67 PASS против свежего e63, второй запуск идемпотентен без bump.
Локальные проверки: lint PASS, frontend140 PASS, release/CI unit22 PASS,
полный auth/admin browser100 PASS(79.311s), build45 assets PASS, diff/ссылки PASS.
Guard source/test байты неизменны относительно2509aa2, добавлен только согласованный
release metadata/build и эта передача. Api/scripts/assessment_definitions/governing
docs относительно e63 не менялись. Новых зависимостей/миграций нет.
Первичные команды/stdout/JSON/PNG — [evidence](../evidence/path-ac05-release-2067/README.md).
Визуальный review320/1440 прежнего шага применим к тому же UI/guard; новые PNG
проверяют2.0.67 на тех же4 widths. Нет утверждения о качестве полного оценивания.

Self-review: исправление соответствует AC05, проверяет оба refs в3 ветвях;
2 before FAIL сохранены, positive/null/lost/reopen/logout/roles/retry проходят;
никакие AS/assignment/profile/time/admission gates не менялись. Это проверка агента,
не человеческое review нового head. Baseline не присваивается.

Активно: commit/push/PR и обязательный CI. Новый head/PR/CI ещё не получены на момент
этой tracked записи; после CI актуальная передача фиксируется комментарием PR без
нового head только ради отчёта. Main и последний подтверждённый test — e63/2.0.66,
новый live readback/deploy не выполнялся. Следующий человеческий gate — review
конкретного нового head после CI, затем отдельное решение о merge/test.
