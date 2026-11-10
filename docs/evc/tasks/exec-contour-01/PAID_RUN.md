# EXEC-CONTOUR-01 Подготовка real provider run

## Стоп-условие

Команда ниже подготовлена, но не запущена. Нужен отдельный прямой допуск владельца
на один paid run, его бюджет и точный evidence root. Повтор после сбоя не разрешён
автоматически.

## Команда

В checkout точного кандидата на проверенной машине:

```sh
PYTHONPATH=. /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  scripts/assessment_first_case.py \
  --profile ac18-to-report \
  --program-source published-pilot \
  --program-receipt /home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json \
  --program-receipt-sha256 09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b \
  --program-version 1.2 \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  --db-admin-port 55432 \
  --port 19341 \
  --directory /home/vadim_bogachev/evidence/exec-contour-01-<approved-run-id>
```

До допуска разрешён только тот же вызов с `--preflight-only`: он не вызывает provider.
Selector проверяется до credentials/БД, а composite сохраняет прежний
`first-case-receipt.json` и новый terminal `execution-contour-receipt.json`.

## Оценка затрат и предел учёта

Исторически сопоставимая подготовка первой AS зафиксировала 10 уникальных operations,
`710759` input и `36791` output tokens (`747550` всего). По тарифу `deepseek-flash`
на 10.11.2026 ([официальная тарифная страница](https://api-docs.deepseek.com/quick_start/pricing/))
cache-miss стоимость такого объёма составляет примерно `$0.1287`
off-peak или `$0.2573` peak. Это ориентир **одной подготовки**, не всего Cycle.

Полный paid run дополнительно оплачивает подготовку следующих AS, dialogue/interim,
clarification/finalization и descriptive Report. Точного верхнего денежного cap из
текущего product trace получить нельзя: число фактически выбранных AS/ветвей и
повторов зависит от runtime, а usage malformed JSON retry может не сохраниться.
После прогона отчёт показывает retained unique-operation usage, HTTP completions,
transport attempts и parse failures; полную сумму подтверждает provider billing delta.
Допуск должен задать внешний budget cap; неполная trace-сумма не называется полной.
