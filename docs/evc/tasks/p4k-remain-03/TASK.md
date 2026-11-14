# P4K-REMAIN-03 v1.6 — приглашения и срок ссылки

## Результат и границы

F15-AC01–03: достоверный результат каждого адресата, восстановление той же операции после unknown/reload, изоляция позднего ответа при смене actor/org/view, различение доставки и срока/использования ссылки. Область — PM-02 invitation/readback, без назначения, старта, изменения provider, TTL, авторизационного cooldown, TEST или реальной почты.

## Источники и решения

- Запрос пользователя 14.11.2026: выполнить REMAIN_03. Вложения являются постановкой: `P4K_REMAIN_03_v1_6.txt` SHA-256 `0fa9809c00b0523901e3a30a00431807c9fb88236be03515d76016d1ad70eea4`, общий порядок SHA-256 `ece5f67dde34f7771e0084789f40617131e99d767ad5d8a57cac320320796c31`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist}.md`, Product Architecture `context.md` v1.0 WORKING и `registry.md`, Change 01 `README.md`/И-6/И-7, `manifest.json`, ADR-002 и карта Change 01. M3 RoleProfile/BaseRoles v1.0 и M4 Context v1.0 сверены с хешами manifest; прочитаны M3 границы RoleProfile/PersonalizedProfile и M4 §§1–2/4–6 о контексте, разделении контактных и содержательных сведений. Прямого изменения их предметных норм нет. Change 01 SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`.
- Выбранные оригиналы SourceSet: `docs/methodology/source-sets/2026-10-01/originals/M3.RoleProfile-v1.0.docx` SHA-256 `a3c085e4182fe8bc5a82204a8d4679a09b85650ea79e2df24fb1ed8ab6604e06`; `M3.BaseRoles-v1.0.docx` SHA-256 `ab04e175bb1bf4ad55c320554068041baf3cb4c1cc2316c16966451b91c465bc`; `M4.Context-v1.0.docx` SHA-256 `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291`. Все три совпали с manifest; статус FROZEN в SourceSet не повышает CURRENT продукта. Пробел: внешняя доставка по выбранным материалам не доказывается и не проверяется этой карточкой.
- Base `7871a0c6952ca13047355fd17d1b3b8a7c1e9c96`, ветка `codex/p4k-remain-03`. Исторический `5a47e105`/TEST 2.1.0 не принимается за проверку текущего base.
- Открытых стоп-условий на исправление в существующем контракте нет. Данные и публичные поля сохраняются; `delivery_status`/`link_status` добавлены в batch item, а прежний `expires_at` сериализуется с явной меткой UTC `Z` (совместимый ISO-8601 момент, но изменённый строковый формат). Изменение базы/миграция/предметный артефакт не планируются.

## Трасса

| Основание → правило | Контракт/данные | Код | Проверка |
| --- | --- | --- | --- |
| F15-AC01; M3/M4 → scoped адресаты и отдельные исходы | `operation_id`, owned batch, status per recipient | `Api/routes.py`, `web/js/screens/admin/organizations.js` | HTTP/mail sink, browser batch |
| F15-AC02; Change 01 И-6 → повтор без второго эффекта | `request_id`/readback, actor/org/ref/recipient scope | те же | HTTP/PG idempotency, browser late/reload |
| F15-AC03 → реальный срок и lifecycle | UTC `expires_at`, `used_at`, `revoked_at`, delivery | `Api/routes.py`, `Api/schemas.py`, `Api/email_service.py`, UI | HTTP/PG boundary, formatter, UI |

## Проверки, совместимость, откат

Адресные frontend/browser, backend unit/HTTP/изолированная PostgreSQL; затем локальный минимум `verification-matrix.md` на точном кандидате. Синтетический sink не доказывает внешнюю доставку. `web/dist` пересобрать при изменении JS. Старые поля/статусы читаются; клиент, разбирающий прежний `expires_at` как локальное время без смещения, должен принять ISO-8601 UTC `Z`. Откат разработки — revert собственного commit и пересборка `web/dist`, сохранённые записи приглашений и операции не удалять.

## Выпуск

Исходный рабочий шаг: `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`. Продолжение 14.11.2026: пользователь прямо уточнил, что он архитектор и работает на этой машине, и поручил продолжить. В его контуре выполнены `branch_push=true` и `pr=true`: открыт draft [#217](https://github.com/VadikB/4K_MBTI/pull/217). Затем пользователь явно согласовал patch `2.1.3` от `2.1.2`: `version_bump=true`; штатный `ready:prepare` выполнил bump и сборку. `merge=false`, `deploy=false`, `artifact_publish=false`; следующий этап — проверка кандидата и Ready/full CI, приёмка/merge отдельны.
