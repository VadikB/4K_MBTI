# Локальный минимум кандидата2.0.67

`preflight.json` и `preflight-repeat.json` — реальные stdout/exit штатной команды
`npm run ready:prepare -- --candidate 2.0.67`, свежий main e63. Bump выполнен один раз;
повтор идемпотентен, новый номер не назначает. Команда обновила только release
metadata/index cache refs и web/dist; обязательные источники/Api/scripts неизменны.

`lint.json`, `frontend.json`, `release-ci-tests.json` — полные локальные stdout/exit:
lint PASS, frontend140 PASS, release/CI Python22 PASS. Python запущен в sterile
isolated sentinel environment с DB_PORT9/пустыми provider keys/без `.env` и БД.
Warnings Node module type сохранены, не считаются скрытым PASS/новым дефектом.

`browser-results.json` — оригинальный Playwright JSON,100 PASS,79.311s,retries0,
сборка2.0.67/настоящий entry/dist/HTTP synthetic. Программа1.1 и role92 в отдельных
component fixtures не подменяют опубликованную1.2/role2 в историческом real PATH.
Четыре admin viewport PNG и status-list PNG — synthetic component presentation.
Старый spec перезаписывает2 tracked historical status-list PNG: новые байты сохранены
здесь, прежние восстановлены из точного Git HEAD; посторонних изменений в PR нет.

`local-identity.json` — SHA256 исходников/release metadata и45 assets на момент
локальных тестов. Git HEAD тогда2509aa2 с ожидаемым незакоммиченным release diff;
это честно не финальный SHA кандидата. Финальный commit связывается этими байтами
и последующим обязательным CI; актуальные head/base/CI links — в PR.

Полный backend/HTTP/integration/остальные browser lanes выполняются в обязательном
новом CI. Предыдущие доказательства не заменяют CI этого head/base. Локальный минимум
не выполняет provider/рабочие DB/публикацию/активацию/merge/deploy.

Historical `path-final-acceptance/CHECK.py` выполнять только в immutable2509aa2,
к которому относятся FILES/dist. Он не менялся ради release bump2.0.67.
Historical paid CHECK относится к e63; прежний LLM PASS не новый запуск кандидата.
