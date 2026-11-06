# Evidence кандидата2.0.71

`python docs/evc/evidence/as-presentation-release-2071/CHECK.py` — offline hashes,
JUnit counts/negative history, public readback links и viewport geometry.
Никаких Git refs/.env/credentials/БД/LLM. Это integrity check, не новый PATH.

Два raw XML хранятся в .gz: сохранены исходные пробелы error log и окончания строк,
а не исправлено первичное evidence ради Git whitespace gate. Manifest проверяет
также uncompressed_sha256; CHECK автоматически читает gzip без изменения данных.

- release-idempotence.json: подготовка/повтор2.0.71,49 metadata/build files unchanged.
- source-continuity.json:17 существенных runtime/test/profile файлов byte-identical
  source6f5681e.22 immutable source/contract hashes и9 Case refs остаются в
  ../as-presentation-fix/source-identity.json. Старые manifests не переписаны.
- primary/*release-2071*.xml и frontend.xml: новые937 backend/108 HTTP/50
  targeted/4 browser/145 frontend PASS. Browser — source-backed synthetic HTTP,
  реальные static entry/dist, live polling,4 widths, actual last-material viewport.
- primary/source-postgresql:5 оригинальных readback **из исходной** бесплатной
  component regression6 PASS, скопированы byte-for-byte до/после release. Это real
  PostgreSQL/HTTP, но provider/QA/upstream start/token identity — controlled
  fixtures, не human review или admission пилота. Нового PG run в release нет.
- primary/as-presentation-before.xml:9 FAIL/2 PASS исходного materializer.
- primary/as-presentation-browser-suite.xml:119/1 первого source expanded browser,
  единичный AC05 UNKNOWN; последующий120 PASS сохранён отдельно, не переписан.
- ../as-presentation-fix/cleanup.json: исходный owned container удалён после export.
  Release не создавал БД и не подключался к постоянной. Real LLM calls0.

Исходный доступный пакет6f5681e (SHA256 c50022dc7aaff950d752664af64a1e6970305a41b60cb453de6f3f1ade69ef78)
сохраняет полную отрицательную историю и source bundle. Его VERIFY не запускается
на изменённой metadata2.0.71 как проверка ложной идентичности; source остаётся6f.
CI и human review будущего точного release head обязательны; локальные evidence
не разрешают merge/deploy/платный AC18. PREP-DIAG-01 UNKNOWN отдельно.
