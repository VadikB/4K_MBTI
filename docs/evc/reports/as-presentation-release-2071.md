# AS-PRESENTATION-R1 — передача кандидата2.0.71

## Результат и независимые статусы

Подготовлен согласованный PATCH2.0.71: новая functional AS materialization отдаёт
конкретные P00/start materials, не общий author passport; неизменный UI poll не
пересоздаёт тот же DOM и не сбивает чтение. [Source report](as-presentation-fix.md)
и [release task](../tasks/as-presentation-release-2071.md) сохраняют основания.
Новые prompts/admission/repair/методология/программа не вводились.

- Fresh base/origin-main: `e9639edef400e2c36425f0d1c3ca98b646fdb0c2` /2.0.70.
- Source handoff: `6f5681e1dda369a11892865b34cf3fe137f61585`, product36ef230a.
  Ветка `codex/as-presentation-fix` и ZIP SHA256
  `c50022dc7aaff950d752664af64a1e6970305a41b60cb453de6f3f1ade69ef78` сохранены.
- Release branch: `codex/as-presentation-2071`, отдельный worktree; exact final
  head/tree и CI выдаются в PR, без дополнительного status-only commit после CI.
- Version_bump/branch_push/pr=true по точному ответу владельца «да»; merge/deploy/
  artifact_publish/program_activation/paid_llm/working_database_access=false.
- CI нового head — ожидается после push/Ready PR. Human review **NOT_DONE**.
- Main и последний подтверждённый test остаются e9639ed/2.0.70. Нового deploy/
  live server readback нет. Historical AC18 runner PASS/visual BLOCKED; новый
  final-SHA/post-deploy AC18 **NOT_RUN**. PREP-DIAG-01 UNKNOWN отдельно.

## Источники, влияние и собственное review

Прочитаны release scripts/CONTRIBUTING/AGENTS/workflow/matrix/recipe/task-template/
review-checklist/исходная task, повторно использованы immutable architecture
context/Registry/Change01/manifest/M1v1.4(CURRENT=NO)/C-34/functional0.5 sources.
Все8 stop categories — нет для разрешённых bump/push/PR/CI. Зависимые merge/deploy
и новый paid PATH требуют отдельного владельческого решения. WEEEK не используется.

Цепочка source→C-34→PM03/PM04→runtime/UI→regressions описана в source report.
Release delta к6f5681e: только4 metadata, rebuilt45 assets и docs/evidence/STATE.
17 существенных runtime/test/profile paths byte-identical6f5681e;22 source/contract
hashes и9 Case refs unchanged. Ни compiler/package, ни saved AS не переписываются.
Raw source manifests не обновлялись ради ложного равенства после version bump.

Собственный checklist: результат один; постороннего refactoring/управляющих docs
нет; public routes/models/БД/права прежние; закрытые passport/private facts остаются
закрытыми; synthetic fixtures не названы runtime-настройкой или human admission;
старые отрицательные попытки сохранены. Это **не** человеческое code review.

## Проверки — новые результаты

Из release worktree, стерильное окружение `env -i`: PATH системный, dotenv disabled,
DB_NAME=product4k_pytest_unused/DB_PORT=1/DB_POOL_MIN_SIZE=0, логирование в БД=false,
нет provider/mail credentials. Python `/Users/vadim_bogachev/Developer/4K/.venv/bin/python`,
Node `/usr/local/bin/node`; CI использует установленные Python3.12/Node22.

| Команда/проверка | Факт |
| --- | --- |
| `npm run ready:prepare` без candidate до разрешения | ожидаемый exit2,2.0.70→2.0.71, файлы не менялись |
| `npm run ready:prepare -- --candidate 2.0.71` + повтор | PASS/exit0,4 metadata+45 assets точно идентичны между первым/повтором; второго bump нет |
| `python -m pytest -q -m 'not integration and not e2e and not llm'` |937 PASS/354 deselected, exit0 |
| `python -m pytest -q -m e2e tests/e2e` |108 PASS/12 deselected, exit0 |
| pytest test_assessment_first_case/test_release_version/test_ci_verification_workflows/test_m5_participant_projection |50 PASS, exit0 |
| `node --test --test-reporter=junit tests/frontend/*.test.mjs` |145 PASS, exit0 |
| `npm run lint:js` |PASS/exit0 |
| Playwright auth-r03 `--grep 'AS projection\|E01 renders accepted\|REL-VERSION-01' --workers=1` |4 PASS/exit0, retry0/skip0. Concrete AS Case01/02 ×4 widths, polling/scroll/last material/reload0 writes/0 assessment answers; legacy и release badge2.0.71 |
| `python docs/evc/evidence/as-presentation-release-2071/CHECK.py` |35 evidence files/39 source hashes/5 PostgreSQL readback links/8 viewports PASS; без Git refs/БД/LLM |
| `git diff --check`, release consistency, локальные Markdown links |PASS перед commit/push |

Primary results: [evidence](../evidence/as-presentation-release-2071/README.md),
[manifest](../evidence/as-presentation-release-2071/manifest.json),
[source continuity](../evidence/as-presentation-release-2071/source-continuity.json).
Browser использует source-backed materializer + synthetic HTTP, реальные entry/dist,
не full PATH/real provider/SQL browser. После capture actual viewport геометрия
проверяется ещё раз; fullPage side effect для inner scroll не замаскирован.

## Переиспользованное и непроверенное

Исходные actual PostgreSQL/HTTP component6 PASS/5 readback применимы: runtime/SQL/
tests byte-identical6f5681e. Provider, Case QA, upstream start permission и token
identity в том fixture синтетические — не human review, product pilot admission
или новое доказательство AC06. Connection/runtime resolver настоящие, не fake.
Нового local PG run нет: только версия/build delta, схема/поведение БД не менялись.
Эти5 readback экспортированы до source-owned cleanup, скопированы byte-for-byte.
Source expanded browser120 PASS применим по неизменным behavioral bytes; release
дополнительно проверяет rebuilt entry четырьмя новыми browser tests, не выдаёт120
за новый release run. Новый обязательный integration/browser CI всё равно нужен.

Сохраняются source9 red FAIL/2 PASS; исходный expanded119 PASS/1 FAIL AC05 UNKNOWN
и последующий120 PASS — раздельные XML. Единичный AC05 не воспроизведён, не назван
новым подтверждённым product defect или причиной PREP/AS. Полная история interim
fixture/procedure failures остаётся в immutable исходном ZIP. Release новых FAIL
до commit не дал. Оплаченных вызовов0; actual provider/admission финального PATH
на новом SHA пока не проверялись.

## Риски и откат

Конфиг: только номер2.0.71/build. API/схема/миграции/рабочие данные/секреты — нет.
Не читались .env/БД; real mail/LLM не запускались. Source owned PG уже удалена после
export, release не создавал контейнеры/БД. Изолированный worktree сохраняет чужую
TG-работу,3 untracked docs и остальные ветки. Published definitions не менялись.
Rollback до merge — revert только release commits; source6f/пакет остаются.
Будущий product rollback — отдельный штатный revert PR/build, без миграции и
пересборки старых snapshots. Сам этот PR не разрешает деплой. Baseline не назначен.

## Следующий gate

Агент: push/Ready PR и mandatory frontend/pytest/full-verification exact head/base.
Владелец: человеческое review указанного после CI release head. Затем только по
отдельному прямому допуску — squash merge/main/test, новый readback, и отдельно
один final-SHA AC18. Программа/её подключения/LLM автоматически не разрешаются.
