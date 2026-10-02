# M8 Results и базовый Report v1

Статус: `draft QA`, M8 v1.2 остаётся FROZEN, CURRENT не изменён. Контракт
реализует PM-06/PM-07 для одного закрытого Cycle и не вводит Recommendations,
Skill Level, CompetencyScore, Group или Longitudinal Report.

## Вход и идентичность

Producer принимает только Cycle в состоянии `calculated`, согласованные C-46/C-56
одного Cycle и точную revision расчёта. Проверяются ссылки расчёта, Cycle и
`composition_checksum`. Ошибка входа останавливает выпуск; отсутствие расчёта не
становится `no_result`.

На Cycle существует один логический Results. Каждая принятая revision расчёта
создаёт неизменяемую Results revision. Повтор одного idempotency key с тем же входом
возвращает прежнюю revision, с другим входом даёт `IDEMPOTENCY_CONFLICT`.

## Results и C-67

Results сохраняет точные C-46/C-56 refs, состав, профиль и роль, план и полный M2,
Sessions/AS, время, четыре исхода Skills, точные дроби Scores, полноту, пять
покрытий, Confidence, Reliability, ограничения и происхождение. Skills группируются
по Competency; поле Competency score всегда `null`.

C-67 — неизменяемая versioned projection выбранной Results revision. Представления
`assessee`, `customer`, `methodology_qa` различаются раскрытием, сохраняя одинаковые
факты и существенные ограничения. Шаблон `m8_basic_report/1.0.0` проверяется по
checksum и связан с M8 v1.2. `recommendations` всегда пуст.

TargetProfile сохраняется в Report отдельно от Results. Нет требования —
`NO_TARGET_REQUIREMENT`; нет результата — `NO_SKILL_RESULT`; при Target Level и
отсутствии нормативного фактического Skill Level — `NOT_COMPARABLE` с причиной
`NORMATIVE_SKILL_LEVEL_NOT_AVAILABLE`. Score не преобразуется в Level или Gap.

## Выдача и права

Admin API создаёт Results/C-67 и читает/экспортирует разрешённые представления.
Владелец Cycle читает только свой latest Results и `assessee` C-67; сервер повторно
проверяет владельца для прямой PDF-ссылки. Экран и PDF читают один сохранённый C-67.
PDF сохраняет revision, точные дроби, ноль, отсутствие значения, покрытия,
Reliability и ограничения; для кириллицы требуется Unicode font.

Создание остается явной авторизованной операцией. Автоматическое событие после
закрытия Cycle, retry worker и переход из основного прохождения относятся к Task 10.

## Хранение и восстановление

`m8_results` задаёт логическую идентичность; `m8_result_revisions` и `m8_reports`
неизменяемы trigger-ограничением; request keys хранят hash входа. Откат отключает
новые M8 routes/UI consumer. История C-46/C-56/Results/C-67 не удаляется и не
переписывается.
