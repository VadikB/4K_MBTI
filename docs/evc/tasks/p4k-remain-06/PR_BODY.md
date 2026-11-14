## Основание изменения

REMAIN_06 v1.6, PM-04 LU-04.2/3/5/6. Задача: `docs/evc/tasks/p4k-remain-06/TASK.md`; AC/primary evidence: `CHECKS.md`, состояние: `STATE.md` рядом. Base `07166475` (main/2.1.5, после REMAIN05 #219). Кандидат PATCH **2.1.6**, один независимо принимаемый результат.

## Результат

До получения runtime чат мог показывать неподтверждённое «1 из 5» и таймер00:00. Теперь вход показывает неизвестность, затем текущую позицию и завершённые позиции раздельно из frozen server progress. Например, plan8/catalog9/materialized1 даёт «Ситуация1из8» и «Завершено0из8»; fill использует completed/total.

Cycle с неизвестным remaining_seconds больше не использует legacy deadline. Ноль остаётся00:00; null/missing/invalid показываются неизвестностью. Current network failure снимает неподтверждённое время без ложной паузы; late foreign responses/failures отброшены существующими scope guards. Штатная browser-достижимость прежнего mixed legacy state не утверждается: beforeFAIL доказан synthetic renderer probe.

## Изменённые файлы

`web/js/screens/interview.js`, `web/index.html`, `web/styles/screens/interview.css`: UI-проекции прогресса/времени. Адресные frontend/browser/ownedPG tests и primary evidence. Release metadata и `web/dist` подготовлены штатно.

## Источники и решения

M1v1.4 AS/Dialogue/Cycle, M5v1.1 предъявленный материал, M7v1.3 время/возврат, Change01WORKING, C24/34/45/46 и frozen R1. Выбранные файлы/SHA256 и прочитанные разделы — TASK. Источник FROZEN/CURRENT=NO не выдаётся за runtime/методологический PASS. API/SQL/schema/time policy/R1 snapshots и product clipboard handlers сохранены. Прямой допуск владельца: PATCH2.1.6/push/PR; merge/deploy запрещены.

## Проверки (команда → результат)

- `npm run ready:prepare -- --candidate 2.1.6` — PASS на fresh main07166475; единственный bump и build/release gate.
- `node --test tests/frontend/*.test.mjs` — **324PASS** на release bytes.
- `npm run lint:js`, `git diff --check` — PASS.
- `playwright test tests/browser/remain06-chat.spec.mjs --workers=1 --retries=0 --timeout=90000` — **4PASS** на release bytes: pending/runtime/time/network, clipboard/IME, actual auth/admin/manual анкета scope.
- Owned PostgreSQL15 selected M7 progress/return/lease/snapshot — **10PASS**; HTTP/unit return/presence — **5PASS**.
- Real HTTP/ownedPG browser R1 — **2PASS**: один сохранённый Turn, same-AS Continue, lost-response/readback/replay/two tabs/foreign403. Short/long/mobile/draft/text200 — **3PASS**.

PG/HTTP/R1/layout проверены до version-only подготовки; `receipts/release216/source-binding.json` подтверждает неизменность Api/interview/wiring/CSS. Новые Run/Turn ради bump не запускались. Controlled provider/mail, real LLM/mail0, все owned ресурсы остановлены и БД удалены.

Ручная проверка: открыть разрешённую AS, до runtime увидеть неизвестность, после — server current/completed/time; сохранить draft, reload; явный Continue возвращает ту же AS. Не Finish→Report ради UI. CI exact head проверяется отдельно после создания PR.

## Непроверенное

Физические устройства/software keyboard, native textzoom и OS context paste — NOT_RUN. F17-AC02/F21-AC01/F21-AC03 остаются PARTIAL в физических границах; native Chromium typing/CDP IME и synthetic transfer-events описаны отдельно. OPS01/общийTEST/paid/Report/GC не запускались. Self-review агента не заменяет human review. Исторические before/fixtureFAIL сохранены в CHECKS.

## Риски: конфиг / схема / деплой / безопасность / откат

Новых config/schema/privacy изменений нет; только release metadata2.1.6 и штатные bundle chunks. API/история/published snapshots совместимы. Откат — revert собственного UI/release изменения со штатной сборкой, без переписывания данных. Merge и deploy в этой задаче не выполняются.

## Следующий минимальный шаг

CI актуального head, затем человеческое review и приёмка оговорённых native границ. Решение о merge/deploy отдельно у владельца. Открытых предметных решений для данного UI diff нет; ограничения проверки перечислены выше.

## Действия выпуска

- [x] `branch_push`
- [x] `pr`
- [x] `version_bump` — PATCH2.1.6
- [ ] `merge`
- [ ] `deploy`
- [ ] `artifact_publish`

## Готовность

- [x] Один результат, локальный минимум, регрессии и полный отчёт.
- [x] Секретов/PII нет, старые snapshots/API сохранены.
- [ ] CI exact PR head и человеческое review завершены — отдельные факты.
- [x] Baseline не присваивается.

## Browser consumer regression

После исходного head63557e7e адресно воспроизведены2FAIL stale E01/P3B exactbadge assertions; исправлены только tests/fixtures, добавлены3negative completedcount renderer variants. After2browser и324frontendPASS; Api/web/release bytes прежние63557e7e, same-versionpreflight2.1.6PASS. receipts/consumer-fix сохраняетbefore/after. НовыйCIheadобязателен, первоначальнаяCIсериянеобъявляетсяPASS.

## CI26ae357d: P03 scoped locator

Frontend/pytest/integration и4runtimebrowserlanesPASS; fast253PASS/1FAIL/1SKIP, parentfullFAIL. Причина — globalcompletedtextlocatorP03 теперь находитheader+returncard. Before1FAIL/after1PASS; locator разделён наcardиheader безослабленияreturnguards. Product/release2.1.6bytesunchanged. Primary receipts/p03-locator. НовыйheadпроверяетсяCI, прежнийFAILсохранён.
