# P4K_AUTH_FIX_01 — локальное исправление авторизации

## Результат и границы

AUTH-V01: белая оболочка авторизации и восстановления сессии, самостоятельная
шапка с актуальным frontend release, правовой footer без дублирования версии.
Сохранить AUTH01/03 474×474 и принятую двухшаговую AUTH02 502×547.
AUTH-F01: снимать устаревшую email-ошибку на input, восстанавливать «Продолжить»
после отказа password-login. INT-01: проверить точный кандидат со свежим main.

Не входят API/права/парольная политика/БД/PM и LU/методология/оценивание.
Все флаги branch_push/pr/merge/deploy/version_bump/artifact_publish/real_email/real_llm=false.
Локальные изменения и синтетические проверки следуют запросу владельца начать с
00_START_HERE пакета редакции1.1 от05.11.2026. Выпуск требует отдельного решения.

## Источники и разведка

- Входной пакет хранится вне репозитория, все 25 SHA256SUMS проверены PASS.
- Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/matrix/template/review/artifact-recipe,
  tests/README и package.json; архитектура1.0/Registry/Change01 И-1/И-6/И-7,
  SourceSet manifest, M1v1.4 FROZEN/CURRENT=NO, приложенный M4v1.0.
- UI: оригинальные PNG Кати1440×1024, SOURCE_PRIORITY и R01/Review12.10,
  UX_UI_Katya.pdf стр1–10, ui-visual-spec/baseline17.10, UX-AUD29/UX-UI01.
- Адресные решения05.11 из пакета имеют приоритет для AUTH: белый #FFFFFF,
  релиз в шапке, без видимой email-метки. Остальные семейства baseline сохраняются.
- Архитектурный адрес: UI/общая оболочка авторизации. LU=Local Unit. Вход не
  начинает Cycle/AS/таймер, предметные определения и snapshots не меняются.
- Аудит и свежая implementation base: e63eba67d77fb73f7fb9bb219bc3fe5d3807a909 /2.0.66.
- Исходная копия /Users/dmitriyzemlyanov/Documents/Соответсвие продукта методологии/4K_MBTI_dev
  чистая, HEAD3385145201d5d365e08e9e8a6a6fb7e12a0aa258 сохранён.
- Собственная worktree /private/tmp/p4k-auth-fix-01-20261105, ветка codex/p4k-auth-fix-01.
- Пробелы/новые продуктовые конфликты: не выявлены. Все восемь стоп-условий EVC — нет:
  смысл/контракт/БД/артефакты/чувствительные данные/выпуск/откат/scope не расширяются.

## План и состояние

1. Разведка и baseline: выполнено; снимки/raw JSON1440×1024,DPR1,Onest.
2. AUTH-V01/AUTH-F01: реализовано; 7 новых F01 и13 V01 browser-регрессий.
3. Итоговые команды, exact SHA/tree, INT-01 и24AC/23TC фиксируются во внешнем
   `outputs/p4k-auth-fix-01/06_RESULT.json` и `REPORT.md` рядом с входным архивом.

## Полномочия и среда

Darwin24.6.0 arm64. Requested: workspace-write/on-request/auto_review,
ограниченная сеть. Effective: workspace-write и restricted network; on-request
поддерживается инструментом; reviewer UNKNOWN (клиент не сообщает).
Глобальные настройки/AGENTS/CI не менялись. Node22/Python3.12/node_modules/.venv и
Chromium переиспользуются из установленной среды через локальные symlink.
Файлы .env не читаются/не копируются, developer DB не используется.
Git worktree add и localhost browser потребовали штатного системного разрешения,
которое получено; отказов automatic reviewer нет. EPERM песочницы не является отказом reviewer.

| Операция | Ресурс/доступ | Основание и проверка |
|---|---|---|
| Чтение/реализация | пакет и собственная worktree | запрос/пакет, status/diff |
| fetch/ветка/локальный commit | Git refs origin/main/own branch | отдельная worktree, штатный escalation |
| Сборка | собственный web/dist | исходная копия не затрагивается |
| UI/browser | static127.0.0.1, API route mocks | никаких внешних API |
| Backend/HTTP | тестовый процесс без .env/DB/credentials | unit+mock HTTP |
| Снимки/отчёт | outputs/p4k-auth-fix-01 вне репозитория | SHA/AC/TC/команды |
| Push/PR/merge/deploy/bump/publish/mail/LLM | внешний контур | запрещено, не выполняется |

## Проверки и откат

Локальный минимум: diff --check, lint:js, frontend suite, build:web,
auth/footer/browser (включая обе ошибки до/после), backend и HTTP.
Browser: original/before/after без resize, bbox/computedStyle; widths320/360/390/430/
768/1024/1440, low480/text200%; реальные Safari/mobile отдельно NOT_RUN.
Integration DB не применима: сервер/БД не меняются, HTTP контракт проверяется с mocks.
CI не выполняется без публикации. Ready/version bump не выполняется; будущая
подготовка — ready:prepare с отдельно разрешённым номером, frontend/pytest/full-verification,
review; merge в main автоматически запускает deploy-test и требует прямого допуска.
Откат: отменить только собственные коммиты/патч в своей ветке; данные не затронуты.
Итоговые SHA/команды/evidence хранятся во внешнем result JSON; пакет/reference/resources
не копируются в Git. Текущее состояние — `docs/evc/tasks/p4k-auth-fix-01/STATE.md`.

## Выявленные ограничения

До исправления browser воспроизвёл stale email-error и CTA «Войти» после401/abort.
После исправления7/7 новых F01 тестов PASS. Визуальные проверки дополнительно нашли
существующие AUTH03height495.89, long-email overflow416px на320 и overflow340px
при200% текста. Исправлены переносы/минимальные размеры grid и интервалы AUTH03;
11/11 V01 visual cases прошли, TC14 генератора проверяется итоговым кандидатом.

Существующий `R03 successful password response reports a missing browser session as
auth failure` падает также на неизменённом e63eba6. При journey401 поздний resetChat
стирает уже показанную ошибку восстановления сессии. Это отдельная прежняя гонка;
AUTH-F01 ограничен двумя поставленными дефектами, она не исправляется попутно.
При сохранении этого FAIL итог — LOCAL_CHECKS_BLOCKED, без заявления LOCAL_VERIFIED.
Последующие фиксы/выпуск требуют отдельного определения области владельцем.

Независимое review исправило границу исключения ui03: #CBD5E1 допускается только
в полном селекторе `.auth-panel.auth-panel input`, а не в списке с `body`.
Общая палитра/token/управляющие документы не меняются.
