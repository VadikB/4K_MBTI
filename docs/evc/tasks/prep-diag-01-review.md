# PREP-DIAG-01 — повторная адресная проверка сохранившегося evidence

Основание — продолжение списка владельца после выпуска2.0.68. Только сохранённые
материалы и код, без повторной генерации/БД/изменения admission или repair.

Исторический код4bab7230d8fa484fb8d922ee7d8b49b63674268d;
operation `c570a030-a47a-4eed-81f9-37c92e1441d8`, CASE.SPEC.02 v0.6,
candidate checksum5754161d86d31192ce1eca6c0f20d7fd3eb6b0884730379953675d4f370f1fad.
Первичные [карточка](../evidence/assessment-contour-2026-11-04/PREP-DIAG-01.json),
[terminal receipt](../evidence/assessment-contour-2026-11-04/final-failure-receipt.json),
[cleanup](../evidence/assessment-contour-2026-11-04/cleanup.json).

Подтверждено: агрегатINCOMPLETE, admitted=false, no AS/start,0 answers, repair=false;
tester5/challenger4 batch refs и required IDs известны. Individual check statuses,
reasons и конкретные incomplete IDs в историческом экспорте отсутствуют. Наличие
required ID не показывает, какой check не завершился; JSON retry не устанавливает
первопричину. Owned-БД удалена, восстановление утраченных checks не заявляется.

Текущий `tests/assessment_first_case_evidence.py::functional_receipt` сохраняет
incomplete_checks(check_id,status,reason,evidence_paths,aggregation_error), наличие
деталей и protocol errors. Unit-регрессия сохранности этих полей повторена в наборе
11 tests — PASS. Сохранённая [SQL export regression](../evidence/assessment-contour-2026-11-04/export-regression/regression-result.json)
явно synthetic: collector→fsync/readback→cleanup→same receipt, не реконструкция.
Новая SQL/LLM генерация для проверки экспортёра не требуется и не выполнялась.

Поздний actual PATH run2ff983f1… на e63/2.0.66 с published1.2 получил admissionPASS,
20 unique operations и start201; offline replay первичных34 файлов выполнен заново.
Это другой кандидат/операция/комплект, не установление причины старого INCOMPLETE.
Ошибки harness, catalog coverage, AUTH-DIAG-01 и пять прежних content FAIL не
объявляются его причиной. Нового подтверждённого продуктового дефекта PREP здесь нет.

Итог: **root_cause=UNKNOWN**, расследование конкретной исторической причины
**BLOCKED_BY_MISSING_PRIMARY_CHECK_DETAILS**. Проверка сохранившихся фактов завершена;
продуктовый остаток открыт, fix NOT_PERFORMED. Дальнейшее prospectively полное
наблюдение допускается только в отдельно разрешённом run; его причина будет новой,
не заменит старую без причинных доказательств. Восстановление БД не переоткрывалось.
