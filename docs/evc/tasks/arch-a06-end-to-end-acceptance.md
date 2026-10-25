# ARCH-A06 — сквозная приёмка функционального пути

## Основание и границы

- Пакет: `P4K_Case_AS_Cycle_Plan_2026-10-23`, редакция 2.0, карточка
  `08_A06_Acceptance.txt`.
- База работы: `main@c9c7c5a488c34003cb2fb8f55e54b630f25c0506`, приложение
  `2.0.23`, PR #110.
- Зависимости: FIX-B01/B02, ARCH-A01, FIX-B03/ARCH-A02, ARCH-A03,
  ARCH-A04, ARCH-A05 и ARCH-A07 уже находятся в `main`.
- Исторические FROZEN, AS, результаты и первичные трассы не изменяются.
  F05, 34 scenario runs и прежний CASE.SPEC.09 real-provider run остаются
  регрессионной базой только в доказанной области.

## Результат

Собрать воспроизводимый пакет A06, в котором отдельно показаны:

1. подготовка функциональной AS для `CASE.SPEC.01–09 × Sales/HR/IT`;
2. штатный путь `prepare → start → turn → close → M6 → M8` по каждому Case;
3. multi-case Cycle с `next`, `return`, `pause/resume` и итоговым M8;
4. адресные runtime-assertions для всех 34 строк scenario plan;
5. HTTP и browser-доказательства, включая разные UI-механики;
6. негативные исходы B01–B03 и A03/A04/A07;
7. PILOT-120: revision/snapshot/API/UI с `7200`, без ограничения генерации
   суммой planned duration;
8. раздельные статусы technical PASS, AI tester, human methodology,
   publication/pilot admission и Reliability.

## Матрица доказательств

Каждая строка фиксирует commit, application/source/package/catalog/profile/
configuration/timing revisions, provider mode, вход, ожидаемый oracle, первичные
API/UI/DB/provider-трассы, AS checksum и фактический результат. Непроверенная
глубина остаётся `NOT_RUN`, `BLOCKED` или `ERROR`; controlled adapter и synthetic
fixture всегда обозначаются явно.

Для 27 сочетаний Case/function обязательна реальная продуктовая подготовка и
tester/admission. Для каждого из девяти Case нужна минимум одна функциональная
HTTP-траектория до M8; в совокупности они покрывают три функции. Browser-часть —
минимум три полных пути по функциям и все отличающиеся механики, отдельно от HTTP.

## Адресная регрессия 34 сценариев

Общий факт одного Turn или успешного API-вызова недостаточен. Для каждой строки
проверяются применимые material IDs и sequence boundary, автор/полномочия и
аудитория персонажа, фактическая открытость ветви, semantic outcome с причиной,
различие `scenario_end` и закрытия AS, pause/resume/stop, отсутствие позднего
события после окончательного прекращения и идемпотентность повтора.

`R_ALL_TIME` проверяет фактическое бюджетное/временное состояние и завершение, а
не совпадение слова в идентификаторе. `mandatory_update` допустим только в
продолжающемся сценарии. `UNKNOWN` не считается эквивалентом явного `FALSE`.

## Стоп-условия

- Нет разрешённой изолированной test-БД или реквизитов тестовой организации:
  DB/HTTP/UI строки получают `BLOCKED`, работа над независимыми assertions и
  упаковкой продолжается.
- Нет утверждённого содержательного oracle: технический прогон разрешён, но
  human methodology остаётся `NOT_RUN`.
- Нет явного допуска real-provider: controlled прогоны не переименовываются в
  real-provider и не подтверждают Reliability.
- Draft lifecycle не поддерживает требуемый путь: не вставлять synthetic
  `human_review`/`FROZEN`; подготовить ограниченный вариант допуска владельцу.

## Проверки и передача

- Python/backend и unit tests для валидатора матрицы.
- Изолированные PostgreSQL integration/HTTP tests для критического пути.
- Frontend lint/build и browser tests для затронутых UI-механик.
- Real-provider запускается отдельным маркером и сохраняет все попытки, включая
  ошибки; случайный последующий успех не стирает предыдущие результаты.
- Полный CI и human review обязательны перед слиянием.
- Откат: revert единственного A06 commit/PR; опубликованные revisions и
  исторические evidence не удалять и не переписывать.

## Текущий результат

- `tests/integration/test_f05_runtime_matrix_db.py`: 34 controlled runtime
  сценария дополнены именованными assertions по sequence, idempotency, Turn,
  pause, stop, scenario end и закрытым ветвям; изолированный PostgreSQL-прогон —
  PASS (`1 passed`). Это техническая регрессия, не A06 methodology PASS.
- `tests/fixtures/arch_a06/acceptance-matrix-v1.json`: заведено точное декартово
  произведение девяти Case и трёх функций Sales/HR/IT. Все 27 строк начинают со
  статуса `NOT_RUN`; прежняя profile matrix не повышает их статус автоматически.
- Unit-проверка структуры новой матрицы и manifest — PASS (`5 passed`).
- Все 27 сочетаний synthetic function profile / авторский Case AS проходят
  детерминированную валидацию snapshot на входе преобразователя — PASS. Это
  подтверждает сохранность и валидность входа, но не заменяет provider generation,
  AI tester, admission или HTTP/DB runtime.
- Все 27 строк проходят controlled generation → tester → admission → compiler с
  уникальными input trace/checksum — PASS. Controlled gateway подтверждает общий
  программный контракт, но не повышает real-provider и AI tester evidence.
- Публичный HTTP-контракт `/users/assessment/cycles/prepare` проверен для всех
  27 operation/profile references, включая participant-safe projection — PASS.
  Проверка намеренно не повышает `http_runtime`, M6 или M8: queue/runtime в ней
  контролируемые, а полный продуктовый путь остаётся `NOT_RUN`.
- Существующий изолированный PostgreSQL product-path для functional catalog
  проходит при явном и неявном выборе профиля (`2 passed`): queue, accepted AS,
  frozen CASE.SPEC route, replay, WAITING_CURRENT_AS и следующая AS. Это опорный
  technical PASS одного synthetic профиля, а не 27 независимых runtime-прохождений.
- Три существующих browser regression path на одноразовых PostgreSQL БД — PASS
  (`3 passed`): полный результат/PDF, interruption/additional session и
  lost-response/retry/two-tabs/owner boundaries. Они используют controlled catalog
  и поэтому остаются браузерной базой, а не A06 browser PASS для CASE.SPEC.
