# P4K-POSTW02-01 — результат и проверки

> **Текущий follow-up: шапка, имя и цвета доработаны по новому запросу владельца.**
> [Результат 1440/390 и fallback](HEADER_REVIEW.html), [сверка и проверки](POST_REVIEW.md).
> Предыдущие исправления A01–A18 сохранены; нижележащие записи — история этапа.
> Владелец разрешил один PR/merge и штатный TEST deploy после CI. Текущий выпуск —
> [RELEASE.md](RELEASE.md), кандидат2.1.13. Нижележащие статусы до выпуска исторические.

> **Текущий результат: локальные исправления A01–A18 выполнены и проверены.**
> [Исправленный вариант](FIXED_COMPARISON.html), [итоги и ограничения](REFERENCE_FIXES.md).
> Ниже сохранён прежний отчёт/план; исходный FAIL относится к e1b07b3.
> Новый source/dist snapshot — evidence/corrected/identity.json. Публикация запрещена.

Локальная реализация редакции **1.1 / v10** завершена. Владелец прямо выбрал новую
редакцию после обнаружения смены папки; REFERENCE_CURRENT.txt прочитан.
Состав product-инвариантов кабинета остался прежним, код повторно не менялся.
Sites API подтвердил version10/source e44fa78efb1ec8605b28cf9bc2c2272da2b9122a
и succeeded publication; metadata без токенов — evidence/reference-v10.json. Base `2afcc37912fb2219f0710a5836b7417ce01d8e8e`,
ветка `codex/p4k-postw02-01`. Версия 2.1.11 сохранена: это рабочий кандидат для
одного draft PR, не новый выпуск. Итоговый head/PR/CI фиксируются отдельным локальным
receipt после commit, без самоссылочного коммита с собственным SHA.

## Изменение и контракт POSTW02-02

`ParticipantAssessmentCard` в owner session-bootstrap/session-restore получил
аддитивные `planned_total: int|null`, `current_position_no: int|null`,
`last_completed_position_no: int|null`, `plan_revision_id: str|null`,
`between_situations: bool`, `journey_state: str|null`. `status` по-прежнему хранит
состояние Cycle, старые `total_cases`/`completed_cases` остаются совместимыми.
`total_cases` теперь равен известному полному плану. В legacy `active_assessment`
неизвестный total остаётся 0 по прежнему контракту; новый renderer его не читает.
Это типизированные поля карточки; старое boolean `planned_total` return-state API
не меняется и не должно передаваться в renderer карточки как число.

M — `m7_planning_repository.read_plan`: последняя сохранённая применимая revision
этого Cycle с проверкой checksum/profile/cycle. Это тот же источник сохранённого
route, который читает готовность через m7_cycle_planner. Каталог и AS count не
используются. N — связанная с этой revision `m7_route_positions.position_no` и
предъявленная current AS (`started_at`, состояние). Проверяются Case/version и
Cycle. Неизвестное не выводится из completed; ещё не предъявленная AS не даёт N+1.
При несовместимой provenance N/M остаются неизвестными. Между AS показывается
номер последней предъявленной закрытой AS; неизвестная current AS не объявляется
перерывом. Этот технический projection не меняет доменный completed count.

Подготовка/сведения/назначение используют существующий acquaintance/readiness/job.
`can_start=false` не превращается в общую блокировку; job failure, установленная
readiness error и runtime pipeline failure видны отдельно от ожидания. Закрытые
Cycle и готовые Report используют прежний M8 owner history. Когда активного
назначения нет, последняя завершённая оценка занимает основную карточку и исключается
из предыдущих строк; одно прохождение отображается один раз, не по Report revisions.
Разрешённый unmanaged M4 entry сохранён, managed W02 его не использует.

Основная карточка и две информационные карточки справа соответствуют предоставленной
композиции v9, сохранённой в v10; ниже прежняя история Cycle. Длинные названия переносятся.
Числа/организации/имена demo не перенесены. PDF/сравнение/генерация не добавлены.

## Прослеживаемость LU и переходов

| Область | Реализация | Доказательство |
| --- | --- | --- |
| PM-04 LU-04.2/04.3, сохранённый план/позиция | Api/participant_dashboard.py + routes.py | 15 HTTP tests, 4 provenance tests |
| PM-04 LU-04.5/04.6, read-only время/возврат | existing read_status/read_return_state; новых команд нет | SELECT-only fake storage; browser explicit-return barrier |
| UI, готовность и кабинет | dashboard renderer, onboarding passive entry + явная кнопка «Мои оценки» | browser requests-1440/390.json: только GET |
| PM-07 history consumer | existing list_owned_cycles/list_owned_reports | latest featured один раз, предыдущие записи отдельно |

