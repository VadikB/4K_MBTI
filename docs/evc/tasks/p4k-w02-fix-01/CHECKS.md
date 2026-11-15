# CHECKS — P4K-W02-FIX-01

**ADD01: прежний PASS LOCAL VISUAL и утверждение о происхождении reference
недостаточны и отозваны. Ниже сохранена история. Актуальная перепроверка —
[ADD01_CHECKS.md](ADD01_CHECKS.md), evidence/add01-verified и gallery.**

Base: `e8773ca80b9e3089a0faec16e9722680d126d8bb` / 2.1.9.
Candidate: 2.1.10, штатный `npm run ready:prepare -- --candidate 2.1.10` PASS.
Runtime проверен до commit; точные SHA256 всех затронутых sources/dist —
[evidence/checked-content.json](evidence/checked-content.json). Tested commit/PR head
после фиксации записываются в STATE. Human visual на фактическом TEST: **PENDING**.

| AC | Проверка и результат | Статус |
|---|---|---|
| AC01 | PARTICIPANT-LAYOUT-01: personal invitation → оба шага пароля → waiting; 1440/390, читаемая copy/text колонка 696/310px, карточка 760/358px, кнопки 48px; desktop ряд/mobile колонка, длинное слово не переполняет; фактический reason assignment_sources; нет истории/обещания saved answers; refresh читает journey | PASS TECH |
| AC02 | W02 path 1440/390/320: оба входа, 4 option, POST message `Поле: Роль\n…`; ошибка/повтор с одним префиксом, receipt только после ответа; отдельный W02 FIX test: 2001 блокируется без POST/обрезки, ровно 2000 отправляется; draft переживает reload, чужое назначение пусто; pending blocks double submit; Esc/return focus | PASS TECH |
| AC03 | competencies/process по одному action, 4 карточки, ol из 4 li/note; reload обоих шагов; динамические 48ч/replace policy из fixture assigned_timing; completed read-only history и возврат; unit регрессия prepared-plan reload сохраняет поясняющий шаг | PASS TECH |
| AC04 | ready/preparing/failed-locked и остальные существующие state/start/retry fixtures; secondary refresh, retry только при server retry_allowed; история в tail, logout только access внутри onboarding; no command refresh, same operation/readback/first AS, stale refusal не обходит admission | PASS TECH |
| AC05 | 6 desktop + 2 mobile, просмотр изображений и сравнение с HTML v5; ниже конкретная сверка вместо вывода только по overflow | PASS LOCAL VISUAL |

## Команды и доказательства

- `git diff --check`: PASS, exit0.
- `npm run lint:js`: PASS, exit0; evidence/lint-final.log.gz.
- `npm run build:web`: PASS, exit0; ready:prepare повторно собрал кандидат2.1.10.
- `node --test tests/frontend/*.test.mjs`: 333/333 PASS, exit0, evidence/frontend-final.log.gz.
- Controlled browser, Playwright 1worker/retries0/global-timeout600000,
  scripts.owned_process.run_bounded deadline600s/no-progress90s.
  browser06: 43 PASS/1 FAIL за28.8s; причина — race теста focus до RAF заголовка.
  Тест ждёт реальный focus; browser07 повторяет все3width W02 path: 3/3 PASS за7.9s.
  Итого все44 выбранных сценария имеют PASS на неизменённом runtime кандидата;
  broad run не выдан за единый44/44 PASS. Логи browser06.log.gz/browser07.log.gz сохранены.
  Браузерные response mocks проверяют потребитель прежнего API, это не локальный
  SQL/HTTP backend прогон. Backend/схема не изменены; существующий сохранённый message
  и права report_issue подтверждаются mandatory integration CI точного PR head.
- auth05 invitation/password/waiting PASS; browser03 41/41 PASS предыдущего визуального
  состава; browser04 ошибка вызова helper без email исправлена; исходный browser01
  не стартовал из sandbox (ps EPERM), owner cleanup сработал. Причины/итоги в run dirs.
- tests/browser/path29-participant.spec.mjs fixture обновлён: две явные кнопки вместо
  удалённого skip. Полный PATH локально не запускался по границе задания; CI штатный.
