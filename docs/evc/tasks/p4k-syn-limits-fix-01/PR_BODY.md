Синтетический driver мог бесконечно отвечать на ASK внутри одной AS, повторный вход
в strict JSON adapter получал новый transport-бюджет, а cleanup оставлял потомка.

Добавлены конечные run/AS step budgets и отдельные deadline/no-progress причины;
общий остаток и исходный deadline сохраняются в контексте gateway. Runner регистрирует
свою process group, останавливает её с конечным grace period и сверяет регистрацию
после аварийного выхода. Controlled-профиль запрещает native provider до отправки.
Существующие export/readback/cleanup gates подтверждены регрессиями.

Задача и AC01–AC06: [TASK](docs/evc/tasks/p4k-syn-limits-fix-01/TASK.md),
[CHECKS](docs/evc/tasks/p4k-syn-limits-fix-01/CHECKS.md).
Исходный аудит сохранён отдельно без перезаписи результатов.

Проверки code candidate926f1633: backend1112, frontend331, HTTP153 (переиспользование
неизменённой области), lint/build/diff PASS. Реальных LLM/mail0; сеть и рабочие .env
блокировались независимым guard. Сверено28 своих групп, оставшихся PID/PGID нет.
Полный PATH/Report/GC и платные вызовы не выполнялись.

Пределы: бюджет in-memory в том же gateway, не durable queue/restart или tokens/cost.
Проверена POSIX process group после регистрации, не произвольный setsid.
AC06 readback относится к настоящему файлу test state и destroy spy, не PostgreSQL.
Нормы участника/Cycle, admission, расчёты и public HTTP API не менялись.

Версия пока2.1.7; PATCH2.1.8 требует решения владельца. До Ready — штатный
ready:prepare и обязательный CI точного head. Merge/deploy не разрешены.
Откат — revert926f1633 с сохранением diagnostic evidence.
