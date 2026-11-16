# POSTW02-04 — подготовка слияния

16.11.2026 владелец в чате прямо поручил: «сливай на main». Это разрешение
на публикацию ветки/PR и слияние через обязательные проверки. Флаги:
branch_push=true, pr=true, merge=true; test deploy — автоматическое следствие merge
по CONTRIBUTING. Pilot/Prod и artifact_publish=false. Version_bump ожидает отдельного
ответа на вопрос о следующем patch по CONTRIBUTING/preflight.

Исходный head23e618e сохранён. Google Drive выгрузил packed-refs и часть pack indexes;
исходный общий Git отдавал Operation timed out. Он не исправлялся и не сбрасывался.
В /private/tmp/p4k-postw02-04-merge-20261116 восстановлена та же ветка и точная история
из доступных loose objects и origin (partial fetch). Ни один старый локальный коммит
не переписан; новый merge commit содержит актуальный main.

База перед выпуском: 7e96d4dc49e8e37356aa93a736d1373fb58eb779 / 2.1.18,
REPORT04/05 включены. Серверные и frontend исходники объединились автоматически;
все конфликты — generated dist, разрешены общей пересборкой. CSS cache reference
подготовки согласован с базой. Исторические review PNG не перезаписываются:
browser runner получил POSTW02_EVIDENCE для новых независимых прогонов.

`npm run ready:prepare` без candidate: exit2, требует отдельный approved patch
2.1.18 → 2.1.19. Владельцу задан вопрос; номер пока не менялся. Если main продвинется,
сначала обновляется база и заново определяется непосредственный patch-преемник.
CI/версия/точный кандидат/PR/результат merge будут добавлены после фактических действий.
