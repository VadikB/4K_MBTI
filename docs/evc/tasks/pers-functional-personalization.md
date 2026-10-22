# PERS-01–PERS-06: функциональная персонализация девяти Case

## Результат и границы

Единый draft-пакет девяти `CASE.SPEC.01–09` из источника v0.2 подключён к
существующему schema-v3/C-34 контуру. Базовая роль —
`specialist_expert`; профессия остаётся контекстом. В задачу не входят
рекомендации развития, mini cases, CURRENT/FROZEN и методологический допуск.

## Источники и решения

- Запрос владельца и `P4K_Functional_Personalization_Block_2026-10-22`, редакция 1.0.
- Source package `P4K_All9_Functional_v0.2`, checksum `149/149 PASS`.
- Паспорта Case: v0.5, v0.6, v0.4, v0.5, v0.5, v0.4, v0.4, v0.4, v0.4;
  status `WORKING`, `CURRENT=false`.
- M1 v1.4 FROZEN/CURRENT=NO, M2 1.0/1.1, M3 1.0, M4 1.0, M5 1.1,
  Change 01, ADR-002 C-23/C-24/C-34/C-45/C-46/C-54/C-56/C-67.
- База задачи: `origin/main d54dbba`, product 2.0.14; она новее указанной
  в handoff `c197226`/2.0.13 и не откатывалась.

Стоп-условий для статической интеграции нет. Публикация runtime, реальная
LLM-матрица и Cycle зависят от прохождения обязательных прогонов; их нельзя
подменять статическим PASS.

## Трассировка

| Источник / правило | Контракт | Код / артефакт | Проверка |
| --- | --- | --- | --- |
| Поля Case 1–22, события, персонажи | CaseVersionV3 / C-34 | `build_m5_functional_package.py`, package 0.2 | `test_m5_functional_package.py` |
| Одна BaseRole, frozen profile | C-23/C-24/C-34 | существующие M4 snapshot и `m5_storage` | M4/M5 unit + integration |
| Полная AS, prompt/model/operation refs | C-34, AI trace | Generation contract/instructions v0.2; existing equivalent-generation operation | package + provider tests; real LLM required |
| Допуск до предъявления | C-34 QA evidence | QA plans, admission flags, validator boundary | 27 negative + positive tests; real tester required |
| Возврат в ту же AS, event visibility | C-45/C-54/C-46 | existing scenario runtime/M7 return | scenario/runtime integration |
| Evidence→IA→M8 и пять покрытий | C-45/C-56/C-67 | existing M6/M7/M8 pipeline | isolated DB full Cycle |

## План, проверка, откат

1. PERS-01: собрать девять Case без потери полей.
2. PERS-02–04: проверить profile/generation/QA контракты и реальный provider.
3. PERS-05: прогнать сценарии, идемпотентность, pause/return и C-45.
4. PERS-06: 27+27+34, все 9 Case, один полный Cycle, export и release report.

Локальный минимум: package verify, целевые unit/integration/HTTP/browser,
`git diff --check`, полные non-LLM pytest и frontend. Перед merge обязательны свежий
`main`, CI `frontend`/`pytest` и review. Откат: оставить package `runtime_enabled=false`,
не публиковать его в каталог; сохранённые AS и их snapshots не изменять.
