# UX-QA20-01 — повторная сквозная проверка после FIX20

## Результат и точная версия

- Поручение: `P4K_UX_Fixes_2026-10-20`, редакция 1.0, задача 06.
- Проверенный опубликованный `main`: `7be110e35b9667da36f734fbb60c2b12a84367cd`.
- Опубликованная на test версия до этого документального QA-релиза: `2.0.12`.
- Версия-кандидат итогового отчёта: `2.0.13`.
- Пакет исправлений: PR #86 `d17d1c4`, #87 `52f7ace`, #88 `0b4fd00`,
  #89 `95b2c45`, #90 `7be110e`.
- Новых продуктовых функций, API, схемы, методологии, прав и миграций в QA-задаче нет.

## Источники, границы и решения

Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
`docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
`docs/evc/artifact-recipe.md`, Change 01 и task manifest, а также `COMMON.txt`,
`ACCEPTANCE.txt`, evidence проверки 20.10, `P4K_Product_Development_Principles.txt`
и задача `06_UX-QA20-01_End_To_End_Verification.txt`.

Проверяется реализация принятого контракта: роль org-admin сохраняется при переходе
между «Управлением» и «Моей оценкой»; собственная оценка требует независимого
доверенного назначения; организация, preparation, revision, snapshot, Cycle и M8
остаются server-owned и tenant-scoped. M1 v1.4 использован как понятийный источник
`FROZEN / CURRENT=NO`; QA не присваивает M1–M8 новый статус и не меняет предметные
артефакты. Стоп-условий и новых решений владельца не обнаружено.

Synthetic browser stand 10.2/10.3 создаёт отдельные `product4k_pytest_*` БД,
обычного org-admin, участника и отрицательные tenant-сценарии; подменяется только
AI-граница техническим gateway. Эти результаты не являются оценкой реального человека
или методологической приёмкой. Реальные письма и LLM не вызывались; секреты,
cookies, пароли и auth trace в evidence не сохраняются.

## Матрица приёмки

| Критерий | Способ и среда | Доказательство | Статус |
| --- | --- | --- | --- |
| F01: self-invite не снимает ожидание | HTTP, integration, Chromium owned stand | `test_adm19_02_self_assignment_http.py`; tenant/admission runtime | PASS |
| F02: черновик A не виден B | frontend + Chromium | account switch, logout, late preview, session generation | PASS |
| F03: ввод между тремя разделами и «Моей оценкой» | Chromium | `UX-FIX20-02 preserves named drafts across all management views` | PASS |
| F04: новая revision сразу видна и invitation bound | frontend, HTTP, integration, Chromium | preview/confirm, questionnaire source, selected assessment | PASS |
| F05: содержательный preview и stale invalidation | Chromium | текст участнику, получатели, отличия, повтор preview | PASS |
| Readiness и primary setup | HTTP + Chromium | server readiness, missing roles, attached-card edit, no tenant-create | PASS |
| Три management-подраздела, keyboard, длинные строки | Chromium | ADM19-01/QA19-03; без horizontal overflow | PASS |
| Личный путь org-admin к своей оценке и M8 | Chromium + integration | server journey, preserved management capability, saved own M8 | PASS |
| Повторный вход, refresh/back/deep link, logout/account switch | Chromium + integration | R03, S10.4, REV-02, G10.7 | PASS |
| Прерывание, возврат, Additional Session, deadline | integration + Chromium | M7; S10-B: initial timeout, clean rerun PASS 38.4 s | PASS |
| API/tenant scope, revoke, ID boundaries, concurrency | HTTP + integration + Chromium | own/foreign tenant, report access, late 401, lost response, two tabs | PASS |
| Immutable revision/Cycle snapshots и история | integration + Chromium | questionnaire/review history, M7 snapshots, REV-02 rerun PASS 60.0 s | PASS |
| M8 0/3, gaps, comparison, long labels, 200% | Chromium 153, CSS widths 320–1440 | QA19-04; embedded screenshots 390/768/1024 in browser JSON/CI artifact | PASS |
| Карточки 8px и сохранённая палитра | Chromium computed styles + frontend | ADM19-01, QA19-02, UX-FIX20-05 assertions | PASS |
| Опубликованные HTML и bundles соответствуют main | test, побайтный `cmp` | HTML PASS; 41 JS bundles, mismatch 0 | PASS |
| Backend process hash независимо от frontend | отдельного runtime SHA endpoint нет | version/assets не выдаются за backend SHA; точный deploy задаёт CI commit | NOT_RUN |

## Проверки

На `7be110e35b9667da36f734fbb60c2b12a84367cd` выполнено:

- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — 66/66 PASS.
- `npm run build:web` — PASS.
- `python -m pytest -m "not integration and not e2e and not llm"` — 485/485 PASS.
- `python -m pytest -m e2e tests/e2e` — 66/66 PASS.
- `python -m pytest --run-integration -m integration` на отдельной
  `product4k_pytest_qa20_7be110e` — 144/144 PASS за 7:45.
- Полный `npx playwright test --workers=1` — 57 PASS, 2 FAIL за 11:24:
  S10-B не дождался report до 70 s; REV-02 не дождался ожидаемой clarification до
  30 s. Оба сценария повторены вместе на новых owned stand — 2/2 PASS; стабильная
  продуктовая регрессия не воспроизведена. Нагрузка/тайминги полного прогона остаются
  известным риском тестового стенда, скрытые retries не включались.
- Адресный evidence-run карточек и M8 — 3/3 PASS; JSON:
  `.test-stand/browser-results.json`, изображения встроены как Playwright attachments.
- `https://test.4k-assistant.ru/users/version` — `2.0.12`.
- `https://test.4k-assistant.ru/` побайтно совпал с `web/index.html`; все 41 файла
  `web/dist/*.js`, включая lazy bundles, побайтно совпали с опубликованными.

