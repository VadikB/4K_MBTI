# ADM-LAYOUT-31 — I08

Снимки получены Playwright на одном синтетическом fixture без PII, писем и LLM.

- `before-de8261d/` — воспроизведён неизменяемый base `de8261d6455719d6c300554d01789118ec9c044c`.
- `after-working-tree/` — финальная локальная сборка ветки `codex/adm-layout-31`; точный SHA фиксируется в отчёте после коммита.
- Общие размеры: desktop `1440×1024`, mobile `390×844`.
- `01`–`06`: участники, account menu, данные организации, анкета, preview/confirm, mobile participants.
- `07`–`09` (только after): подтверждение отмены, конфликт уже начатой оценки, успешная отмена.

Команды воспроизведения:

```text
P4K_STATIC_ROOT=<archive-of-de8261d> ADM_LAYOUT_EVIDENCE_DIR=<before-dir> npx playwright test tests/browser/auth-r03.spec.mjs --grep "I08 captures" --workers=1
ADM_LAYOUT_EVIDENCE_DIR=<after-dir> npx playwright test tests/browser/auth-r03.spec.mjs --grep "I08 captures" --workers=1
```

Изображения являются доказательством геометрии и состояний UI, но не заменяют HTTP/DB/race-проверки P06.
