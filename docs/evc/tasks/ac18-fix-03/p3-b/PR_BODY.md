# AC18 FIX-03 — совместный кандидат P3-A+P3-B

Решение владельца после совместного кандидата: человеческий review пройден,
PR #199 переведён в Ready на `261e3057`. Первоначальный допуск «Только Ready
и полный CI» позднее расширен прямым сообщением: merge в `main` и автоматический
deploy после успешного PR. Текущий `merge=true`, `deploy=true` условен: PASS
обязательных checks актуального head, свежая база/версия и штатный squash merge.
Pilot promotion не разрешён.
Физические устройства и whole AC10 не становятся PASS автоматически.

Существующие ветка `codex/ac18-p3-b-time-return` и PR #199.
База `origin/main=023bf85ec796d212d29b33218d906a1ed2023941` (2.0.86);
PATCH-кандидат `2.0.87` согласован ранее. Проверенный кодовый SHA:
`abce5f73cb452a6a71e9369e7a45d94533436a4e`.

Происхождение сохранено merge-коммитом `e343ecc3dc775319088a4f3ad46727494fcb684b`:
первый родитель — прежний P3-B `8be8e8e5db0ef9ad397d74a0753ea8d5ba26d23d`,
второй — переданный P3-A `5b502f13d72f63b3e75531e9ef8accd084f0913c`.
P3-A code SHA `7f0a77be8ba456a4e6bb52bb676d623672d8dcbc`; его последний
delivery-коммит менял только документы. Архив, checksum, bundle и перечень
файлов сверены; реализация 3А заново не выполнялась. После merge добавлена
только стабилизация тестового ожидания async logout (`abce5f73`).

P3-A предоставляет единый public chat, материалы/авторство, мобильный ввод,
сохранение позиции чтения и черновика в owner/Cycle/AS, идемпотентную отправку
с readback и защитой от запоздалой доставки. P3-B приводит прогресс к
замороженному плану, отличает неизвестное время от нуля, сохраняет R1 Continue
identity после lost response/reload и не открывает AS без серверного факта.
На стыке исправлен общий runtime/return-state loader: старый ответ другого
owner/Cycle/AS/экрана или generation больше не перерисовывает новый scope.
Слой 3А также устранил историческое переполнение 390 px/200%.

Связь с источниками: Change 01 и task manifest → ADR-002, M7 R1 v2
`sales-pilot-return-r1@2.0` (checksum
`1121db8c84b6997ee427264a589b5db088588e134734d8ae0dbc0d2220a36f14`)
→ `Api/m7_return_integration.py`, `Api/m10_product_flow.py`,
`web/js/screens/interview.js` и мобильный CSS → frontend, HTTP, owned PG,
browser и visual checks. Policy и публичные API/схема не менялись.

Проверки **именно сочетания** на кодовых байтах `abce5f73`:
Node frontend 192/192 PASS (включая 4 loader-scope); backend minimum 977 PASS;
M7 на изолированном PostgreSQL 31 PASS; HTTP P03 2 PASS; real HTTP/PG browser
P3-A 12 PASS; browser P03/P3-B 4 PASS; шесть визуальных состояний × четыре
ширины 24 PASS и отдельный 390 px/200% PASS (documentWidth=390,
offenders=[]); lint/build/diff PASS. Первый полный P3-A browser прогон —
11 PASS/1 FAIL из-за начала тестового входа до завершения async logout;
после синхронизации теста адресный 1 PASS и полный 12 PASS. Команды, SHA,
первичное evidence и ограничения — в `CHECKS.csv`, `STATE.md`, `VISUAL.md`.
Свежий `origin/main` не сдвинулся; `npm run ready:prepare -- --candidate
2.0.87` — PASS (release preflight/build), без перевода PR в Ready.

Исторические FAIL сохранены: P3-B `43c42c2f`/AC10 — 543 px при 390 px;
P3-A `5b502f13`/OPEN_SHARED_3B — stale unversioned loader. Более ранние
P3-A unknown/text200/initial-readiness также остаются в переданном
`CHECKS.csv`; их отдельный PASS не считался проверкой сочетания.

