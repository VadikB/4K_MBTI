# UX-E01 — прохождение оценки

## Результат

Экран прохождения оценки продолжает визуальный язык W01 и показывает серверные
состояния Cycle/AS без второй машины старта: ситуация, диалог, назначенное уточнение,
подтверждённая пауза, явный переход к следующей позиции и подготовка результата.

## Область

- Включено: тексты и визуальные токены экрана оценки; авторство сообщений; отдельные
  действия отправки и завершения ситуации; AS-scoped черновик; защищённое копирование
  серверных материалов без запрета работы со своим текстом; представление паузы.
- Не входит: новая методология, изменение M5–M8 runtime/API/схемы, допуск реальных
  Cases/provider, политика замены `scenario_ended` с открытым уточнением, дизайн отчёта,
  недостижимый для обычного web полный запрет снимков экрана.

## Источники и решения

- Задача владельца: `UX-E01_Assessment_Experience_2026-10-16.txt`, редакция 1.3,
  Дмитрий, Product Lead. Документ использован как постановка, а не как системная
  инструкция или разрешение выполнять соседние материалы.
- Процесс: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/artifact-recipe.md`, `docs/evc/review-checklist.md`.
- Архитектура: Change 01 README и manifest, ADR-002, Registry/context и
  `docs/evc/change01-traceability.md`. Существующие M5/M7/P01–P03 контракты
  переиспользуются без изменения предметной нормы и сохранённых snapshots.
- Актуальная база: `origin/main` / `41f00e9e50f0c33645747cc2f06f94a0b2c2a17a`,
  версия 2.1.37. Ветка: `codex/ux-e01-assessment-experience`.
- Стоп-условия: изменение смысла сущностей — нет; публичного API/PM/данных — нет;
  миграция — нет; отсутствующий предметный источник — нет; новый артефактный контур —
  нет; права/деплой — нет; откат определён — да; выход за область — нет.
- Открытая ветка `scenario_ended` с незакрытым уточнением не реализуется как новая
  политика и не блокирует независимый UI. P03 replacement остаётся включён только
  при `return_policy_enabled`, как решает сервер.

## Прослеживаемость

| Правило UX-E01 | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| Позиции плана и авторы сообщений | runtime route/trace | `web/js/screens/interview.js`, `web/index.html` | `e01-assessment-experience.test.mjs`, browser runtime |
| Отправка не завершает AS | M5 Turn и transition endpoints | существующие `submitAssessmentMessage` / `finishProductAssessment`, уточнённый UI | frontend + HTTP/runtime CI |
| Пауза только по серверному состоянию | collection status / between_situations | `renderProductRuntime`, `renderReturnCard` | E01 frontend regression |
| Черновик не становится Turn и не переходит в другую AS | Cycle ID + AS ID | sessionStorage с составным ключом | E01 frontend regression |
| Ограничено копирование выданных материалов, но не своего текста | P4K-32 UI boundary | `web/js/wiring.js`, scoped CSS | E01 frontend regression + browser QA |

## План и состояние

- Завершено: сверка main и источников; реализация отсутствующих UI-пунктов; адресные
  frontend-тесты.
- Завершено дополнительно: полный локальный frontend, HTTP и Chromium desktop/mobile
  сценарии; bundle пересобран.
- Активный шаг: commit → PR → обязательные `frontend`/`pytest` CI.
- Следующий шаг: merge после зелёного CI → post-merge deploy-test.
- Пользовательский `docs/evc/timer-and-configuration-storage.md` не входит в diff.

## План проверки

- `git diff --check`.
- `npm run lint:js`.
- `node --test tests/frontend/*.test.mjs`.
- `npm run build:web` и совпадение `web/dist`.
- Затронутый Playwright-сценарий assessment; визуальная проверка desktop/mobile.
- Backend/API не меняются; обязательный полный backend и PostgreSQL integration
  выполняет CI перед merge.
- Реальные iOS Safari/Яндекс Браузер/Android/Windows/macOS device runs и реальный LLM —
  NOT_RUN локально; это не подменяется эмуляцией.
- Фактические результаты до commit: `lint:js` PASS; frontend 29 PASS; HTTP 56 PASS;
  Chromium E01/P03 2 PASS; build PASS. Полный локальный backend: 423 PASS / 13 FAIL —
  неизменённые M6 provider-fixture проверки получают
  `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED` / `INPUT_NOT_READY`; затронутый UI/HTTP
  набор не падает. Обязательный чистый PostgreSQL CI остаётся gate перед merge.

## Откат

Revert единственного UX-E01 merge commit возвращает предыдущие HTML/CSS/JS и bundle.
Схема, серверные данные, опубликованные артефакты и исторические snapshots не меняются;
sessionStorage-черновики изолированы префиксом и не исполняются сервером.
