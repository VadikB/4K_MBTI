# Первый эшелон: Cycle/Session и граница сбора

## Результат

Новая M5 Assessment Situation создаётся только внутри заранее сохранённых Cycle и
Session. Cycle фиксирует PersonalizedProfile, выбранную роль, исходные пары
IndicatorID/M2Version, бюджет времени и календарное окно. Закрытая граница сбора
запрещает новые Turns.

## Область

- Включено: модель Cycle/Session, принадлежность AS, состояния Session/Cycle,
  параметры 60 минут/72 часа с источниками, проверка границы перед Turn.
- Не входит: Evidence/EB/IA, C-46/C-56, Results/C-67, полный планировщик M7,
  генератор уточнений и UI времени.

## Источники и решения

- Прочитаны `README.md`, `CONTRIBUTING.md`, Change 01, task manifest,
  ADR-002, `change01-traceability.md`, workflow, verification matrix и artifact recipe.
- Требования: M1 v1.4 FROZEN, Change 01 И-2/3/5/6, ADR-002 C-24/C-34/C-45,
  T01/T05/T06/T10 и этап 1 единой задачи первого эшелона.
- M6 v1.8, M7 v1.3 и M8 v1.2 перечислены, но оригиналы и checksum отсутствуют.
  Техническая модель времени реализуется по явному контракту задачи; предметные
  алгоритмы этих этапов не заявляются.
- Решение владельца 02.10.2026: обратная совместимость и сохранение данных текущей
  версии не требуются; все существующие данные могут быть удалены без повторного
  согласования. При первом появлении обязательных Cycle/Session refs старые M5 AS
  удаляются, потому что их принадлежность нельзя достоверно восстановить.

## Прослеживаемость

| Правило | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| Один Cycle фиксирует профиль/роль/цели | C-24, `m5_cycles` | `m5_cycle_runtime.create_cycle` | integration: snapshot и цели неизменны |
| Session принадлежит Cycle | C-24, `m5_cycle_sessions` | `create_session`, FK/unique ordinal | integration: чужая Session отклонена |
| AS принадлежит Cycle/Session | C-34 refs и FK | `prepare_assessment_situation`, `_as_row` | integration: ownership mismatch |
| Закрытие сбора запрещает Turn | M1.6, T05/T10 | `assert_collecting`, `submit_turn` | integration: complete → rejection |
| Бюджет и окно фиксируются до старта | M1.9, T10 | поля Cycle и parameter sources | integration с управляемым временем БД |

## Данные и откат

Изменение несовместимое. Старые автономные M5 AS и дочерняя runtime-трасса
удаляются однократно при добавлении обязательных refs. Case packages и M4 profiles
не удаляются. Откат — возврат кода и повторное создание чистой БД; восстановление
удалённых данных не требуется по решению владельца.

## Проверки

Требуются backend unit, HTTP, PostgreSQL integration, `git diff --check`, CI
`frontend`/`pytest`.

Фактически выполнено локально:

- `npm run test:backend` — PASS, 234 passed;
- `npm run test:backend:http` — PASS, 22 passed;
- `TEST_DATABASE_URL=… npm run test:backend:integration` — PASS, 34 passed;
- `git diff --check` — PASS.

CI, frontend lint/tests/build и test deploy выполняются после фиксации PR. QA helper
Prompt Lab создаёт Cycle из целей выбранного Case, поскольку это лабораторный вход.
Основной продуктовый планировщик обязан создать общий Cycle и исходный состав до
первого выбора Case; его подключение относится к следующему PR основного пути.
