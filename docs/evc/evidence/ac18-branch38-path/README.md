# AC18 — primary evidence полного PATH кандидата38bf8244

07.11.2026. Один отдельно разрешённый новый real-provider run
`8336eef355fc43b49c1837fc89e2868e`: PASS на точном
`38bf82448e63e55414ff55ac45fa126e9c4385f0`, до какого-либо нового выпуска.
Изменения UI/harness присутствуют в этой ветке; receipt не переименован в будущий SHA.
Формальная приёмка deployed выпуска этим run не закрывается автоматически.

`remote/` содержит64 оригинальных безопасных JSON/PNG с delivery-manifest hashes.
Подкаталог `remote/run-evidence/f69393c0-1bb9-4617-894d-2904238adb49/`:
source-provenance и exact published receipt; pre-start и first-case receipts;
completion/process/cleanup, screenshots/viewport geometry и assignment replay.
Raw server/runner logs, `.env`, secret state, cookies/auth tokens не экспортированы.
Безопасная проекция логов сохраняет только allowlisted metadata, не тела/queries.

Generation1 +tester5 batches/33 required checks +challenger4 batches/32 protected
checks; admission PASS/admitted=true; repair=false.10 уникальных операций,
10 завершённых HTTP-запросов, transport attempt1 каждый, JSON parse failures0;
712010 prompt +37353 completion =749363 tokens, модельdeepseek-flash.
StartHTTP20108:46:06.274840UTC; Cyclea8f1b6bb-cc41-4df2-95e6-77a296d1be4f,
ASdcaa65f1-d527-477c-a009-c26d7d298700, оценочных ответов0.
Пять фаз×1440/320/390/768 и7 W02 screenshots визуально просмотрены;
VIEWPORT-REVIEW.json сохраняет список/hashes. Дополнительных LLM по ширинам нет.

Все source/terminal receipts сохранены и readback проверены до штатного destroy.
Owned-БД product4k_pytest_8336eef355fc43b49c1837fc89e2868e и secret state удалены;
отдельный READ ONLY maintenance readback08:46:45UTC: DB0/connections0/port free.
Это удаление синтетической среды, не рабочей БД; evidence не является дампом БД.
Исходники/источники позволяют воспроизвести сценарий новым отдельно разрешённым run.

Без БД/LLM и внешних зависимостей:

```sh
python3 docs/evc/evidence/ac18-branch38-path/VERIFY.py
```

Расширенный `--checkout` допускает только точный38bf8244 и требует project Python
dependencies и Node; он не переносит PASS на release commit с другим SHA.
Применимость к metadata-only release проверяется отдельно, а не ослаблением verifier.

Полный локально переданный владельцу пакет:
AC18-BRANCH38-PASS-20261107-38bf8244.zip (7040790 bytes), SHA256
e6dd3a0e6941c470d830021ca136e3ab8a536bf5db9f741717b8cb360adea6bc.
Он включает128 manifest files, исходники/diff/incremental Git bundle и исторический
negative auth-run. В Git здесь хранятся сами первичные64 файла, не только ссылка
на локальный ZIP. PREP-DIAG-01 остаётся отдельно UNKNOWN.