Первый integration-запуск из sandbox был инфраструктурным FAIL: локальный TCP к
`127.0.0.1:55433` запрещён (`Operation not permitted`). Повтор той же команды с
разрешённым локальным доступом дал 144/144 PASS; это не продуктовый дефект.

## Реальная браузерная матрица

| ОС | Браузер | Результат | Причина / шаг повторения |
| --- | --- | --- | --- |
| macOS | Chromium 153.0.8010.12 | PASS | Полный automated owned-stand; это не Google Chrome |
| macOS | Safari | NOT_RUN | Нет безопасной live-сессии обычного org-admin/участника; открыть test и пройти путь из задания 06 |
| macOS | Chrome | NOT_RUN | Google Chrome не установлен в доступной среде |
| macOS | Яндекс Браузер | NOT_RUN | Приложение установлено, но нет безопасной live-сессии обычного org-admin/участника |
| iOS | Safari / Chrome / Яндекс | NOT_RUN | Реальное устройство недоступно; повторить M8, management и re-entry на опубликованном SHA |
| Android | Chrome / Яндекс | NOT_RUN | Реальное устройство недоступно; повторить тот же сценарий |
| Windows | Chrome / Яндекс | NOT_RUN | Реальная Windows-среда недоступна; повторить тот же сценарий |

Эмуляция CSS-ширины и Chromium не считается приёмкой Safari/iOS/Яндекс. Эти пропуски
не блокируют репозиторные gate и публикацию отчёта, но полная кроссбраузерная
визуальная приёмка остаётся за владельцем и маркетологом.

## Воспроизведение, риски и откат

1. Использовать локальный PostgreSQL 16, доступный только для synthetic QA.
2. Выполнить `npm run build:web`.
3. Выполнить `STAND_ADMIN_URL=<local-postgres-admin-url> npm run test:browser`.
4. Открыть `.test-stand/browser-results.json`; screenshots и Report/PDF находятся
   в Playwright attachments/CI artifact `browser-acceptance`. Не публиковать
   `state.json`, `prepare.log`, cookies или auth-данные.

Подтверждённых остаточных продуктовых дефектов области FIX20 нет. Остаток — реальная
кроссбраузерная приёмка и наблюдаемая чувствительность двух длинных browser-тестов к
нагрузке полного последовательного запуска. Откат документального PR — обычный revert;
данные, API и схема не меняются. После merge требуется точный CI, deploy-test,
проверка версии `2.0.13` и повторная побайтная сверка опубликованных bundles.
