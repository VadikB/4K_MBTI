# P4K-POSTW02-QA-04 — ответ, ожидание и прокрутка

18.11.2026. Прямое поручение владельца: «запусти 4 задание». Приложенная
QA04 rev1.1 от17.11 описывает требования; полномочие на локальный этап следует
из сообщения владельца. Исполнитель — текущий Codex, один владелец функций.
branch_push/pr/merge/deploy/version_bump/artifact_publish=false.

Свежий origin/main997e4eb /2.1.30 проверен явным fetch18.11. QA03 PR247 открыт,
не слит; локальная ветка codex/p4k-postw02-qa-04 создана от main и fast-forward
интегрирует QA03 до8930e64. Это интегрированная локальная база, main не меняется.
После принятия QA03 нужна сверка с его фактическим squash/main перед PR QA04.

## Источники и область

Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/verification matrix,
artifact recipe, task template/review checklist; decision-register, QA01/03 и
POSTW02-05 STATE; context1.0, Registry, Change01 WORKING И-1/2/4/6/7,
SourceSet manifest01.10, M1v1.4 §6/9 (FROZEN/CURRENT=NO), M7v1.3 §5.3–5.6/6.1–6.4
и clarification/completion contracts. Глоссарий30.09, рабочая выдержка
POSTW02-04/evidence/glossary-sections.txt: Dialogue/Turn/LU; определения M1
приоритетны. PILOT-120/ARCH-A05 и первичная карточка прочитаны; числовые нормы,
snapshot/интервалы не меняются. Остальные решения реестра вне области.

QA04 и REFERENCE_V10.zip скопированы/хешированы в evidence/input.json.
Эталон v10/e44fa78: screen.mjs33–40, screen.css149–156/202–205/242–249;
порядок история → processing-notice → composer. Статусы и геометрия отдельно.
P4K.TASK.RULES v1.0 в Git не найден (также отмечено QA03); конкретные ограничения
карточки и EVC достаточны для технического fix. Новых предметных норм нет.

UI PM-04, представление server-owned AS/Dialogue и операции ответа. Backend/API,
схема/данные/Turns, методология, сценарий и завершение сохраняют контракт.
Текущие источники/тесты: interview.js, wiring.js, answer-drafts.js,
Api/m10_product_flow.py, p3-a/qa03 harness, postw02 browser fixtures.
Все8 стоп-условий EVC: нет. Новый формат/контур/права/данные не вводятся;
ограниченный UI diff обратим. Нового долга артефактов нет.

## План и проверки

- [x] Свежий main, последовательная база QA03, источники и причины.
- [x] Исправить собственную прокрутку, receipt/status/label и placeholder.
- [x] Controlled production behavior tests и HTTP существующего readmodel.
- [x] Chromium1440/390/320, фиксированные данные, снимки и v10 по зонам.
- [x] Затронутые frontend регрессии/полный frontend набор, lint/build/diff;
  отчёт AC→доказательство→PASS/FAIL/NOT_RUN, коммиты и STATE.

Профиль:1worker,0LLM,0mail,0автоповторов; browser≤300s, шаг≤20s,
длинные ожидания — управляемые часы. Локальные HTTP fixture servers закрыть.
БД не меняется; HTTP с controlled storage, рабочие БД/.env не используются.
Штатный CI обязателен перед merge; локальный этап его не подменяет.

Прослеживаемость: QA04C1/2→существующий scroll scheduler→production renderer и
browser; C3/4/6→точный receipt/актуальный runtime→renderer/wiring; C5→M1.6,
M7.6→server finish availability→placeholder; C7→draft revision guards/QA01;
C8→v10 zones→те же DOM/палитра. Новая сценарная последовательность, шапка,
индикатор, профилирование и QA05 вне области. Причина живой задержки не выводится
из controlled fixtures. Откат — revert собственного UI/tests/dist diff после
8930e64, без переписывания истории/интервалов/операций.

Результат: код/тесты/dist и финальный UI head a134d58; [отчёт](REPORT.md), [передача](STATE.md).
