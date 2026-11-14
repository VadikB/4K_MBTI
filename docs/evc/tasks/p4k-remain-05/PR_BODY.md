# REMAIN_05: понятные ошибки знакомства и восстановление первого старта

После AbortError, deadline или пустого/повреждённого201 клиент терял pending первого старта и мог показать непроверенное состояние. Теперь ключ сохраняется до POST, ответ проверяется, неопределённый исход восстанавливается только через owned runtime того же Cycle. Заголовки и тело ограничены существующим deadline helper. Известные причины отказа сохраняются; технические ошибки/UUID получают понятное объяснение и отдельный код обращения, введённые ответы и шаг остаются на странице.

F27 проверен через existing controlled tester/challenger/queue и настоящую изолированную PostgreSQL/HTTP; runtime admission, prompts, snapshots и политика retry не меняются. Test harness получил optional остановку на первой AS, чтобы проверки не создавали оценочных ответов/Next/Report.

Локально PASS: frontend303, protocol65, PostgreSQL/HTTP23, browser8, lint/build/diff. Base a1cdfedfb8b71d150b078eb0380ea013f0b08965; code candidate1b1c18f74474e011278b9b8d1644a0e3d94de0cb. Серверные65/23 reused сd1326a3e по byte-identical области. Первичные результаты, сохранённые harness FAIL и границы synthetic доказательств — CHECKS.md; sources/полномочия/rollback/resources — TASK.md и STATE.md.

Без миграции/конфига/предметных артефактов; откат собственных code commits с dist, данные не менять. CI, человеческое review, TEST/deploy, real LLM/mail NOT_RUN. Исторический fd…/PREP-DIAG UNKNOWN. Версия приложения и PR этим локальным handoff не назначаются; публикация архитектором после сверки main и допуска.
