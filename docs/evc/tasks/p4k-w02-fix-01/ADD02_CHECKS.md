# ADD02 — ready и два ожидания

Начальный/tested-before head `1ef5fcdf5d60e37c93edfcc83ed3c4c40afae233`;
base/main `f5053402ab4fe11ead3447642c960bca9dfa81f9`. Branch
`codex/p4k-w02-fix-01`, PR224 OPEN/not draft/not merged. Версия2.1.11 сохраняется.
Точные source/dist SHA256 — [checked-content.json](evidence/add02/checked-content.json).
Итоговый commit/CI receipt — локальный RELEASE_STATUS.json и первичные checks PR.
Это локальная controlled-проверка, не TEST и не доказательство развёртывания.

## Фаза второго снимка и серверный маршрут

Переданная владельцу галерея ADD01 показывала `early-waiting-390.png` и1440 из
`PARTICIPANT-LAYOUT-01` в auth-r03.spec.mjs. Его конкретный переход: personal
invitation → password creation/confirmation → journey `wait_for_acquaintance_data`.
Server fixture: readiness `waiting_for_organization`, reason `assignment_sources`,
onboarding `not_started`, profile `incomplete`, assessment `not_started`.
Поэтому этот воспроизводимый кадр — ранний вариант А; вид карточки не использован
как доказательство фазы. Самостоятельный файл второго внешнего скрина с hash в ADD02
не приложен: тождество любого иного изображения/состояния TEST не утверждается.

Проверен существующий server путь:

- `Api/acquaintance.py:read_state` получает early/late readiness, читает state только
  из текущего разрешённого scope через `acquaintance_state_store.read`, возвращает
  mandatory_complete, scoped answers/consent/confirmation и onboarding progress.
- `Api/acquaintance_state_store.py:read/same_scope` сверяет organization/assignment/
  questionnaire revision и пользователя; старый row другого scope не является текущим.
- `mandatory_complete` требует early ready, действующее consent, answers_confirmed_at
  и три непустых ответа текущего server state. Global onboarding completed или local
  answers этого разрешения не заменяют.
- `Api/routes.py:get_user_journey_state` возвращает полную acquaintance projection.
  При early ready, подтверждённых текущих ответах и late waiting выбирает
  `show_onboarding`; `main.js` → openOnboarding → авторизованный GET
  `/users/8/acquaintance` → текущая organization card.
- При early not-ready сервер не разрешает историю через этот контракт; frontend
  сохраняет раннее ожидание/состояние доступа. Старые локальные ответы не используются
  как обход. Backend/HTTP/БД контракт для существующего позднего маршрута не изменён.

Новый поздний fixture Б: пользователь8, organization10, assignment_ref=w02-assignment,
questionnaire_revision41; early ready; server mandatory_complete=true,
consent/answers_confirmed_at сохранены, answers A/B/C; onboarding completed/current8;
late waiting_for_assessment_data/W02_ANSWERS_NOT_BOUND, profile_id=null, нет плана.
Это доступная история текущего знакомства по существующему серверному контракту,
без объявления готовности подготовки. Причина реального waiting остаётся FIX02.

## Изменения

Из readinessStep удалена конкретная вставка paragraph(returnPolicyCopy(...)) и
неиспользуемый helper. CSS hide/фильтра по тексту нет. Process renderer и фактические
M7 snapshots не менялись. Participant_notice отображается прежним consumer без
фильтра/удаления. Числа5/75/48 в продуктовых кадрах — server fixture, не demo8/60/72.

Позднее organization уже имело требуемый состав и server маршрут. Найден и устранён
побочный command `/acquaintance/resolve-profile` при автоматическом open/history-return
на late waiting: beginPreparation вызывается на этих read-entry только при
server late_readiness=ready_to_prepare. Явное подтверждение и допустимый retry/prepare
сохранены, доступ/start/таймеры не менялись. На позднем waiting все проверенные запросы
теперь GET; нет ни prepare/start, ни записи ответов/progress, ни resolve-profile.

## Приёмка и команды

