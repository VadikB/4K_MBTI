# Первичные доказательства PATH-AC-AUDIT-01

`browser-*.json` и `ac05-before.json` — оригинальные Playwright JSON, не сводные
самоотчёты. Исходный EPERM/2 реальных false-success FAIL/ошибка fixture сохранены.
Итоговый `browser-final-pass.json` —100 PASS, HTTP synthetic, localhost/реальный dist.
`admin-{1440,320,390,768}.png` — компонентные synthetic screenshots; программа1.1
в этих fixtures не является заменой exact published1.2 в прежнем real PATH.

`RUN_LOCAL_CHECKS.mjs` сохраняет полные stdout и `local-checks.json`: команды,
sterile environment (без секретов), exit codes, sha256, source/dist identity и
побайтовую идемпотентность build.25 Python =20 HTTP +5 source M3, frontend140.
Логи `.txt.gz` сохраняют stdout без редактирования содержимого/blank lines;
compression исключает проверку форматирования текста процесса как Markdown/source.
Ни одна команда не вызывает provider, не использует рабочую БД и не запускает CI.
Абсолютные локальные tools paths отражают машину исполнения, а не требование этих
же путей на другой машине; аргументы operator позволяют выбрать свой tools root/Python.

`FILES.json` — hashes/bytes68 файлов, включая проверенные source/dist и evidence.
Он не хеширует сам себя; внешний пакет/Git связывает его с commit.
`CHECK.py` проверяет сохранённые byte hashes, before/after причины и результаты,
не повторяет browser/HTTP и не объявляет их новым выполнением. Запуск из полного
восстановленного checkout: `python docs/evc/evidence/path-final-acceptance/CHECK.py`.
`python -O` намеренно запрещён; raw primary files не редактируются ради PASS.

Новый paid run/DB/cleanup/publication/activation/push/PR/merge/deploy отсутствуют.
Прежний paid PASS/e63 и исторический PREP-DIAG-01 UNKNOWN сохраняются отдельно.
