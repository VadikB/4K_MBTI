# AS-PRESENTATION-DIAG-01 — локальная правка представления AS

06.11.2026. Исправлена публичная проекция **новых функциональных AS**: участнику
передаются конкретные P00 и стартовые материалы AS, не авторский passport8–13 с
Python repr и инструкцией «определяются в AS». Существующие AS не переписаны.
Дополнительно устранён подтверждённый сброс прокрутки при polling того же снимка.
Это локальная техническая проверка, не итоговый AC18 и не допуск нового выпуска.

## Область, источники и решения

Прямой допуск владельца — «делаем» на узкую бесплатную правку представления с
регрессиями. [Карточка](../tasks/as-presentation-fix.md) содержит прочитанные нормы,
8 stop conditions и связь Change01 И-1/3/6/7 → M1v1.4 M1.5 → C-34 → PM03/PM04.
M1 FROZEN/CURRENT=NO; полный M2, методология, admission, prompts и repair прежние.

Functional-personalization/0.5, Generation_contract_v0.2 этапы3/4/7,
G06/G09/G11, Generator_instruction_v0.2 п.5 и Participant_SPEC_02_v0.2 определяют
P00 + явные стартовые материалы как публичный результат. Все9 author AS проверены.
Legacy Sales/SLS02 остаётся отдельной проекцией. [Source identity](../evidence/as-presentation-fix/source-identity.json)
содержит22 точных SHA256 и9 пар Case/author-AS refs, все unchanged от base.
Новый предметный текст/содержательный fallback не вводился.

## Ожидание → факт → причина → исправление → повтор

| Дефект | Факт и причина | Исправление и проверка |
| --- | --- | --- |
| Авторский паспорт в participant view | В AC18 визуально list/dict в «Участники»/«Условия». Compiler делал str(passport8–13); materializer отдавал эти общие инструкции рядом с конкретными P00/материалами.9 Case regression FAIL | Для frozen source_schema_profile functional-personalization-indicator-v1/v2 материализуются существующие публичные поля конкретной AS. Полные passport/accepted AS/Indicator layers/private facts остаются закрытыми.9 Cases + legacy/unknown profile/admission/substitution guards PASS |
| AS polling сбивает чтение/доступ к кнопкам | Новый browser probe показал stable visible_ratio=0 после trial. Ожидание smooth-scroll не помогло. renderProductRuntime каждые1200ms очищал тот же DOM и scheduleBottomAlignment двигал документ | Не пересоздавать неизменные AS/payload/trace/clarification при том же DOM node. Timer/status/actions продолжают обновляться; новый trace рендерится. Проверены живые polls, reload/0 writes,4 ширины и конец длинного материала. Геометрический collector и CSS unchanged |

Не требуется и не выполнено редактирование опубликованного пакета: materialization
создаёт новый snapshot и его обычные checksums. Сохранённый snapshot читается как
есть. Отсутствующий/неизвестный frozen functional profile не угадывается по роли
или latest config: legacy projection сохраняется, admission не меняется.

## SHA и состояния

- Base и повторно fetched origin/main: `e9639edef400e2c36425f0d1c3ca98b646fdb0c2`,2.0.70.
- Рабочая ветка: `codex/as-presentation-fix`, отдельный worktree. Точный финальный
  commit и byte hashes — в `code-identity.json` передаваемого пакета; только этот
  новый локальный commit содержит исправление, main автоматически его не получил.
- Сборка наследует номер2.0.70 исключительно для локальной проверки; это **не**
  новый выпущенный2.0.70. Bump/PR/push/merge/deploy/publication отсутствуют.
- CI нового кандидата **NOT_RUN**: не разрешены push/PR. Старый CI не зачтён новым.
- Test — последний подтверждённый deploy e9639ed/2.0.70; нового серверного readback
  здесь нет. Постоянная БД/.env/реальные письма/LLM не использовались.
- Корневой worktree чужой TG-задачи изменялся независимо; не переключался и не
  редактировался мной. Три чужих untracked документа и остальные worktrees сохранены.

## Проверки и первичные результаты

Команды выполнялись из отдельного worktree, в sterile env без dotenv и keys:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  PYTHON_DOTENV_DISABLED=1 PYTHONPATH=. DB_NAME=product4k_pytest_unused DB_PORT=1 \
  DB_POOL_MIN_SIZE=0 LOG_TO_FILE=false AUDIT_LOGS_TO_DB=false PYTHONDONTWRITEBYTECODE=1 \
  /Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -q \
  -m 'not integration and not e2e and not llm' --junitxml=/private/tmp/as-presentation-backend-final.xml
