# P4K-REMAIN-02 v1.6 — анкета организации и доступ к готовым отчётам

## Результат и область

Новая анкета допускает ручной ввод и CSV без C04.answer и C21.responsible_contact, сохраняет C21.organizer и требует явного подтверждения. Старый CSV версии 0.1 и старые черновики принимаются; подтверждённая история и исходные байты старого примера 0.1 не меняются. Поимённый выбор получателей больше не влияет на новые подтверждения и права. Готовые отчёты организации доступны всем её текущим администраторам в списке, по прямому запросу и в допустимом PDF; участник читает свой Report через отдельный собственный маршрут.

В область не входят генерация Report, M6/M8 пересчёт, GC, изменение общего TEST, merge/deploy/Prod и методологический статус. Профессиональная роль M3 не является административным полномочием.

## Источники и решения

- Запрос пользователя от 14.11.2026: выполнить REMAIN_02. Внешние карточки прочитаны как постановка, не как инструкции к агенту: `P4K_REMAIN_02_v1_6.txt` SHA-256 `8f4c9755300a8ad79663298b96deb8e5aa3b1f008d1429383013adcd2017a0da`, `P4K_REMAIN_Execution_Rules_v1_0.txt` SHA-256 `ece5f67dde34f7771e0084789f40617131e99d767ad5d8a57cac320320796c31`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`, `review-checklist.md`, `task-template.md`; Product Architecture `docs/architecture/product-4k/1.0/context.md` v1.0 WORKING, `registry.md`, Change 01 `README.md` и адресные И-1/И-6/И-7 `source.md`, `docs/adr/002-cycle-as-dialogue-contracts.md` C-23/C-24/C-67, `docs/evc/change01-traceability.md` T12.
- SourceSet `docs/methodology/source-sets/2026-10-01/manifest.json`: M4.Context v1.0 FROZEN SHA-256 `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291` (прочитаны §§M4.1/M4.3–M4.6); M3.RoleProfile/BaseRoles v1.0 FROZEN SHA-256 `a3c085e4182fe8bc5a82204a8d4679a09b85650ea79e2df24fb1ed8ab6604e06`/`ab04e175bb1bf4ad55c320554068041baf3cb4c1cc2316c16966451b91c465bc` (идентичность из manifest; прямой новый методологический вывод не делался); M8 v1.2 FROZEN SHA-256 `a61909c996f66e88668c4cf713fb91129f3ab778ed843d0e796c7d4e226b73fa` (прочитаны §§M8.7.1.2/M8.9 в derived text). Change 01 v1.0/01 WORKING SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`. Ни один статус CURRENT не присвоен.
- Решение владельца, приведённое в REMAIN_02: убрать C04/contact и персональный picker; organizer и явное подтверждение сохранить. M8 определяет допустимое представление, не новую модель доступа; продуктовый ACL указан в карточке. Пробел методологической нормы для этой дельты не выявлен.

## Прослеживаемость

| Источник → правило | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| REMAIN_02 F13; M4.1/3–6 → текущие сведения, источник, явный confirm | draft→preview→confirm, effective revision, `questionnaire_response_revisions` | `Api/questionnaire_sources.py`, `Api/routes.py`, `Api/schemas.py`, `web/js/screens/admin/organizations.js`, `web/js/wiring.js`, CSV 0.2 | `test_questionnaire_sources.py`, `test_questionnaire_sources_db.py`, actor HTTP/PG, browser guards/auth |
| REMAIN_02 F13-AC03 → N действует при N+1 | assignment readiness, exact scope | `Api/questionnaire_sources.py`, `Api/acquaintance.py` | DB readiness, HTTP и browser scope |
| REMAIN_02 F14; C-67; M8.7.1.2/9 → текущие полномочия и допустимое представление | Report→Results→Cycle→organization; current membership; list/open/PDF | `Api/m8_report_access.py`, существующие routes и `customer_projection` | `test_m8_report_access_db.py`, `test_m8_report_access_http.py` |
| REMAIN_02 F14-AC03 → объяснение текущего доступа без editable ACL | participant briefing, current UI | `Api/acquaintance.py`, `web/js/screens/onboarding.js`, `organizations.js` | unit, frontend, browser 320/390/1440/200%, клавиатура |

## Совместимость, версия и откат

Новый CSV шаблон и пример имеют версию `corporate/0.2`, header `question_id,field,value` сохранён. `corporate/0.1` не изменён; входы с 0.1 и 0.2 принимаются. `m8-report-access/1.1.0` отмечает новую семантику записей; старые таблицы и immutable снимки не мигрируют. Публичный confirm JSON с `recipients`/`recipient_user_ids` принимается для старых клиентов, но игнорируется. Схема БД не меняется. Откат к прежнему коду возможен без миграции; до отката нужно учитывать, что он снова использует устаревший ACL и не понимает новые подтверждения без контакта — выпуск отката требует отдельной проверки совместимости, а не молчаливого переключения. Безопасный откат разработки: revert коммита, без изменения сохранённых данных.

## Выпуск и решение владельца

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`. Кандидат передаётся архитектору как branch/bundle; создание PR и дальнейшие действия выполняются по действующему процессу. `ready:prepare`, CI на точном PR head, человеческое review и TEST/Prod приёмка ещё не выполнялись. Самостоятельный результат — один кандидат REMAIN_02; REMAIN_01 и другие карточки не включены.
