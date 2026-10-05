# Task 11.1 — исправление оснований Recommendations

## Разведка и план

База: `14cf514e5420fe095a45285619498024b73c0c0e` (актуальный origin/main,
получен 05.10.2026). Ветка: `codex/task11-1-recommendation-basis`.
Посторонний diff отсутствует. Задание: редакция 1 от 05.10.2026, предоставлено
пользователем с запросом реализации. Merge/deploy исключены.

Прочитаны README, CONTRIBUTING, EVC workflow, verification-matrix,
artifact-recipe, архитектурный context/Registry, Change 01 README и manifest,
отчёты Task 10/11; M8 v1.2 §6–6.1, M6 v1.8 §6–7, относящиеся потребители
C-56/Results/C-67 и unit/integration тесты. Точные источники — manifest
`docs/methodology/source-sets/2026-10-01/manifest.json`; FROZEN/CURRENT не меняются.

Причина: `_basis_for` принимает наличие revision_id за доказательность,
не использует admissions и заполняет пустое основание утверждением о проявлении.
`generate` безусловно выпускает три типа. Чтение старого C-67 не проверяет блок.

До изменения: синтетический partial с единственным IE, пустыми refs и
confirmed_features породил 3 рекомендации с выдуманным проявлением;
`PYTHONPATH=. .venv/bin/python /tmp/r11_counterexample.py` — FAIL (exit 1).

План:
1. Проверить сохранённую цепочку Results → C-56 → IA → Evidence/Dialogue,
   отделить техническую целостность от предметного допуска M6.
2. Новая версия пакета: фильтрация до выбора, адресные практики,
   отдельные исходы отсутствия основания и технического сбоя.
3. Совместимое безопасное представление исторического C-67 без UPDATE/GET-регенерации;
   единое представление UI/PDF, новая явная Report revision при регенерации.
4. R11.1-01–10, backend/HTTP, изолированный PostgreSQL, пакетные проверки,
   PDF/выдача; отчёт и отдельный commit/PR.

Границы: admission M6 не пересчитывается (8.1); IE без отдельного разрешения
на конкретный вывод не используется. GC/Reliability и экспертное утверждение
шаблонов не присваиваются. Полная browser-трасса остаётся в 10.3.

Откат: отключение рекомендаций с сохранением безопасного фильтра выдачи,
фактического Report и immutable истории. Возврат небезопасного v1 запрещён.

## Проверки

Локальная техническая проверка выполнена. Приёмку владельца, экспертное утверждение,
GC, Reliability, merge/deploy этот отчёт не присваивает. HEAD реализации фиксируется
отдельным коммитом; точный состав: `git diff 14cf514e5420fe095a45285619498024b73c0c0e..HEAD`.

| Проверка | Статус и доказательство |
| --- | --- |
| R11.1-01 | PASS: unit IE перед допустимым IA и перестановка; PostgreSQL mixed использует K1.I17, исключает IE K1.I16 того же Skill K1.4 |
| R11.1-02 | PASS: IE, пустые refs, декларация без доверенной проекции; сохранённый empty → unavailable |
| R11.1-03 | PASS: подмена Cycle, Results/admissions, IA, Evidence, дубли; фактическое разрешение фрагмента до turn; scope Skill/Component проверяется генератором |
| R11.1-04 | PASS: unit full/partial/no_result; PostgreSQL qualitative с result_without_score сохраняет рекомендации |
| R11.1-05 | PASS: missing/denied admission, uncertainty, contradiction исключаются; numeric=false при interpret=true не запрещает qualitative |
| R11.1-06 | PASS: подтверждённое действие допускает три содержательно разных типа; mixed и обоснованный L0 получают только Development |
| R11.1-07 | PASS: 2.4 / Target L2 / NOT_COMPARABLE без Gap; новый profile id=8 в PostgreSQL не меняет snapshot и текст при регенерации |
| R11.1-08 | PASS: failure отличается от unavailable; базовый Report сохранён; повтор key возвращает тот же Report |
| R11.1-09 | PASS: реальная PostgreSQL, Report 1→старый 2→новый 3; checksum Results и IA неизменны; старый C67 в БД побайтно по JSON сохранён, при выдаче скрыт |
| R11.1-10 | PASS в адресной области: реальный HTTP router, PostgreSQL, JSON/PDF владельцу 200, чужому 403; UI loadM8Report на том же сохранённом JSON; раскрыто основание; 3 страницы PDF просмотрены, кириллица и длинный текст не обрезаны |

