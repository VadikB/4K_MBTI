# Независимая проверка серии A/B — 25.10.2026

## Проверяемый результат

- исходное основание задания: `f4af7beb0d09374153bf0e16c6edb5c0dabe1cec`,
  приложение `2.0.16`, PR #102;
- итоговый проверяемый `main`:
  `2e4aa4000799e329e095a68ccd2d114e656267d3`, приложение `2.0.25`, PR #112;
- test readback 25.10.2026: `GET https://test.4k-assistant.ru/users/version` →
  `{"version":"2.0.25"}`;
- post-merge workflow `40189333177`: `frontend`, `pytest`, `deploy-test` — PASS.

Пакет является индексом проверяемых доказательств, а не новым baseline и не
методологическим заключением. Его собственный commit заполняется после создания
коммита/PR и не меняет проверяемый product commit.

## Состав

- `status-matrix.json` — статус каждого A/B и точная граница доказательства;
- `ci-and-releases.json` — head/merge SHA, версии, PR и CI;
- `evidence-index.json` — первичные и производные доказательства;
- `verification-commands.md` — воспроизведение и фактические результаты;
- `INDEPENDENT_CONCLUSION.md` — незаполненное заключение проверяющего;
- `MANIFEST.sha256` — целостность файлов этого каталога, кроме самого manifest.

## Итог исполнителя

| Пункт | Технический статус | Ключевая граница |
|---|---|---|
| B01/B02 | PASS | public projection и owner/replay закрыты; первоначальный PR head имел один неуспешный pull_request CI из-за отдельно исправленного M10 lock-order, итоговый main зелёный |
| A01 | PASS | 55/55 до M6 на package 0.3; draft не равен публикации/методологическому допуску |
| B03/A02 | PASS | штатные planner outcomes и единый accepted-AS path; real-provider breadth относится к A06 |
| A03 | PASS | controlled concurrency/PostgreSQL; Reliability и real-provider не присвоены |
| A04 | PASS | frozen manifest/resolver; provider alias не становится побайтово воспроизводимым автоматически |
| A05 | PASS в заявленной области | 39/61 и 22 отсутствующих показаны честно; каталог не расширен |
| A06 | PARTIAL / честный остаток | harness и controlled evidence PASS; 27 полных real-provider HTTP/DB/M6/M8 строк остаются NOT_RUN |
| A07 | PASS технический | controlled semantic validator; real-provider и методологическая приёмка NOT_RUN |

## Не смешивать статусы

- `technical`: код, контракт, unit/HTTP/PostgreSQL/browser проверки;
- `controlled_ai_tester`: tester через управляемый gateway; это не real-provider;
- `real_provider`: только сохранённые явно маркированные трассы;
- `methodology`: заключение человека-методолога, здесь не заполнено;
- `publication`: lifecycle пакета/DB revision; draft не опубликован автоматически;
- `reliability`: отдельная эксплуатационная приёмка, здесь не присвоена.

## Остаток для владельцев

1. Независимый проверяющий заполняет `INDEPENDENT_CONCLUSION.md` на неизменяемом
   commit пакета.
2. Методолог утверждает oracle и допустимость интерпретаций; технический исполнитель
   не ставит этот PASS.
3. Если требуется закрыть A06 шире заявленного технического harness, нужны отдельный
   допуск и новые несоставные real-provider run для 27 Case/function строк с полными
   HTTP/UI/DB/M6/M8 трассами.
4. Reliability и pilot admission остаются отдельными решениями. Draft package 0.3,
   runtime 1.1.0 и M8 prompt 1.2.0 не становятся CURRENT/FROZEN из-за этого отчёта.

## Откат

Удалить/revert только этот индекс. Ни один исторический snapshot, FROZEN package,
AS, result или первичная трасса не изменялись.