Логотип `#onboarding-home` уже имел маршрут через journey/bootstrap в кабинет.
Его обработчик сохранён и разделён с явной кнопкой «Мои оценки» в подготовке/готовности.
Кнопка карточки готовности открывает read-only entry, проверяет expected Cycle;
при смене assignment/plan показывается conflict, чужая готовность не стартует.
Переход через историю и назад сохраняет passive entry и не создаёт missing operation.
Active card открывает выбранный Cycle напрямую в существующем return-flow;
признанное отсутствие всё ещё требует отдельного Continue, runtime/AS до него не читаются.
Подтверждение начала, retry, next AS и сам Continue этим изменением не выполняются.

## Токены и визуальная проверка

Контрольные значения уже приняты в W02 v5. Они вынесены в shared participant tokens,
а W02 получил aliases с теми же вычисленными значениями. Старые generic aliases
`--bg-soft=#F6F9F9`, `--text-muted=#68777C`, `--panel-border=#D6E2E5` отличаются от
явного задания/W02: `#F7F7F7`, `#464554`, `#CBD5E1`. Кабинет использует общие
participant aliases по заданию; остальные страницы не перекрашиваются.
Основной текст #222C30, кнопка #18B8C6, ссылка/фокус #007D89, Onest, белые карточки,
8px и отсутствие теней сохранены. Неподтверждённая вторая палитра не введена.
Palette regression по-прежнему отвергает произвольные local hex; проверяет точные aliases.

[Сравнение до/после](VISUAL_REVIEW.html) использует одинаковые viewport 1440×1000
и 390×844. Дополнительно 320×844 проверено только на overflow.
В браузере подтверждены `rgb(247,247,247)`, 8px, загруженный Onest и
scrollWidth=clientWidth на 1440/390/320. Кадры просмотрены исполнителем.
Это проверка локального продукта по предоставленной спецификации v10, **не**
авторизованного живого reference. Метаданные версии/SHA/publication подтверждены API.
Содержимое точного исходника v10 и его авторизованный live render NOT_RUN: инструменты
Sites не предоставляют чтение archive; local v10 checkout не найден. Вход Google не
повторялся, обход не использовался. Визуальная приёмка
владельцем после выпуска остаётся отдельной.

## Фактические проверки

| Проверка | Результат / evidence |
| --- | --- |
| Existing dashboard/journey/email-admission unit+HTTP, 15 | PASS, backend-existing.log |
| New real owner bootstrap HTTP + SELECT-only storage, 15 | PASS, backend-reviewed-final.log |
| Untrusted cycle/profile/route/checksum provenance, 4 | PASS, backend-provenance.log |
| Targeted frontend: dashboard, onboarding flow, W02, palette, error presentation, 40 | PASS, frontend-scoped.log |
| После защиты passive history: только затронутый W02/onboarding subset, 14 | PASS, frontend-readentry.log |
| eslint | PASS, lint-final.log |
| esbuild | PASS, build-final.log; source/dist hashes checked-content.json |
| Bounded browser before (1440/390 + overflow320) | PASS, before/result.json |
| Bounded browser after | PASS: verified 1440/390; after/geometry-320.json + after/browser.log для 320 |
| Дополнительный временный read 503, только desktop | PASS, refresh-verified/result.json; карточка не заменяется блокировкой |
| Domain entry mutations | PASS: все обращения browser GET; AS runtime не читается до явного Continue |
| Cleanup | PASS, cleanup-summary.json: server closed, ports closed, owner registries absent |
| Source identity Change01/M1/M7 | MATCH с manifest, source-identity.json; статусы не повышены |
| git diff --check | PASS |
| Полный локальный backend/integration/общий browser/PATH/real provider/письма/Prod | NOT_RUN по узкой области задания; обязательный CI не меняется |
| Site v10 version/SHA/publication metadata | PASS, reference-v10.json |
| Точный source/live render v10, ручная TEST/приёмка владельца | NOT_RUN, причина выше |

Начальные новые fixtures имели два неверных ожидаемых заголовка готовности и
неполный UserResponse. Эти FAIL сохранены в исходных логах; исправлены только
fixtures, production copy не подгонялась. Успешный overflow320 не повторялся.
После новых изменений повторялись только затронутые наборы; общий PATH не запускался.
Один browser runner: workers1/retries0, whole180s/test60s/idle60s, ephemeral localhost,
штатный owned-process teardown TERM/grace1s/KILL, DB/LLM/mail=0.

## Риски, откат и передача

Нет схемы/миграции/перезаписи снимков. Доступ, scheduler, W02 вопросы, profiling и
M6/M8 расчёты не изменены. Read model добавляет SELECT планов/позиций для карточек;
поведение подтверждено fake storage/HTTP, фактический PostgreSQL остаётся обязательным CI.
Код/JS/CSS и соответствующий dist откатываются одним revert собственного commit;
сохранённые оценки не затрагиваются. Ready release/version bump, merge и deploy
не разрешены этим этапом. Draft PR и CI не являются человеческим review или выпуском.
