# P4K_AUTH_FIX_01 — локальное завершение 07.11.2026

## Результат и область

Продолжить сохранённый AUTH-кандидат, включить свежий main, подтвердить устранение
B-01 и выполнить обязательный локальный минимум. Прямое основание — запрос владельца
и поручение `P4K_AUTH_FIX_01_Completion_2026-11-07.txt`, редакция1.0.
Исторический срез05.11 `f78cb4a66fdef796ab08824984e1890c8018fd1c` не переписывается.

Разрешены собственная ветка, локальная интеграция, synthetic проверки и коммиты.
Push/публикация PR/merge в main/deploy/bump/предметные публикации/реальная почта/LLM
запрещены. Серверные API/БД/схема/методология/admission/AGENTS не меняются.
Архитектурный адрес — UI авторизации; LU=Local Unit, Component=компонент навыка.

## Сохранность

Darwin24.6.0 arm64; собственная worktree `/private/tmp/p4k-auth-fix-01-20261105`,
ветка `codex/p4k-auth-fix-01`. При старте HEAD/tree точно совпали с05.11,
рабочее дерево чистое. Исходная пользовательская копия/ветки не изменяются.

Постоянная папка в исходном проектном workspace:
`outputs/p4k-auth-fix-01-completion-20261107/backup/`.
`auth-before.bundle` содержит свою ветку f78cb4a и полную историю, bundle verify PASS.
50 прежних evidence-файлов скопированы и побайтово SHA256-сверены; receipt/manifest
в той же папке. Старый отчёт, первичный ZIP, worktree не перемещались/не удалялись.
.env/cookies/браузерные профили в evidence-копию не включались.

## Источники и решения

- Исходный AUTH пакет1.1: 01_TASK/SOURCE_PRIORITY/02AC/03TC/05TRACEABILITY,
  оригинальные PNG1440×1024 и принятые адресные исключения05.11; прежние STATE/result.
- Fresh main `65c1f4c04466b60d4c6ce4611346fc92c617ed74`, релиз2.0.75;
  заново прочитаны AGENTS/README/CONTRIBUTING, EVC workflow/matrix/recipe/review,
  registry/context/Change01/SourceSet и относящиеся положения источников.
- Architecture1.0+Change01 WORKING; M1v1.4 FROZEN/CURRENT=NO; вспомогательная сверка
  глоссария30.09 и P4K.DEV.PRINCIPLES1.0. Изменения статуса/предметных норм нет.
- Governing документы/UX-эталон не изменены на main относительно прежнего кандидата.
  Обновлённые README/tests README прочитаны; AC18 readiness — дополнительный
  synthetic регрессионный набор, не разрешение реального PATH/PG/LLM.
- PR174 MERGED: `3f42bba992e1a556e1961ca4abdaa0954a367153`, auth feedback fix.
- PR180 MERGED: `65c1f4c04466b60d4c6ce4611346fc92c617ed74`, token validation readiness.
  Оба merge commits — предки fresh main; squash head ancestry не подменяет это доказательство.
  Read-only PR/check receipts сохранены вне Git; их CI не является CI нашего кандидата.

Содержательных конфликтов/новых продуктовых решений нет. Все8 EVC stop-условий — нет:
смысл/контракты/БД/артефакты/чувствительные данные/развёртывание/откат/scope не расширены.

## Реализация и интеграция

Локальный merge свежего main в свою ветку сохраняет существующую историю.
Конфликт imports в auth-r03 разрешён объединением обоих наборов; generated dist
восстановлен штатной сборкой актуальных sources, без выбора старого bundle.
Все token-pending/validation generation guards изPR180 сохранены вместе с нашими
email input/error ownership и CTA «Продолжить».

Статический header fallback синхронизирован с уже существующим APP_RELEASE2.0.75;
номер приложения не назначался/не повышался. Белая оболочка/геометрия/footer
нашего AUTH сохранены; остальные версии и изменения main не откатываются.

B-01: ALREADY_FIXED на main вPR174. `resetStaleUserState` очищает старый feedback
синхронно до lazy cleanup, `resetChatScreen` передаёт preserveAuthFeedback,
`resetChat` сохраняет новую ошибку; session generation guards действуют.
Дублирующий runtime fix не добавлен. `auth-recovery.spec.mjs` дополнен:

- S-01 delayed/eager: точные synthetic email/password поручения, успешный login→401,
  сообщение сохраняется после реального import+rAF, controls/busy и повторная попытка.
- S-02: валидный journey открывает путь участника без ложной ошибки.
- S-03: старый readiness journey401 отпущен барьером после logout/new login;
  более новая сессия сохранена. Прежние same-tab/cross-tab cleanup guards сохранены.
- S-04: исходные20 AUTH tests и связанные reset/abort/401/503/registration/footer,
  auth readiness/failure capture изPR180 входят в обязательную перепроверку.

## Проверки и передача

Dev-check: frontend147 PASS; AUTH/readiness51 PASS; recovery6 PASS.
Это промежуточные результаты до фиксации итогового commit, не финальная приёмка.
Финальный минимум точного кандидата: diff/lint/frontend/build/backend unit/HTTP,
browser AUTH/recovery/readiness/footer/journey, снимки и bbox1440×1024/DPR1/100%/Onest,
исходная responsive/text200% проверка и финальный fetch+ancestry INT-01.
Backend/HTTP запускаются в sterile env с dotenv disabled, loopback port9 sentinel,
без credentials/рабочей БД; browser — HTTP fixtures и loopback.

Итоговые exact SHA/tree, команды/exit codes, FIN01–08/AC/TC и raw evidence:
`outputs/p4k-auth-fix-01-completion-20261107/` исходного постоянного workspace.
Отчёт05.11 сохранён отдельно с прежним FAIL. AC22/23/24 — исторические узкие
условия запуска, не доказательство устранения14 подтверждений и не gate продукта.
Настройки разрешений не менялись и заново не сертифицируются.

CI кандидата/push/PR/merge/deploy/mail/LLM: NOT_RUN; DB integration — неприменима
к сохранённым UI изменениям. Реальные Safari/mobile keyboards — NOT_RUN,
Chromium эмуляция не выдаётся за физические устройства.
Откат: отмена только своих локальных коммитов; исходный результат восстанавливается
из проверенного bundle, данные не изменены. Последующая публикация требует решения.