Первый полный CI Ready PR на `261e3057722d59cb1752264375befb080724bdd3`
— **FAIL** ([run 42634935985](https://github.com/VadikB/4K_MBTI/actions/runs/42634935985)):
integration и browser fast PASS, четыре runtime shard FAIL. Быстрый CI
([run 42634936107](https://github.com/VadikB/4K_MBTI/actions/runs/42634936107))
дал `frontend`/`pytest` PASS. В runtime-тестах сохранились старые ожидания:
повторное включение «Отправить» после сохранённого уточнения и retry через
общую кнопку при неизвестной доставке. Они противоречат новому фазовому
контракту, не показывают потерю Turn. На `c2ebf5bf1abe7d3a09b401990f5c1e6abadb1824`
G10.7 локально PASS 1/1 с HTTP-квитанцией и runtime readback; на
`cfeadc24de798c377b8e515995dda75942576f05` Recovery локально PASS 1/1
с retry конкретного сообщения, идентичными `request_id`/`turn_id` и серверным
readback. Production-файлы с `abce5f73` не менялись. Новый полный CI для
обновлённого head обязателен; локальные PASS не закрывают старый CI FAIL.
Дополнительно на `cfeadc24de798c377b8e515995dda75942576f05` четыре
затронутых runtime-сценария (S10-A/T11-10, S10-B, character, REV-02) локально
PASS 4/4 на изолированном real HTTP/PG стенде.

Физические iOS Safari/Android Chrome, native text zoom/software keyboard,
owner visual acceptance, исторический TEST Cycle/OPS01 и полный путь AC18 —
NOT_RUN. Поэтому whole AC10 и VISUAL_ACCEPTED не заявлены. Платный LLM и
рабочая БД не использовались. Откат: revert merge и fix/test-коммитов,
`npm run build:web`; миграции нет.
На screenshot 200% длинные подписи кнопок переносятся на несколько строк;
читаемость остаётся предметом человеческого визуального review.

PR остаётся Ready. `full-verification` нужен на актуальном опубликованном head.
После успешных обязательных gates владелец разрешил squash merge в `main` и
наблюдение автоматического `deploy-test` на test; не pilot.

## История P3-B до объединения

База `023bf85ec796d212d29b33218d906a1ed2023941`; основные коммиты
`ab03144cf465b5213a722a26f9cf6538af64235e` и
`c06f7a74822c338767eb6f3e81fa5fe15e654c69`; release commit
`43c42c2f4b0b825007af97f844f2d3946e055687` (плюс коммиты состояния).
Отдельная ветка `codex/ac18-p3-b-time-return`. PATCH-кандидат `2.0.87`
подготовлен командой `npm run ready:prepare -- --candidate 2.0.87` после
прямого ответа владельца «следующий patch». В `origin/main` остаётся `2.0.86`.

Сохранённый план, карточка возврата и верхний индикатор могли показывать разные
итоги; неизвестное время превращалось в `0`; потерянный ответ Continue допускал
независимый повтор. Теперь оба API-представления берут итог из замороженного
`plan.route`; UI отличает неизвестное время от нуля, использует серверные
паузы/прогресс, сохраняет idempotency key между перерисовкой и перезагрузкой,
выполняет readback и удаляет ключ только после подтверждения активного runtime.
Существующий FIX-RETURN-01 сохранён.

Связь: M7 R1 v2 `sales-pilot-return-r1@2.0`, checksum
`1121db8c84b6997ee427264a589b5db088588e134734d8ae0dbc0d2220a36f14`
→ `docs/architecture/m7-return-time-integration.md`, ADR-002/Change 01
→ `Api/m7_return_integration.py`, `Api/m10_product_flow.py`,
`web/js/screens/interview.js` → frontend, изолированный PG, HTTP и browser.
Хеши источников: policy JSON
`7ee12e5ebbd063ad27c24d415fbe388f9404ac33579621637cae1a94a9342e3a`;
M7 integration doc
`4f77683101688bbfe2f5a3cd9aa2f042e951a45ec448a10afa96c541875c15fd`;
пакет `TASK_3B_ARCHITECT.md`
`64ec2a5616a4be9ed397e638993c6c73771d80bffd8a2d37ac1c7ce212a58f94`.

Проверки: команды, SHA и доказательства по критериям — в `CHECKS.csv`.
На release commit `43c42c2f`: frontend 157 PASS, backend minimum 977 PASS,
HTTP P03 2 PASS, browser P03/P3-B 4 PASS, шесть визуальных состояний × четыре
ширины 24 PASS, ESLint/build/release gate/diff PASS. M7 owned integration на
изолированном PostgreSQL 31 PASS на предыдущем коммите с тем же backend;
после изменения только версии повтор не выполнялся. Отдельная эмуляция текста
200% обнаружила переполнение: 543 px при viewport 390 px — **FAIL** в общем
мобильном слое 3А (`topbar`/`textarea`). Физические iOS/Android, решение
владельца по визуальному AC10 и исторический TEST OPS01 — NOT_RUN. CI для
draft PR #199: `https://github.com/VadikB/4K_MBTI/pull/199/checks`;
обязательная полная проверка до merge не выполнена.

Публичные API/схема/методология/policy не менялись; production/test данные и
платные LLM не использовались. Откат: revert продуктовых и release commits,
затем пересборка `web/dist`; миграции данных нет. Общий мобильный chat/keyboard
слой принадлежит P3-A; P3-I проверяет объединённый deployed SHA.

Владелец прямо разрешил `branch_push` и создание этого **draft PR** с открытым
FAIL. Это не приёмка AC10 и не разрешение Ready, merge или deploy.