Команды (exit 0, если не указано иначе):

- `npm run test:backend` — 333 passed, 107 deselected, финальный запуск.
- `TEST_DATABASE_URL=postgresql://127.0.0.1:55491/task11_pytest npm run test:backend:integration`
  — эквивалентный прямой pytest: 74 passed, 366 deselected. PostgreSQL 15,
  отдельный временный cluster `/tmp/r11-pg`; не developer/test-сервер с рабочими данными.
- После последнего усиления same-AS проверки и неизменности IA повторён
  `TEST_DATABASE_URL=postgresql://127.0.0.1:55491/task11_pytest .venv/bin/python -m pytest --run-integration -m integration tests/integration/test_m8_recommendation_basis_db.py -q`
  — 6 passed. Остальной код полного DB-прогона не менялся.
- `npm run test:backend:http` — 29 passed.
- `.venv/bin/python -m pytest tests/unit/test_m8_recommendations.py tests/unit/test_m8_results.py -q` — 20 passed.
- `npm run lint:js`; `node --test tests/frontend/*.test.mjs` — 3 passed;
  `npm run build:web`; `git diff --check` — PASS.
- Проверка пакетов: загрузчики сверяют manifest/checksum, unit и DB используют новые версии.
- PDF: настоящий owner HTTP → Typst 0.14.2 → `pdfinfo`/Poppler → визуальный просмотр страниц 1–3.
- Адресный browser: синтетический HTTP-ответ в действующем `loadM8Report`, отдельная
  локальная HTML-обвязка. Это проверка отображения компонента, не полная product/browser acceptance.
- Реальные LLM — NOT_RUN, механизм детерминированный, тестовые шлюзы синтетические.
- CI frontend/pytest — NOT_RUN локально; обязателен для PR перед merge. Deploy не выполнялся.

## Реализация и происхождение

| Источник / правило | Контракт и реализация | Проверка |
| --- | --- | --- |
| M1 v1.4 + Change 01: источник, версии, границы ответственности | PM-05/C56 не меняется; PM-06 проверяет сохранённый материал; PM-07 представляет C67 | R03, R09 |
| M6 v1.8 §§6–7: IA и допустимость интерпретации | `Api/m8_recommendation_basis.py`: immutable C56 → IA revision → assessment → Evidence → материал; hash, Cycle/AS, точные ссылки. `m8_recommendations._candidate`: отдельный interpreted admission | R01–05 |
| M8 v1.2 §§6–6.1: типы зависят от основания | `Api/m8_recommendations.py`, внешний пакет v1_1: admissibility до выбора, нет общего fallback, содержательные function/product/rationale | R02, R04, R06 |
| M4 v1.0, snapshot PersonalizedProfile | существующий Results snapshot + allowlist контекста; контакты не берутся для рекомендации | R07 |
| M8: историчность и представление | `Api/m8_results.py`: новая Report revision; pure legacy projection на GET, revalidation текущей цепочки; UI и PDF получают один C67 | R08–10 |

Выбранные источники/хеши — `docs/methodology/source-sets/2026-10-01/manifest.json`;
M8 SHA256 `a61909c996f66e88668c4cf713fb91129f3ab778ed843d0e796c7d4e226b73fa`.
Дополнительно прочитаны `docs/architecture/product-4k/m1/v1.4/README.md`,
`docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`,
`docs/adr/002-cycle-as-dialogue-contracts.md` и существующие потребители/тесты C56/C67.
В доступных файлах задание 11 имеет редакцию 1; требуемая редакция 2 не обнаружена.
Задание 11.1 и действующие версии источников являются границами этого исправления.