```

| Проверка | Фактический итог / scope |
| --- | --- |
| Исходная red regression |9 FAIL/2 PASS, exit1, сохранена до materialization fix |
| Адресные projection/Sales/functional/generation/snapshot |58 PASS, exit0; после расширения15 projection regressions входят в backend |
| Полный backend |937 PASS/354 deselected, exit0; по команде выше |
| HTTP `pytest -q -m e2e tests/e2e` |108 PASS/12 deselected, exit0; без LLM |
| PG `pytest -q --run-integration tests/integration/test_m10_product_path_db.py -k functional_catalog` |6 PASS/10 deselected, exit0; повтор с `--basetemp=/private/tmp/as-presentation-pg-primary` сохранил5 readback до fixture DROP SCHEMA. Оставшийся параметр — намеренное закрытие Cycle при provider call |
| `node --test tests/frontend/*.test.mjs` |145 PASS, exit0 |
| `npm run lint:js`; `npm run build:web` |PASS, exit0;45 generated assets. Чужих dist-файлов в этом worktree до clean не было |
| Browser AS/legacy/viewport subset |12 PASS, exit0,4 ширины1440/320/390/768; первый отрицательный итог2 FAIL/1 PASS сохранён |
| Расширенный auth/admin/interview + viewport |Финальный120 PASS, exit0, retry0/skip0. Первый119 PASS/1 FAIL, exit1: AC05 invalid-json GET after lost PUT; сохранён. Причина единичного сбоя UNKNOWN, в повторе не воспроизведён; не объявлен причиной AS bug или PREP |
| `git diff --check`, immutable sources |PASS; published artifacts/contract/compiler/admission/repair unchanged |

Новый browser full повтор выполняет тот же файл и неизменённый collector с
дополнительной проверкой доступности последнего материала через nested scroller.
Первый119/1 не удаляется и не обозначается успешным. Interim wait-only collector
эксперимент не устранил ошибку и не включён в финальный diff. Отдельные sandbox
EPERM/EADDRINUSE и прерванный PG probe сохранены как неуспешные попытки, не PASS.

PG proof использует настоящие psycopg/SQL/runtime/HTTP owner guard. **Provider,
Case QA и upstream start permission в старом компонентном fixture синтетические**:
это не real generation, human review, новая методологическая приёмка или полный
PATH. Authentication token lookup для runtime GET — controlled identity fixture,
не доказательство AC06. Нет fake Connection или injected successful runtime resolver.
До любых оценочных ответов сравниваются persisted public → runtime → HTTP public,
snapshot/execution checksums, candidate/accepted AS и refs. Разные объекты не
требуются равными по хешу. Затем старый тест продолжает свой controlled сценарий.

Browser использует materializer на точных author examples и synthetic HTTP,
реальный entry/dist и живой UI polling; это не SQL/browser end-to-end или real LLM.
Автоматические probes не отправляют ответы/команды, actual provider operations0.
Восемь кадров Case01/02 на4 ширинах просмотрены: конкретные вводная/материалы,
читаемые переносы, без repr и horizontal overflow. Длинная desktop AS штатно
имеет внутренний scroll; проверка последнего материала не заменена наличием в DOM.

## Очистка, риски и откат

[Cleanup](../evidence/as-presentation-fix/cleanup.json): exported5 primary readback,
0 remaining task schemas/0 other connections; exact owned container/labels/volume
сверены. Штатные stop + rm --volumes без FORCE удалили только этот временный PG.
Временные synthetic данные невосстановимы, evidence сохранено; рабочих данных нет.

Конфиг/схема/границы PM/права/чувствительные данные — без изменений. Изменённые
product files: Api/m5_case_runtime.py, web/js/screens/interview.js и generated dist.
Остальное — fixtures/regressions/task/report/evidence/STATE. Public routes/models
не менялись; participant_payload остаётся словарём, UI поддерживает отсутствие
legacy optional sections. Legacy compatibility и существующие consumers проверены.
Откат: revert рабочего task commit + штатная пересборка при разрешённом выпуске;
никакой миграции или восстановления постоянной БД не требуется. Старые AS не
переобрабатываются, rollback влияет на будущую materialization и UI.

## AC18 и следующий шаг

Исторический approved AC18 на e9639ed: runner/preparation/start/first-AS PASS,
10 unique provider operations/748766 tokens, admission PASS, repair=false,
start201/0 assessment answers. Его **финальная визуальная приёмка BLOCKED**;
эта локальная правка не превращает старый receipt в PASS на другом SHA.
Новый final-SHA/post-deploy AC18 **NOT_RUN**, real LLM здесь0.

Далее владелец отдельно разрешает выпуск: release preflight/новый номер → PR/CI →
человеческий review → отдельный merge/test deploy. Только после окончательного
выпущенного SHA и нового отдельного разрешения — итоговый real-provider PATH.
Публикация/активация программы не требуется для этой правки и не разрешена.
PREP-DIAG-01 остаётся отдельным историческим инцидентом, root cause UNKNOWN.
