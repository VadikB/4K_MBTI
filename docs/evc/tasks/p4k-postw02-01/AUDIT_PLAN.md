# Детальная сверка по прямому запросу владельца

16.11.2026. Публикация запрещена: push/PR/merge/deploy=false.
Проверяемый продукт: e1b07b359d209561585f39ffadceea381eb5351d, без исправления
runtime в ходе аудита. Ранее заявленное визуальное соответствие не подтверждено.

Источник: rev1.1 P4K_POSTW02_01_Cabinet + REFERENCE_CURRENT; точный Site v10
e44fa78efb1ec8605b28cf9bc2c2272da2b9122a. Исходник получен штатным Sites
open-source workflow, без archive/push/publish. Чтение локального исходника теперь
доступно; прежняя причина NOT_RUN была ошибочной и подлежит явному исправлению.

Сверка: исходники renderHistory/report-cabinet.css/report.css/ui-theme.css;
неизменённый локальный рендер пяти сцен на 1440×1000 и 390×844. Продукт получает
синтетический HTTP payload с теми же названиями/организацией/датами demo только
в тесте; тексты состояний взяты из реального Api/routes.py/participant_dashboard.py.
Дополнительно длинное синтетическое название на обеих ширинах; в эталоне меняется
только DOM-текст названия, исходник и CSS остаются неизменными. 320px — только
overflow. Снимки normal сохраняют исходный reference DOM без нормализации.

Профиль audit-v10: один runner, worker=1, retries=0, whole=180s/test=60s/idle=60s,
локальный ephemeral HTTP server, все /users HTTP подменены; DB/LLM/mail=0.
Owned process teardown TERM/grace1s/KILL, server afterAll.close. Существующие
backend/frontend наборы не повторяются: продукт не меняется. Новая проверка
собирает факты, не объявляет FAIL проверки запуска отсутствием расхождений.
Успешный runner означает пригодность evidence; результат соответствия отдельный.

Итог: source SHA/checksums, парные снимки, computed styles/geometry/copy, таблица
подтверждённых расхождений и допустимых отличий продукта от demo. Защищённый live
URL/Prod/полный PATH не проверяются. Прежняя ручная visual review не считается
точной сверкой. Исправления продукта в этот audit не смешиваются.
