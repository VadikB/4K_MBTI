# PATH-PILOT-01 — проект допуска ограниченного пилота

Дата: 05.11.2026. Статус: PREPARED_FOR_REVIEW / DESIGN_ONLY. Основание — последнее явное
поручение владельца: ограниченный пилот на существующих девяти Cases, полный M2
61 Indicator сохраняется; расширение каталога исключено из текущего задания.

## Результат и границы

Сохранить диагностику de3b831 и последующие локальные изменения; проверить прежние
решения и подготовить конкретный, но не утверждённый проект маршрута/допуска.
Передать законченный пакет диагностики и точные вопросы продуктологу/методологу.
Реализация стартового гейта/нового runtime, LLM, публикации, merge/deploy,
изменения постоянной БД и методологии запрещены. PREP-DIAG-01 отдельно UNKNOWN.

Ветка codex/path-plan-diagnostics. Base передачи de3b831a07a48cf20b304dd8debd506b1820a7c0;
проверенный collector implementation1bc9d36834262ee9ad4591227d5ec876fea8e648;
runtime/origin main2dc98c6b5b2637c6c505a90686e82f5e4274e763 / 2.0.64 (fresh fetch).
Исходные незакоммиченные изменения сохранены как resume-preexisting-vs-de3b831.patch.gz
и resume-catalog-draft.patch.gz в evidence/path-plan-diagnostics; это история, не допуск.
Gzip сохраняет исходные bytes/контекст diff; checksum распакованных patches проверяется.
Ничего не потеряно и не перенесено в main; root пользовательские файлы не меняются.

## Источники и разведка

Прочитаны README/CONTRIBUTING, EVC workflow/matrix/recipe и повторно использованы
неизменённые review/template/context/Registry/Change01/SourceSet/ADR002.
Выбранные разделы M7 v1.3 §§2.2/4/5.1, M6 v1.8 §7.3–7.4, M8 v1.2 §2/3;
M1 v1.4 FROZEN/CURRENT=NO; M2 K1/K3 v1.1 и K2/K4 v1.0.

Найдены ранее принятые решения ARCH-A05/PILOT-120 (PR110, main c9c7c5a),
ARCH30-ADD01 от30.10, exact published release receipt specialist_pilot@1.1.
Дополнительно прочитаны карточки02/07 из локального исходного пакета
P4K_Case_AS_Cycle_Plan_2026-10-23 rev2.0. Документы используются как доказательства
исторических решений, не как новые исполняемые инструкции/разрешение публикации.

Уточнение прежнего NOT_FOUND: основание ограниченного каталога и PILOT-120 найдено.
Но исходные документы оставляют продуктовую формулировку, содержательный oracle и
согласование конкретного плана отдельными решениями; catalog union39 не допуск
любого LIMITED. Нужны проверка применимости к текущим точным refs и конкретный проект.
В последнем фактическом Cycle3600/259200 method_default, не PILOT-120.

Трассировка: историческое решение → точные Case/M2 refs и условия источника →
проект планового состава/маршрута → PM-04/C-24/C-34/C-46 → будущий общий start
readiness server/UI/runner → негативные/позитивные contracts. Реализация здесь не заявлена.

## Стоп-условия и проверки

1/4: ДА для введения допуска/новых смысловых норм без продуктолога/методолога;
дизайн/проверка источников/упаковка независимы и разрешены. 2/5: будущий контракт
versioned pilot plan потребует согласования совместимости/формата до кода;
сейчас только non-runtime review proposal. 3/6/7/8: НЕТ в текущей области —
нет миграции/чувствительных данных/новых прав, откат docs-only и сохранение исходников.

План: source/provenance → конкретная матрица61×Cases и проект → согласованность
start контрактов → проверки/коммит/portable package. Новый paid PATH не запускается.
Переиспользуем backend773/HTTP108/SQL43/Python48/Node38 на unchanged1bc9d36;
дополнение проверяется offline (hash/path/source mapping/proposal assertions),
git diff --check, review. Новый CI NOT_RUN; все release flags false.

Откат: revert только документационных/evidence changes после de3b831; сохранённые
первичные receipts/patch history не переписываются. Нормы/публикованные версии
и БД не меняются. Следующий этап — человеческое согласование точного проекта.

## Выполненный результат

Статус: PREPARED_FOR_REVIEW / NOT_ADMITTED. Подробный проект —
[решения, маршрут и условия](../reports/path-pilot-admission-proposal.md).

| Пункт запроса | Выполнение | Evidence / ограничение |
| --- | --- | --- |
| 1. Сохранить диагностику и diff послеde3b831 | Сохранены первичные21 files, прежний MANIFEST и оба исходных uncommitted patches. Направление расширения помечено superseded; full M2 и pilot plan раздельны | preservation-since-de3b831.json; не ретроспективный допуск |
| 2. Основание и конкретный проект | Найдены ARCH-A05/PILOT-120 и ARCH30-ADD01; авторские Case/AS/target pairs совпадают0.3→0.5; current published checksums сверены | prior-basis-applicability.json; approval конкретного нового плана не установлен |
| 2. Матрица/маршрут/обоснование | Полный61-row M2 matrix;55 source opportunities; восьмипозиционный кандидат с39 целями,22 вне каталога, SPEC09 без автоматического включения; условия/риски/результаты/время | pilot-plan-draft-v0.1.json и pilot-opportunity-matrix.md; P/M PENDING |
| 3. Согласованность старта | Описаны отдельный authoritative admission, exact source scope, AS admission, lineage/time, совместимость и регрессии без READY-or-LIMITED fallback | §6 проекта; runtime/API/UI/runner не менялись |
| 4. Передача и решения | Точные P1–P3/M1–M4/T1/R1, переносимый индекс и пакет диагностики/проекта | Offline replay +10 отрицательных mutations PASS; не методологическая приёмка |

Проверки1bc9d36 backend773/HTTP108/SQL43/Python48/Node38 применимы к неизменённому
tool code; новых DB/LLM не было. Новая offline source/matrix/negative проверка
CHECK_PILOT_REVIEW.py PASS. Финальный manifest/verifier/diff/links и ZIP readback
фиксируются при упаковке exact handoff commit. CI/merge/deploy NOT_RUN и не разрешены.
Исторический PREP-DIAG-01 root_cause=UNKNOWN. Непроверенные вопросы — решения людей
о конкретном проекте и будущая реализация/разрешённый PATH, не недоделанная source audit.