Новые версии в существующем файловом контуре (статус draft сохранён, утверждение не присвоено):

| Пакет | SHA256 содержимого | SHA256 manifest |
| --- | --- | --- |
| recommendations/m8/v1_1, 1.1.0 | `60a5a6bb9aca152f9a8e1efe31efe8a1afc7ecc9f6860f9264f6b9e1ab34d9da` | `5f3047e4cb6b44633fcc1ce94e1a2622cdb6b3a8d5db50e74d60bc77b01340c7` |
| reports/m8_basic_report/v1_2, 1.2.0 | `3242ad6a95ce5b8d6457b2732a6b71b650b377e190aa7dddd737f8f1b66f4e54` | `0c9451b0bdf1cb7c32ebb68ede07a0c552ea0667e0f5b15aca030ff0ee7f1c99` |

Старые пакеты v1/v1_1 отчёта не редактировались. Схема БД и публичные маршруты не менялись.
Генерация детерминированная; сохраняются входы, hashes, resolved projection, механизм,
результирующий текст и причины исключения. Участник видит пояснения, не reason codes.

Consolidation/Transfer имеют консервативное покрытие: два действия K1.I01 и K1.I13
из положительных частей дескрипторов M2 v1.1. Точное действие должно совпасть
в confirmed_features, descriptor_basis, сохранённом descriptor и разрешённом Evidence-ref
с фрагментом. Сам уровень не выбирает тип. Для иных обоснованных IA возможен
Development; свободный текст не классифицируется как положительное действие.
Расширение каталога требует предметного просмотра, это осознанная граница, а не
утверждение о полной поддержке всех положительных проявлений M2.

## История, безопасность, ограничения

Все непроверяемые legacy recommendations предыдущего контракта скрываются целиком,
с пояснением необходимости обновить представление. Это консервативно может скрыть
и старую корректную рекомендацию. Сохранённый C67 не UPDATE-ится; GET не вызывает
generate, новую IA или расчёт. Явная регенерация создаёт новую Report revision.
Текущий блок дополнительно сверяется с сохранённой цепочкой при чтении; ошибка
скрывает только рекомендации и не выдаёт их как ready. Основной Report остаётся доступен.
Массовая обработка реальных данных не проводилась.

Откат: сохранить фильтр legacy и отключить выдачу рекомендаций при сохранении
Results/Report/history; не возвращать прежний небезопасный генератор. Перед
применением на test — PR CI и решение владельца; merge автоматически разворачивает test.

Ревью: затронуты только M8 generator/resolver, Report loader/presentation, UI/PDF,
новые пакеты, регрессии и пересобранный web/dist. Старые нормы/управляющие документы
не менялись. Источник admission M6 не дорабатывается: 8.1 должна уточнить его
содержательность; IE при отсутствии явного разрешения на отдельный факт исключён.
Качественные результаты пропускаются при явном интерпретационном допуске независимо
от numeric_admissible. Предлагаемая практика не становится новым Evidence.

## Сохранённые примеры и передача

Все данные синтетические, не GC и не реальные сведения участника.
В `docs/evc/tasks/artifacts/task11-1/`:

- `positive.json` — допустимый блок, три обоснованных варианта;
- `empty.json` — отсутствие основания;
- `mixed.json` — только Development, IE того же Skill исключён;
- `failure.json` — технический сбой и доступный базовый Report;
- `http-report.json`, `report.pdf` — одно представление, фактически выданное owner HTTP.

JSON содержит воспроизводимые generator input и цепочку refs/checksums до материала.
Повторное получение примеров: добавить `R11_ARTIFACT_DIR=/tmp/r11-artifacts` к
адресной DB-команде. UUID нового запуска могут отличаться, текст при одинаковом
сохранённом входе детерминированный.

Техническая готовность 11.1: локальные обязательные проверки пройдены.
T11-10/S10-A/B/C: NOT_RUN, отдельная задача 10.3. Экспертный просмотр шаблонов:
не выполнен. GC: не утверждён. Reliability: not_verified. Baseline не присвоен.