| AC | Проверка | Итог |
| --- | --- | --- |
| AC01 | Оба return_policy_snapshot: same/replace. Process показывает свой действующий текст; после завершения process ready и reload не содержат полный повтор. Параметры/краткая инструкция/time note/start/history сохранены. Отдельное participant_notice остаётся. | PASS TECH |
| AC02 | Позднее organization на1440/390: точные2абзаца+note, только secondary check в карточке, history в tail, без logout. История A/B/C read-only, возврат/reload/вход через URL аккаунта возвращают waiting. Все запросы GET, state byte-equivalent. | PASS TECH |
| AC03 | Ранний invitation/password existing test проходит. В позднем тесте после смены assignment/ref и server mandatory=false старый sessionStorage draft и global completed не включают историю/обещание ответов. Неуспешный GET показывает read error без ложного отсутствия данных/истории; retry читает saved state. | PASS TECH |
| AC04 | 4финальных PNG ready/organization ×1440/390; все просмотрены. Отдельно scrollIntoView кнопки, истории, footer и геометрия footer/main/card; horizontal overflow отсутствует. | PASS LOCAL VISUAL + TECH |

- `git diff --check`: PASS.
- `npm run lint:js`: PASS.
- `npm run build:web`: PASS, final build log; версия не повышалась повторно.
- `node --test tests/frontend/*.test.mjs`:334/334 PASS.
- Bounded browser01:32/32 PASS15.7s — existing W02 readiness/start/retry/history/footer,
  early invitation и5 ADD02 tests. Затем organization fixture уточнён до точной формы
  server late waiting (profile/assignment/name null), без изменения runtime поведения.
- Финальный bounded verified:6/6 PASS6.9s —5 ADD02 + existing early. Сняты4новых
  продуктовых кадра, ранние/остальные сцены и формы не переснимались в финальном наборе.
  Схема/backend/HTTP не менялись; полный локальный Cycle/ASK/Report/GC не запускался.
  Старые API/access/issue/consent/3question доказательства применимы к неизменённым paths.

Фактическая финальная команда из worktree:

```sh
python3 /private/tmp/p4k-w02-add02-browser.py add02-verified \
  w02-readiness.spec.mjs auth-r03.spec.mjs \
  --grep 'W02 ADD02|PARTICIPANT-LAYOUT-01'
```

Команда, лимиты и status/stop до запуска — [plan.json](evidence/add02-verified/plan.json).
[Runner](evidence/add02/runner-used.py), [логи](evidence/add02/),
[JSON product projections и геометрии](evidence/add02-verified/).
Runner использует штатный scripts.owned_process.run_bounded600s/no-progress90s,
Playwright1worker/retries0. Реальные LLM/письма/генерация0; рабочая БД не использовалась.
Mandatory frontend/pytest/full-verification точного нового head выполняется в CI,
не заменяется локальным успехом или прежним PASS1ef5fcd.

## Визуальная сверка

[Текущая галерея ADD02](VISUAL_REVIEW.html). [Галерея ADD01](VISUAL_REVIEW_ADD01.html)
сохранена как история; прежний ready с полным return policy не является текущим.
Новые reference не требовались: независимые ready/organization HTML renders с
проверенным SHA из ADD01/1ef5fcd переиспользованы. Исходный HTML не изменён,
SHA256 `2ae50fbe1ef73b4eb9fa6c808fec16d31475fb5cf79bb3d69ff275d41447170c`.

| Сцена | Product y/height | Reference y/height | Отличие |
| --- | --- | --- | --- |
| ready1440 |172.5/563|188.5/563|Состав/высота совпали после удаления повтора; y−16 из-за версии в footer+32. Product назначение5/75/48 вместо demo8/60/72. |
| ready390 |88/721|88/697|Название назначения занимает дополнительную строку24px. Карточка с естественной высотой, основная кнопка48px целиком видна; история/подвал доступны прокруткой. Нет полного повтора перерывов. |
| organization1440 |292.5/323|308.5/323|Высота/2абзаца/note/check/tail совпали; y−16 из-за версии. Нет раннего logout. |
| organization390 |160.5/371|176.5/371|Та же высота/состав, центр−16. История под карточкой слева, footer не перекрывает её. |

Header72/64, max760/card358 на mobile, padding32/24, typography/palette/scopedCSS
сохраняют ADD01. Новых CSS-правок, фиксированных высот или уменьшения шрифта нет.
[comparison.json](evidence/add02/comparison.json) содержит фактические rect/styles,
server projection и ссылки/hashes использованного evidence, без заявления pixel equality.

## Cleanup и передача

[resources-final.json](evidence/add02/resources-final.json): обе owned process groups
отсутствуют, owner registry отсутствуют;18764/18766 и ephemeral64672/64943 закрыты.
Собственные browsers/workers/server остановлены. DB/containers/LLM/mail0.
Чужие ресурсы сохранены. Риск — scoped UI/read-entry; откат revert своего PR без данных.
Human review/фактический TEST PENDING; merge/deploy/Prod/FIX02 не выполнялись.
