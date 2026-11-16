# Исправление по результатам точной сверки

Основание: прямой ответ владельца «Хорошо, проведи изменения и покажи что получилось»
после REFERENCE_AUDIT A01–A18. Публикация по-прежнему запрещена: push/PR/merge/deploy=false.
Работа в прежнем worktree/ветке, base2afcc379, предыдущий продуктe1b07b3.
Исторические evidence/audit-v10 и REFERENCE_COMPARISON сохраняются без перезаписи.

Источник: task01 rev1.1 + REFERENCE_CURRENT, exact v10e44fa78; renderHistory,
report-cabinet.css/report.css. Новый найденный первичный справочник:
Архитектура/1.0 Доработка Полная/обработка замечаний/путь Отчета/
P4K_REPORT_TASKS_2026-11-15/reference/sources/P4K_UI_Baseline_1.2.txt.
Редакция1.2 заменяет1.1 в области палитры: surface-soft#F7F9FB, footer#68777C.
Поэтому два открытых token observations из аудита закрываются KEEP, без новых
#FAFAFA/#64748B. Прямое более позднее task01 rev1.1 задаёт canvas#F7F7F7 и
контрольные подписи/рамки/кнопку/фокус; они сохраняются. Принятые participant
hover/active109eab/0c8591 уже существуют в shared tokens W02, исправляется их каскад.

1. Renderer: отдельная компактная строка истории в прежнем consumer; метаданные
   текущей карточки по server-owned journey, неизвестный N не выдумывается.
2. UI copy пяти состояний из v10 в существующей server projection; действия и
   маршруты/полномочия/план/данные не меняются. Боковые тексты по renderHistory.
3. Scoped CSS точной композиции: интервалы/типографика/рамки/hover/focus/подвал.
   W02/ADMIN/отчётный renderer не перекрашиваются.
4. Регрессия: затронутые frontend tests, HTTP15 + адресные copy cases с fake storage,
   lint/build/diff; проверка HTML состава DOM, пяти сцен/long/320, точная геометрия
   с allowlist двух цветов/реальной шапки/версии/неподдержанного compare.
   Без повторения неизменённых backend/provenance/full PATH/Prod/real provider.

Browser: один bounded fixture workers1,retries0,whole180/test60/idle60, localhost
эпhemeral HTTP, все /users stubbed; owned teardown/server.close; DB/LLM/mail=0.
Снимки corrected отдельно. До/эталон/после в новом FIXED_COMPARISON.html.
Откат: revert только собственных исправлений runtime/test; доменные записи не меняются.
Новых схем/контрактов/норм/предметных артефактов нет. Общий CI сохраняется.
