# M8 Task 11 — Recommendations на подтверждённых основаниях

## Результат и границы

На базе `ec0dbc887c89725e4f41b6037f8f0a05a8d4a404` добавлен индивидуальный
блок Recommendations в сохранённый C-67. Фактические IA, Scores, Skill Results,
Gap и Results revisions не меняются. Group Report, программа обучения и тренажёр
не входят в изменение.

## Прочитанные источники и CHECK M4

- M8 v1.2 FROZEN, разделы 6, 6.1, 7.5, 8, 9; DOCX SHA-256
  `a61909c996f66e88668c4cf713fb91129f3ab778ed843d0e796c7d4e226b73fa`;
- M4 v1.0 FROZEN, разделы 4.3–4.6, транскрипция SHA-256
  `9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1`;
- PersonalizedProfile schema SHA-256
  `8caef8c3f39a08ae4add2037ad1e6ab27d996ff26430dfb17746b24b92bd0276`;
- Change 01, manifest 2026-10-01, ADR-002, M8 Task 09 и Task 10.

Решение CHECK M4: M8 v1.2 уже разрешает релевантную содержательную часть
зафиксированного PersonalizedProfile, а M4.4–M4.6 разделяют содержательный контекст
и идентификацию. Генератор читает только allowlist полей OrganizationContext,
RoleProfile и UserContext из snapshot данного Cycle. ФИО, контакты, email и телефон
не передаются. Текущие изменённые источники профиля не читаются. Отсутствующий
контекст не достраивается; используется нейтральное описание условий Cycle.

## Контракт и хранение

`m8_recommendations/1.0.0` — versioned deterministic template package. В каждом
сохранённом C-67 находятся версия контракта, механизм и checksum шаблона, точный
минимизированный input и его checksum, сформированный текст, статус и причина сбоя.
Recommendation содержит SkillID, один из трёх типов, IA/assessment/evidence/AS refs,
ComponentID/IndicatorID, цель, практику, контекст, наблюдаемый признак и ограничения.

`m8_basic_report/1.1.0` показывает один C-67 на экране и в PDF. Явная регенерация
`POST /users/assessment/m8/cycles/{cycle_id}/reports/regenerate` создаёт новую
Report revision; scoped idempotency не создаёт дубль. Ошибка генерации сохраняет
базовый Report с честным `GENERATION_FAILURE` и пустым блоком.

## Проверки T11

| Проверка | Статус | Доказательство / ограничение |
|---|---|---|
| T11-01 | PASS unit | чужой Skill и неразрешимая IA ref отклоняются |
| T11-02 | PASS unit | full, partial, result_without_score и no_result разделены |
| T11-03 | PASS unit | Score 2,4 + L2 остаётся `NOT_COMPARABLE`, Gap не выводится |
| T11-04 | PASS unit | отсутствующий Indicator частного состава не попадает в текст |
| T11-05 | PASS unit | три типа содержат основание, практику, контекст и признак; устойчивость не заявляется |
| T11-06 | PASS contract/unit | immutable Report revisions, scoped key, Results не меняется |
| T11-07 | PASS unit/source review | snapshot + allowlist, CHECK M4 зафиксирован выше |
| T11-08 | PASS unit/HTTP | owner scope, минимизация, Dialogue не передаётся, graceful failure |
| T11-09 | PASS code/visual PDF | UI/PDF используют один C-67; A4 Unicode PDF 42 844 bytes, кириллица и длинный текст без обрезки/наложений |

Автоматические проверки не являются методологической приёмкой содержания шаблонов.
Экспертный просмотр примеров остаётся отдельным решением владельца смысла. AI не
используется, поэтому реальный provider-вызов неприменим. PostgreSQL integration
NOT_RUN: локальный сервер `127.0.0.1:55487` недоступен (`Connection refused`).

Фактические команды: backend без integration/e2e/llm — 325 PASS; HTTP e2e —
29 PASS; `py_compile`, `node --check`, `npm run lint:js`, `npm run build:web`,
проверки checksum обоих пакетов и `git diff --check` — PASS. PDF отрендерен
Typst и проверен через Poppler PNG. CI до push/PR — NOT_RUN.

## Откат

Откат выключает endpoint регенерации и создание новых Report v1.1, возвращая новым
запускам шаблон v1.0. Существующие immutable C-67 v1.1 и Results сохраняются и
остаются читаемыми; таблицы и фактические оценки не удаляются.
