# CHECKS — P4K-REMARKS-COMBINED-2026-11-10

Дата: 2026-11-10. Base: `8e3fb851f7920d3eee31312932057f035068422a`.

| Контур | Результат | Доказательство |
|---|---:|---|
| Package checksum | PASS | `shasum -a 256 -c SHA256SUMS.txt`: 17/17 listed files OK |
| Python compile | PASS | изменённые `Api/*.py`, `PYTHONPYCACHEPREFIX=/tmp/p4k_remarks_pycache` |
| JS lint | PASS | `npm run lint:js` |
| Source → dist | PASS | `npm run build:web` |
| Frontend | PASS | `node --test tests/frontend/*.test.mjs`: 219/219 |
| Backend без integration/e2e/llm | PARTIAL → FIXED | 1039 PASS, 1 устаревшее ожидание transfer; после исправления адресно 7/7 PASS |
| Membership HTTP e2e | PASS | `tests/e2e/test_arch30_membership_http.py`: 9/9 |
| Questionnaire/assignment e2e | PASS | три адресных файла: 26/26 |
| Membership PG integration | PASS | marker-owned `f22_integration_pytest`: 2/2, включая двойную миграцию/backfill |
| Browser renderer/guards | PASS | 191 PASS; затем исправленный questionnaire fixture 1/1 PASS |
| Browser actual HTTP/PG | NOT_RUN | явный `STAND_ADMIN_URL` отсутствовал; тесты fail-closed до действий |
| Full integration | FAIL (вне адресного контура) | 290 PASS, 4 SKIP, 12 FAIL, 25 ERROR; stand fixtures отклонили имя maintenance DB, плюс независимые legacy failures |
| Whitespace | PASS | `git diff --check` |

## Acceptance coverage

- `SUP-AC01..05`: PASS по HTTP/e2e и marker-owned PG; restart/CI — ожидает CI.
- `SUP-AC06`: PASS существующих purge frontend guards; полный lost-response stand — ожидает CI.
- `SUP-AC07`: PASS UI/frontend/e2e; legacy endpoint возвращает 410 без мутации.
- `SUP-AC08`: PASS renderer viewports; owner visual acceptance — `PENDING`.
- `ADM-AC01..04`: PASS code/e2e/renderer; actual HTTP/PG browser — `NOT_RUN` без stand.
- `ADM-AC05`: PASS 22 guards и расширенный auth/browser regression.
- `ADM-AC06`: PASS шести visual states на 1440/390/320/200%; owner — `PENDING`.
- `PART-AC01..04`: PASS frontend/browser renderer и production-function checks.
- `PART-AC05`: PASS существующих recovery unit/browser checks; owned HTTP/PG PATH29 — `NOT_RUN` без stand.
- `PART-AC06`: PASS renderer viewports; исторический случай — `UNKNOWN`, owner — `PENDING`.

## Откат

Revert кода до применения постоянной миграции допустим. После появления явных
`is_participant=FALSE` старый runtime снова интерпретирует admin как участника, поэтому
перед rollback необходимо восстановить участие по зафиксированному snapshot либо
оставить новый read-contract. Удалять колонку без такого восстановления нельзя.
