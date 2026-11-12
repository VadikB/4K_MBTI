# Состояние P4K-F05-F09-ONE

- База: `c06e94d5ff3784b2788b44089091a62a3921d301`, ветка `codex/f05-f09-one`.
- Активный шаг: итоговая проверка diff, фиксация кандидата и передача.
- Чужой checkout сохранён. GitHub CLI не авторизован.
- Исправлено: F05 latest draft и `effective_confirmed`; F06 поколение экрана
  назначения и защита поздних 200/error/readback; F07 известный отказ и
  неизвестный исход Turn; F08 сохранение ID Finish, bounded wait и readback;
  F09 сохранение ID Next, ограниченный poll, retry по серверу и мобильный layout.
- EVC-доказательства: 1089 backend PASS, 153 HTTP PASS, 31 targeted owned PG
  PASS, 271 frontend PASS, browser IT F05, PATH29 confirmed→draft→назначение→первый
  Turn и 12 browser
  component PASS. Lint/build/diff check PASS. Подробности и непокрытые части
  19 критериев — в CHECKS.
- F05 browser IT и PATH29 удалили свои marker-owned БД. Отдельная
  `p4k_f05_pytest` удалена после проверки marker; отсутствие всех test БД
  проверено, выделенный PostgreSQL 15 остановлен. Безопасная сводка и
  [cleanup](evidence/cleanup.json) сохранены в evidence.
- Следующий шаг: финальный review, local commit и передача точного SHA.
  Не объявлять PR-ready при незакрытых AC.
- Внешние действия: только fetch `origin/main`; push/PR/merge/deploy не выполнялись.