- Обязательные CI frontend/pytest/full-verification: RUNNING, [Ready PR #224](https://github.com/VadikB/4K_MBTI/pull/224).
  Итог точного head — локальный RELEASE_STATUS.json и первичные checks GitHub.
  Release gate, все integration/browser CI сохраняются без сокращения профиля.

## Визуальная сверка HTML v5

[Снимки](evidence/screenshots/) и `reference-*` получены локальным рендерингом
исходного HTML с hash из задания, clean mode. Встроенный шрифт не выводился.
Восемь продуктовых снимков открыты и просмотрены Codex. Полная матрица28 не снималась.

| Снимок | Проверенные различия с прежним main и сопоставление с HTML |
|---|---|
| early-waiting-1440 | Убрана узкая52px текстовая колонка. Белая760px карточка/32px padding/22-30 title/40px icon; обычные48px buttons в ряд. Общая шапка/подвал видны. Early тексты отличаются от post-answer organization в HTML намеренно: нет обещания saved answers/history, показан server reason, сохранён выход. |
| form-1440 | Восстановлены select4варианта, подписи/placeholder и мягкие поля; modal560px/padding28/radius8/title20-28. Кнопки/close/cancel и вертикальные отступы сопоставлены с HTML. На снимке заполненное поле/выбор Роль, в эталоне пустой draft/ФИО; состояние фокуса ожидаемо различается. |
| competencies-1440 | По HTML у каждой карточки3px #109EAB, grid margin20px сверху/снизу, label12-16, тексты прежние; одно действие. Исторические ответы синтетические, поэтому положение текущего сообщения в scroll отличается от demo. |
| process-1440 | Четыре пронумерованных li с12px промежутком, примечание14-21/#464554/line3px/#CBD5E1/padding-left14, одно действие. Дополнительные48ч/правило возврата берутся из server fixture, не из demo8/60/72. |
| preparing-1440 | Белая760px карточка32px/radius8, heading22-30/icon40, note времени с линией, secondary48px check, только текстовая history под карточкой. Лишняя warning рамка удалена; строка «Операция в очереди» отражает queued contract вместо demo running. |
| failed-locked-1440 | Иконка ошибки, white card/title как HTML; одна secondary check, без retry/logout. Diagnostics после действия, history в tail без рамки. Сохранён служебный footer версии продукта; по сравнению с demo без версии это меняет вертикальный центр блока. |
| early-waiting-390 | Card358px/padding24/title20-28/icon40; header64px, text310px, кнопки48px в колонку. Длинные слова переносятся без обрезки; адаптация по HTML, early-specific тексты/выход/reason сохранены. |
| form-390 | Modal358px/padding28, поля300px, textarea и обе кнопки в колонку; крупные промежутки кнопок по mobile HTML, всё окно в844px без обрезки. Видны select/text/focus; исходные данные и согласие не меняются. |

Намеренно сохраняются действующие footer версии, accepted copy и серверное время.
Пиксельная идентичность demo-данным не заявляется; проверены состав, компоновка,
геометрия и типографика затронутых элементов. Human visual TEST остаётся отдельной.

## Ресурсы и review

[evidence/resources-final.json](evidence/resources-final.json): шесть owned process
групп отсутствуют; registry отсутствует, все записанные localhost порты закрыты.
DB/контейнеры/LLM/письма=0. Временная IAB вкладка закрыта; preview не оставлен.
Чужие процессы/worktree не изменены. Повторяемые команды status/stop — plan.json.

Саморевью: API остаётся message-only; server permissions/retry/admission не ослаблены,
опубликованные definitions/snapshots не меняются; diff ограничен W02 UI/consumers/tests,
PATCH и evidence. Секреты не читались/не включены; fixtures синтетические.
Риски — UI/fixtures и ожидающее человеческое review; откат revert своего PR без данных.

CI уточнение: runtime2 на94dfaad выявил гонку helper после успешного server start201.
Диагностика: evidence/ci-runtime2-failure/diagnosis.json. Исправлен только DOM-consumer
runtime.spec.mjs, node --check PASS; реальная проверка interview сохранена.
Runtime SHA256 прежний, повтор полного CI относится к следующему head.

CI уточнение2: head6bb2924 — frontend/pytest/integration/все4runtime PASS;
fast281PASS/3FAIL. В новом CSS display:flex перебивал .hidden, что подтверждено
двумя auth regressions. Селектор ограничен :not(.hidden); третий FAIL — прежний
DOM selector diagnostics, обновлён на перенесённый diagnostics после actions.
Css08:11/11 PASS за7.4s (invitation/password waiting,6readiness failures,
AUTH-RESUME valid/relogin/late401, REMAIN04 waiting/logout). Build/diff-check PASS.
При сравнении runtime hashes изменилась только onboarding.css; JS/dist прежние,
геометрия видимой панели прежняя. Два early снимка обновлены из css08.
Логи: evidence/css08.log.gz и ci-fast-failure.log.gz. Семь owned групп absent,
все порты18764/18766/18784 закрыты, DB/LLM/mail0. Следующий полный CI проверяет
исправленный кандидат, версия2.1.10 остаётся прежней (до merge не выпущена).
