# PERS-01–PERS-06: пакет доказательств

Порядок независимого чтения:

1. `docs/evc/reports/pers-functional-personalization.md` — границы и итоговая сводка.
2. `docs/evc/pers-methodology-export.json` — машинная выгрузка статусов.
3. `protocol-v2-final-summary.json` — связь 27 позиций с конечными AS и допуском.
4. `transformation-verification.json` — нормализация и локальное исправление.
5. `technical-recovery-v2/summary.json` — две восстановленные технические позиции.
6. `negative/summary.json` и `scenario-v2-executed/summary.json` — 27 отрицательных
   и 34 сценарных проверки.
7. `full-cycle-attempt-summary.json`, `full-cycle-real-final.json` и
   `full-cycle-real-repeat.json` — история и успешные трассы M5→M8.
8. `INDEPENDENT_CONCLUSION.md` — форма отдельного человеческого заключения.
9. `MANIFEST.sha256` — контрольные суммы всех файлов архива.

Draft-пакет остаётся `runtime_enabled=false`. Технический PASS не присваивает
методологии `CURRENT/FROZEN` и не разрешает пилот на людях. Секреты не включены.

Основные воспроизводимые команды приведены в `COMMANDS.md`. Проверка архива:

```bash
shasum -a 256 -c MANIFEST.sha256
```
