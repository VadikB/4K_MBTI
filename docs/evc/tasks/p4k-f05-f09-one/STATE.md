# Состояние P4K-F05-F09-ONE

- База: `c06e94d5ff3784b2788b44089091a62a3921d301`, ветка `codex/f05-f09-one`.
- Активный шаг: продолжение адресной browser/owned PG проверки, итоговая
  регрессия и фиксация кандидата.
- Чужой checkout сохранён. GitHub CLI не авторизован.
- Исправлено: F05 latest draft и `effective_confirmed`; F06 поколение экрана
  назначения и защита поздних 200/error/readback; F07 известный отказ и
  неизвестный исход Turn; F08 сохранение ID Finish, bounded wait и readback;
  F09 сохранение ID Next, ограниченный poll, retry по серверу и мобильный layout.
  Дополнительно исправлен текст неизвестного исхода Next после commit/потери
  ответа: он указывает на проверку той же операции, не на сохранение Turn.
  F07 теперь объясняет `M7_BLOCKING_SYSTEM_WAIT` как обработку предыдущего
  действия; отклонённый Turn не создаётся.
- EVC-доказательства: 1089 backend PASS, 153 HTTP PASS, 31 targeted owned PG
  PASS, 271 frontend PASS, browser IT F05, PATH29 confirmed→draft→назначение→первый
  Turn и 12 browser
  component PASS. Lint/build/diff check PASS. Подробности и непокрытые части
  19 критериев — в CHECKS. Новые E9–E13: 3+1+2+1+3 PASS browser/owned PG,
  F05-AC01/AC03, F06-AC01 и F09-AC04 закрыты; двухситуационный Turn→Finish→ASK→явный Next→Report и
  потери ответов Finish/Next проверены отдельно от общего PATH29.
  E12 проверил потерю ответа после подтверждения #2: после reload действует #2,
  #1 остаётся в истории, второго Confirm нет.
  E13 проверил поздние 200/409/500 назначения после logout/login, без изменения
  новой сессии и без дополнительного Cycle.
  E14 проверил полный runtime layout на 1440/390/320/200%: позднее CSS
  сужение Next устранено, между AS ненужная форма скрыта, screenshots в evidence.
  E15 проверил настоящий 409 Turn, readback исходной команды и терминальный
  двухситуационный Cycle.
- F05 browser IT и PATH29 удалили свои marker-owned БД. Отдельная
  `p4k_f05_pytest` удалена после проверки marker; отсутствие всех test БД
  проверено. PostgreSQL 15 повторно запущен для E9–E15; после E15 отсутствие
  test БД проверено и выделенный сервер остановлен. Безопасная сводка и
  [cleanup](evidence/cleanup.json) сохранены в evidence.
- Следующий шаг: финальный review, local commit и передача точного SHA.
  Не объявлять PR-ready при незакрытых AC.
- Внешние действия: только fetch `origin/main`; push/PR/merge/deploy не выполнялись.
