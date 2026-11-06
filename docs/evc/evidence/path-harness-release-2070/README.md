# Первичные доказательства кандидата 2.0.70

Отчёт: [PATH-HARNESS-R1](../../reports/path-harness-release-2070.md).
Новые результаты не переписывают [исходный proof](../path-ac06-ac10-proof/README.md).
Проверка без БД/сети/LLM: `python3.12 docs/evc/evidence/path-harness-release-2070/CHECK.py`
из полного checkout кандидата. Manifest — SHA-256 исходных bytes; source-identity
привязывает исполняемые файлы к source `4510aa4b7ac3db87f44cd422862a549d8c72c9a7`.
Финальный PR head добавляет только docs/evidence; CI проверяет именно его.

- backend.xml921/http.xml108/frontend.xml145/release-ci.xml22/http-pg.xml outer1:
  source `c972a88af085ea12520aae9380d2564984933054`. После него backend/API/версии/
  frontend/SQL источники неизменны. Child18 actual HTTP/PG — http-pg/checks.json,
  pytest.txt и cleanup.json;31 events,25 no-write, настоящее разрешение/транзакции.
- verified-targeted.xml34 (runner12+release/CI22), browser-results.json5 PASS:
  source4510aa4. Browser-admin — реальные routes/session/SQL/double-click/lost reply.
  Browser-component — **явная component-only upstream подстановка**, не full PATH,
  не human QA и не пилотный допуск. Пять фаз ×4 ширины, current geometry после
  trial scroll, clipping ancestors, overflow, PNG;0 действий/генераций collector.
  Основной component scenario далее проверяет синтетический ответ, не доказывает
  full PATH с0 answers. Будущий real/full PATH возвращается до этого ответа.
- Три новые DOM collector-регрессии — часть5 PASS: disabled остаётся disabled,
  clicks=0, offscreen/clipping/overflow отклоняются,12 DOM replacements допустимы.
  Они не заменяют actual PostgreSQL и не симулируют успешный product resolver.
- negative-io: первый browser run c972a88,1 PASS/1 FAIL; IO ratio0 при успешном
  trial/геометрии. Точный механизм callback UNKNOWN; не продуктовая причина AS.
- negative-rerender: ef0cc87,3 PASS/1 FAIL — предварительный scroll получил
  detached DOM при перерисовке admin card. Сохранены JSON, geometry/PNG и cleanup.
  Это промежуточный source, а не финальный результат. Обе отрицательные выгрузки
  остаются отрицательными; успешный result не получен удалением этих файлов.
- Каждый owned run экспортирован перед marker-guarded DROP без FORCE; контейнер
  с tmpfs удалён после readback0 owned DB/0 connections и проверки label/ID.
  Другие контейнеры и рабочая БД не использованы. State/cookies/auth traces/логи
  серверных query strings не включены; данные и адреса только синтетические.

240 integration исходного source2a868e5 переиспользованы по неизменным Python/Api
bytes; в новом release evidence не выданы за повтор на4510aa4. Новый mandatory
CI/full-verification нужен для точного head/base; его состояние — в PR.
AC18 NOT_RUN. PREP-DIAG-01 отдельно, историческая причина UNKNOWN.
