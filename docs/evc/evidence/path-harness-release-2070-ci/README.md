# PR175 — исправление изоляции нового unit-теста

Завершён локальный повтор: backend922 PASS/354 deselected,343.80s; HTTP108
PASS/12 deselected,94.65s. Python/test bytes совпадают с source
`db79007c4ab13780591f027ae4f38c0cc453c89d`; full run начат до фиксации commit
без последующего изменения исполняемых bytes. После фиксации source отдельно
повторены35 runner/release/CI PASS (verified-on-db790.xml). Final commit только
docs/evidence; новый обязательный CI exact head/base ещё требуется.
Новый CHECK проверяет local JUnit и checksum manifest; старые134 files immutable.

Предыдущий head1cd972f, CI [42212416209](https://github.com/VadikB/4K_MBTI/actions/runs/42212416209/job/127874041662):
Unit tests **1 FAIL/920 PASS**, HTTP SKIP после отказа. Raw primary log сохранён
lossless gzip без временного signed download URL; публичный checks-before.json
сохраняет head/URL/status. Это не успешный CI и не дефект admission.

Ожидание: unit file-hash проверяет настоящий hash collector без требований к
remote refs машины. Факт: новый test вызывает code_identity с rev-parse origin/main;
CI pytest checkout shallow и такого ref не имеет. Runtime корректно отказывается
при отсутствии ref, менять его на выдуманный SHA/fallback нельзя.

Исправление только tests/unit/test_assessment_first_case.py: явная **unit-only
подстановка Git metadata**, настоящие file bytes/hash; дополнительная регрессия
подтверждает прежний runtime fail-closed (CalledProcessError128) без origin/main.
Это не fake Connection/resolver/HTTP/PG, те проверки и код продукта неизменны.
Никакой fetch/правки CI/relaxation ради PASS и никакого второго bump2.0.70.

Проверки: targeted.xml35 PASS (runner13 +release/CI22). В новом восстановленном
shallow checkout без origin/main old test воспроизвёл1 FAIL (shallow-before.xml.gz),
после исправления проверяются адресно2 Git/hash tests (shallow-after.xml).
Промежуточный собственный probe скопировал весь test module вне tests/unit:
12 PASS/1 FAIL из-за неверного __file__-relative пути другого summary fixture;
shallow-layout-negative.xml.gz сохранён, не выдан за product/CI defect или PASS.
В штатном расположении весь module входит в35 PASS.

Исходные manifests/пакеты2fa1 и1cd не переписаны. Старый CHECK355 source hashes
запускается на immutable1cd/4510 snapshot (восстановление уже PASS); текущая ветка
от него отличается ровно новым unit-файлом и docs/evidence. Новый CHECK здесь
проверяет остальные354 source hashes и известный новый hash unit-файла, а также
сохранность134 primary files; не маскирует изменение unit как byte equality.
Полные backend/HTTP повторены как указано выше; новый CI нужен для final head.
Main/последнее подтверждённое test3f42bba/2.0.69; merge/deploy/paid AC18 запрещены.
PREP-DIAG-01 исторический UNKNOWN, отдельно от этой установленной ошибки теста.

Первый staged diff-check отклонил whitespace внутри raw negative JUnit traceback.
Hook не обходился и bytes не редактировались: эти два XML lossless gzip; CHECK
читает сжатый primary. Передача повторена после штатного diff-check.
