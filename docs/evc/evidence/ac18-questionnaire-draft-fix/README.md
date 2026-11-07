# Evidence локальной правки Q-DRAFT-01

`actual-http-pg/` —36 первичных файлов четырёх новых owned-прогонов: run/source
hashes, SQL baseline, значения до/после настоящего GET, confirmed HTTP/SQL readback,
результат и owner cleanup, before/after PNG. Нет refill, подмены ответа/Connection/
resolver/DOM, LLM или PATH acceptance. Source/code version описана в run receipts:
base d8ecd81d + точные SHA256 исполнявшихся JS/dist/test files.

```sh
node tests/questionnaire_draft_fix_verify.mjs
```

Проверено:4 PASS_UI_HTTP_PG_NOT_AC18,4 cleanup, refill0, provider0. Tree checksum36
case-files: `93e2dc1322537fd5c48df8d3e697592737d149f6c433d879ad594a7abfc82d0d`.
Для более позднего дерева verifier принимает явный `--source-ref <exact SHA>`,
проверяя те же hashes по неизменяемым Git objects, без сети/БД/provider.

Предыдущие43 отрицательных diagnostic files **не переписаны** и находятся отдельно
в `docs/evc/evidence/ac18-questionnaire-draft-diagnosis`. Проверять их прежний код:

```sh
node tests/questionnaire_draft_diagnostic_verify.mjs \
  --source-ref d8ecd81d27a0633cbdc5f4d707804c32900e99d5
```

Историческая причинная идентичность с конкретным AC18 не доказана;
PREP-DIAG-01 и timeout-cleanup отдельно UNKNOWN. Нормальный cleanup этих4 завершённых
прогонов не является проверкой cleanup при timeout. Эти files не подтверждают
методологический/human допуск пилота или финальный real-provider AC18.
