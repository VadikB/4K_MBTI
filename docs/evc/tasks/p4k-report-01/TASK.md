# P4K-REPORT-01 — завершение Cycle и сохранённый Report

Статус: PATCH-кандидат 2.1.12 и локальная проверка; исходная база `origin/main` =
`2afcc37912fb2219f0710a5836b7417ce01d8e8e` (2.1.11), ветка
`codex/p4k-report-01`. Текущий основной checkout с чужими изменениями не менялся.

## Результат и границы

Один закрытый Cycle продолжает обработку после рестарта, сохраняет один
логический Results и один доступный владельцу Report. Клиент различает ожидание,
готовность, ошибку подготовки и потерю соединения; повторное чтение не запускает
обработку. Служебная попытка после ошибки использует корректные C-56/Results.
Обычная перегенерация удалена. Не входят изменения M6-алгоритмов, отчётные
содержательные блоки REPORT-03/04, радар REPORT-05, PDF REPORT-10 и релиз TEST.

## Источники и связь

- Поручение: `/Users/vadim_bogachev/Downloads/P4K_REPORT_01_Completion.txt`,
  SHA-256 `573cd5df13ca99696082a1fa49dcb68e4809bc1aca96107c3f82fffe32dba1db`;
  общий файл `00_START_P4K_REPORTS_2026-11-15.txt`, SHA-256
  `593959b60edf0eab30c19a1e8cc2e9acb6496a0c9bf6b0df2bde211883168d1e`;
  reference zip, SHA-256
  `887f7200a85bb4f97a52b2035efd72e234ca42919460fb8f0b5ea30c458a346a`.
  Из него прочитаны `SOURCES_AND_SCREENS.txt`, `CURRENT_PRODUCT_DECISIONS.txt`,
  `prototype/UI_BASELINE.md`, экранные сцены и исходники прототипа.
- Product Architecture v1.0 + Change 01, 01.10.2026, WORKING:
  `docs/architecture/product-4k/1.0/updates/2026-10-01/source.md`, И-1,
  И-5–7; PDF SHA-256
  `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`.
  Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, архитектурные
  `context.md`/`registry.md`, EVC workflow, verification matrix, artifact recipe,
  task template, review checklist и `tests/README.md`.
- M7 v1.3 FROZEN, производный текст §§7.5/7.7.5 и закрытие,
  исходник SHA-256 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`;
  M8 v1.2 FROZEN, §§1.3, 2, 7, 9, исходник SHA-256
  `a61909c996f66e88668c4cf713fb91129f3ab778ed843d0e796c7d4e226b73fa`.
  M1 v1.4 FROZEN/CURRENT=NO; выбранный Task SourceSet в
  `docs/methodology/source-sets/2026-10-01/manifest.json`.
- Правило M7 «закрытый Cycle не открывается» → `m7-completion-contract`/C-46 →
  `Api/m7_completion.py`, `Api/m10_orchestration.py` → SQL/browser закрытия.
  Правило M8 «Results после закрытия и расчёта, допустимый C-67» →
  `m8-results-report-contract`/C-56/C-67 → `Api/m8_results.py`,
  `Api/m8_descriptive_report.py` → fault injection/HTTP/browser.
  LU-04.7/05.4/06.2/06.4/07.1/07.2; PM-04/05/06/07.

## План и технические решения

1. Повторить выявленный обрыв Results → Report и проверку обычной регенерации.
2. Использовать существующий M10 worker. Добавить DB claim на Cycle с токеном,
   heartbeat и сроком 10 минут; после аварии продолжить из `calculated`.
   Уникальные ключи M6/M8 и сохранённые checksums защищают повторы.
3. Ошибка описания не публикует пустой `assessee` Report. Успешный C-56/Results
   служебная попытка читает повторно; ошибочный расчёт имеет отдельную ревизию.
   Суперадминистратор с `configuration.publish` остаётся сервисным актором.
4. Удалить owner regenerate и закрыть вторую публикацию через admin M8 route;
   сохранить внутренние synthetic fixtures для адресных проверок.
5. Проверить UI на 1440/390, адресно 320 и эквивалент 200% от 1440; сохранить
   скриншоты и synthetic PDF.

Пробел: source-set фиксирует нормативные версии, но продуктный проход не
доказывает содержательную валидность живого LLM. Транспорт здесь controlled.
Ноябрьское решение владельца в приложении заменяет старое требование об обычной
owner-регенерации. Стоп-условия EVC: новых предметных норм, удаления данных,
нового артефактного контура и изменения M6 нет; API-изменение прямо включено в
поручение, схема аддитивна, восстановление и откат описаны ниже.

## Проверки и выпуск

Минимум: fault injection unit/HTTP, isolated PostgreSQL integration,
controlled browser, `node --test` затронутых frontend, ESLint, web build,
`git diff --check`. Один worker, retries=0, 0 реальных LLM/писем.
Browser: тестовый лимит 240 с; один сценарий, максимум 70 с ожидания Report,
остановка при отсутствии готовности; отдельный операция GET 4 с.
Другие случаи представлены короткими SQL/HTTP-fixtures. CI `frontend`, `pytest`
и `full-verification` требуется на точном head перед merge.

Миграция: `m10_report_claims` создаётся действующим `ensure_schema`, старые
строки не меняются. Откат к предыдущему runtime оставляет таблицу и immutable
Results/Reports невостребованными; уже закрытые Cycles не открывать, сохранённый
outbox/Results продолжить совместимым worker после восстановления.
Флаги: `version_bump=true` через `ready:prepare -- --candidate 2.1.12` на
актуальном main; `branch_push=false`, `pr=false` до фактической публикации;
`merge=false`, `deploy=false`, `artifact_publish=false`.
