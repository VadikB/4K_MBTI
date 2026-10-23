# F05 remediation: первичные доказательства

Контур: ветка `codex/pers-audit-remediation`, исходный checkpoint
`7ac6eea95b948c8cef09029b3bd3d8947ab58041`, изолированная PostgreSQL с
`pytest` в имени. Пакеты F04 и исходные F05 evidence не изменялись.

## Real-provider прогоны

| Файл | SHA-256 | Фактический результат |
|---|---|---|
| `m6-original-error.json` | `355be34d4d946b872d3ec712ecd559a60d2366ef12320247ba65bcdd22f1fb35` | Сохранённый точный код исходного M6 `ValueError`, классификация и отсутствие assessment-request; provider payload и секреты не сохранялись |
| `real-provider-controlled-as-to-m8.json` | `1aa08f30e0aed63fb4cb8603a67d5df0b72d96fc6070a4b59902e5bb24685163` | Принятая controlled AS, реальный M6 и M8 `report_ready` |
| `real-provider-generation-rejected-before-repair.json` | `e647dce218373276b02d487e2b709f34e69c3feae42f1040508e39f7c26b0f5f` | Содержательный blocking FAIL tester до repair; это не техническая ошибка |
| `real-provider-generation-repair-to-m8.json` | `eb5992ebc89d599712888d176ad425d2f05211e4e3fb07ddd7616bb483aaf242` | Исторический успешный прогон после repair до M8; ранний формат файла хранит downstream evidence без полной functional trace |
| `real-provider-generation-to-m8-final.json` | `0e000054a034eafc2f1670d802c1b10eef5a225ce632360831b03723378f3995` | Повторный полный прогон на текущем head: generation/tester/admission → runtime → M6 → M8; содержит accepted AS, checksums, tester trace, runtime readback, provider attempts и непустой C67 |

Последний прогон был допущен первым tester без repair. Поэтому он доказывает
полный функциональный путь, но не выдаётся за самостоятельное доказательство
ветки repair. Ветка repair отдельно покрыта сохранённым исходным blocking FAIL,
историческим successful run и детерминированной unit-регрессией повторного полного
tester/challenger.

## Классификация ошибок

- `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED` — исходная техническая ошибка M6:
  frozen operation расходилась с опубликованным provider contract. Не является
  недостаточностью данных или содержательным дефектом AS.
- `M6_FRAGMENT_SPAN` и `M6_ATTRIBUTION_MISMATCH` — строгие технические отказы
  конкретных ответов provider. Кандидаты не принимались и не исправлялись
  сервером; provider вернул новые полные JSON после точной обратной связи.
- Blocking findings tester в rejected AS — содержательный дефект AS. Он не
  понижается до warning и запрещает допуск.
- Недостаточность данных остаётся отдельным контролируемым исходом F05/M8 и не
  смешивается с перечисленными техническими ошибками.

## Границы

Это техническое evidence. Оно не означает полную методологическую приёмку
`CASE.SPEC.01–09`, не присваивает `CURRENT`/`FROZEN` и не закрывает A03/A04/A07.
