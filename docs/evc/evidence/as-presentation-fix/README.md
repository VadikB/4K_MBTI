# Evidence AS-PRESENTATION-DIAG-01

- [Source identity](source-identity.json):22 неизменённых файла/контракта и9 Case/AS refs.
- [Cleanup](cleanup.json): точный owned PostgreSQL, export →0 schemas/connections →remove.
- [Отчёт](../../reports/as-presentation-fix.md): причины, границы, команды и ограничения.

Доступный пакет `4K_AS_PRESENTATION_FIX_20261106.zip` содержит code-identity.json,
changes.patch, changes.bundle, source snapshots, этот отчёт и первичное evidence:
JUnit before/after, actual PostgreSQL/HTTP readbacks, screenshots/viewport JSON,
checks.json и offline VERIFY.mjs. Точный SHA выдаётся в пакете, не угадывается по
версии локальной сборки. `node VERIFY.mjs` проверяет hashes и public readback links
без .env, БД, браузера, доступа GitHub или LLM.

Отрицательные результаты сохранены отдельно:9 red failures исходного materializer;
browser failures до устранения repeated DOM render;119/1 первого expanded suite;
interim fixture/procedure failures. Они не переименованы в PASS. Финальные результаты
и точные применимые байты перечислены в checks.json/code-identity.json пакета.

Исторический AC18 не перепакован и не изменён:
`4K_AC18_2070_e9639ed_20261106_FINAL.zip`, SHA256
`2d2edccbfc3b5470f32822c70913474aa6d756ff0465b60709f32795d1954501`.
Новый пакет не подтверждает human admission, полноту M2 или новый real PATH.
