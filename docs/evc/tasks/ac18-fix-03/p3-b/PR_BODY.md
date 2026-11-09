# AC18 FIX-03 / P3-B — прогресс, время и возврат

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
владельца по визуальному AC10, исторический TEST OPS01 и CI — NOT_RUN.

Публичные API/схема/методология/policy не менялись; production/test данные и
платные LLM не использовались. Откат: revert продуктовых и release commits,
затем пересборка `web/dist`; миграции данных нет. Общий мобильный chat/keyboard
слой принадлежит P3-A; P3-I проверяет объединённый deployed SHA.

Владелец прямо разрешил `branch_push` и создание этого **draft PR** с открытым
FAIL. Это не приёмка AC10 и не разрешение Ready, merge или deploy.
