# ARCH-A04 — неизменяемый execution manifest Cycle

## Результат и область

Новый Cycle сохраняет версионированный manifest фактически выбранных пакетов M2–M8,
SourceSet, Case/runtime, prompts/protocol, provider contract и runtime refs. Повторное
исполнение разрешает только сохранённые пути и checksum; `latest/current` не участвуют.

Включено: контракт manifest, сохранение при создании Cycle, строгий resolver,
совместимость схемы и регрессия V1/V2. Не входит: смысловая проверка M8 (A07), изменение
методологии, перезапись исторических Cycle/FROZEN и гарантия воспроизводимости плавающего
provider alias.

## Источники и решения

- Base: `main@f2ad4dfa5e95b8c6ea6e3831dc43bb1a94ac10e1`, приложение `2.0.20`.
- Пакет `P4K_Case_AS_Cycle_Plan_2026-10-23`, редакция 2.0: `00`, `01`, `02`, карточка `06`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, обязательные EVC/architecture документы,
  Change 01, source-set manifest и ADR-002.
- Решение владельца: пройти согласованный список; A04 и A07 — отдельные результаты.
- Стоп-условий нет: публичный API и предметные правила не меняются; миграция additive.

## Критерии и проверки

- [x] Manifest и его checksum сохраняются атомарно с новым Cycle.
- [x] V1 продолжает разрешаться после публикации V2; новый Cycle использует V2.
- [x] Изменение bytes под тем же ref и удаление публикации дают явную ошибку.
- [x] Версия приложения отделена от версий методологии/publication.
- [x] Исторические строки не переписываются и не получают молчаливый fallback.
- [x] Unit, PostgreSQL integration, backend/HTTP минимум и `git diff --check` проходят.

## Риски и откат

Схема получает nullable additive columns для исторической совместимости; отсутствие
manifest у legacy Cycle остаётся явным состоянием, а не выводится из текущих файлов.
Revert кода возвращает прежний resolver; колонки безопасно остаются неиспользуемыми.

## Состояние

- Завершено: manifest/resolver, frozen M5/M6/M8 consumers, prompt package, release `2.0.21`.
- Проверки: backend 556 PASS; HTTP 68 PASS; integration 151 PASS, 1 real-provider SKIP
  (145+1 SKIP в общем прогоне и 6 stand PASS повторно с корректным `STAND_ADMIN_URL`);
  unit 542 PASS; build/lint PASS. Browser: 48 PASS, 14 stand cases NOT_RUN из-за
  сбоя локального Node `spawnSync` (`stdout/stderr=null`); изменение UI отсутствует.
- Активный шаг: финальное ревью, commit и PR.
- Ветка: `codex/arch-a04-cycle-manifest`.
- Следующий шаг: проверки, отчёт, PR; затем отдельная A07.
