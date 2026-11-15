# Проверки P4K-SYN-LIMITS-FIX-01

Base / исходный аудит: `68a52a7c21bfe7759d2522a644ad194f7d111f4e`.
Code candidate / tested SHA: `926f16337186381c4497a4e466be5c1178405ecf`.
Ветка: `codex/p4k-syn-limits-fix-01`. Передаваемый head дополнит этот SHA только
отчётом/evidence; полные code hashes — [implementation-identity.json](implementation-identity.json).
Это локальное подтверждение технической обвязки, не приёмка продукта/методологии.

Первичное исходное evidence сохранено отдельно: [REPORT аудита](../../evidence/p4k-syn-limits-01-2026-11-15/REPORT.md),
[audit-copy.json](audit-copy.json). Проверены все исходные файлы по SHA-256, без
перезаписи прежних FAIL/PARTIAL/NOT_RUN. Ниже ссылки относятся к новым проверкам.

Точные исходные байты всех файлов аудита сохранены в
[original-audit-bytes.tar.gz](original-audit-bytes.tar.gz), проверены по audit-copy.json.
Для Git-просмотра у static-evidence.txt и машинных логов убраны только хвостовые
пробелы/пустые строки EOF. Точные байты затронутых логов и REQUEST дополнительно
сохранены в [raw-log-bytes.tar.gz](raw-log-bytes.tar.gz); пары исходных/просмотровых
checksum — [view-normalization.json](view-normalization.json). Исходная папка
аудита в основном checkout не изменялась, исходный REPORT сохранён побайтово.

| AC / исходный результат | Исправление / подтверждение | Тест и первичное evidence | Итог | Tested SHA | Предел вывода |
| --- | --- | --- | --- | --- | --- |
| AC01/L02 FAIL:1095 ASK в одной AS, остановка только извне | DriverBudget: общий счётчик и счётчик AS; фаза не создаёт новый бюджет; исчерпание до следующей команды | actual `completeStartedAssessment`, повтор q1/q2: maxStepsPerAS5 или maxSteps6, в обоих вариантах3 ASK; положительный short Next без Report. [driver-final.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/driver-final.log), frontend-candidate.log | PASS | 926f1633 | Controlled page adapter; технические пределы исполнителя, не норма числа уточнений участника |
| AC02/L04 FAIL:4→8 попыток с тем же ID | Gateway хранит OperationBudget по operation ID; JSON retry и transport key rotation резервируют общий остаток до отправки; исходный deadline не обновляется | actual `_strict_json_call`+gateway: исходный default4 остаётся4 после повторного входа; профиль5 использует остаток1, дальнейшие входы0; другая operation независима; positive JSON. [app-env-isolation.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/app-env-isolation.log), backend-candidate.log; test_synthetic_limits.py | PASS | 926f1633 | Срок жизни того же gateway/operation context. Полная prepare repair/queue и durable worker restart не входят в маршрут исходного контрпримера и не аттестованы; tokens/cost не доказаны. Timeout списывает попытку как неизвестный исход |
| AC03/L05 FAIL:потомок остаётся после native cleanup | OwnedProcess: новая session/group, регистрация PID/PGID/start identity, TERM/grace1s/KILL и внешняя сверка; recovery регистрации до нового запуска | actual `test_stand_check.check()`+реальный SIGINT, живой и уже завершившийся родитель, непослушный потомок; контрольный чужой PID жив; hard exit17 контроллера и последующий recover; ошибка записи registry. [targeted-final.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/targeted-final.log), backend-candidate.log, resources-final.json | PASS | 926f1633 | POSIX группы; зарегистрированные потомки исходного сценария. Нет гарантии для произвольного setsid, окна до регистрации или Docker. Zombie отдельно от работающего процесса; DB/browser/контейнеры/порты не создавались |
| AC04/L01 NOT_RUN из-за старого minimum120s | Самостоятельные deadline/no-progress в driver и Python runner; heartbeat не обновляет содержательный progress key, в файл пишется hash | actual driver неизменный processing80ms, actual runner150ms; разные причины RUN_DEADLINE_EXCEEDED/RUN_NO_PROGRESS_EXCEEDED; positive exit0. [driver-final.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/driver-final.log), [targeted-final.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/targeted-final.log) | PASS | 926f1633 | Внешний30s supervisor не сработал. Общий срок и отсутствие прогресса проверены раздельно; время участника/Cycle не изменено |
| AC05/L03 PARTIAL:проверен лишь controlled/real conflict | Native gateway до отправки запрещает внешний provider в синтетическом профиле; environment стенда и actual app-install выставляют технический запрет независимо от успешной подстановки | controlled provider работает; captured native class заблокирован, включая отсутствующий adapter actual app-install; независимый network/DNS deny активен до импорта и отдельно self-tested. [provider.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/provider.log), [app-env-isolation.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/app-env-isolation.log), guard-summary.json | PASS | 926f1633 | Owned DB gate app-install заменён nullcontext, не тест БД. Штатный запрет доказан без срабатывания interceptor; отдельная guard self-test намеренно заблокировала1 DNS. Реальные LLM/mail0 по deny+чистому env, не по fake counter |
| AC06/L06 PARTIAL:helper/spy, сохранность БД не проверена | Существующий gate/readback/summary подтверждены, не переписаны; общий runner останавливает вычисление до передачи неизвестного export | Ошибки write/readback/HTTP; destroy spy=[]; настоящий файл state прочитан обратно, испорченный diagnostic export сохранён; native helper в child+настоящий worker остановлены извне; summary FAIL/exit1 при process_exit0, исходный synthetic marker сохранён. Positive export/destroy работает. [export.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/export.log), [targeted-final.log](../../evidence/p4k-syn-limits-fix-01-2026-11-15/targeted-final.log), backend-candidate.log | PASS | 926f1633 | Файловый test state и command spy, не сохранность PostgreSQL и не прохождение пользовательского Cycle/Report. Сохраняется process exit и входной synthetic scenario marker; продуктовый исход не имитируется |

## Обязательный локальный набор

Команды запускаются через `run_check.py` с очищенным allowlist env,
`PYTHON_DOTENV_DISABLED=1`, `DB_POOL_MIN_SIZE=0`, независимым deny сети до импортов.
Реальные credentials не загружались. Тестовые `.env.example` и pytest temporary
fixtures допустимы; рабочие `.env` запрещены. Новых зависимостей не устанавливалось.

- `npm run test:backend`: **1112 passed**,572 deselected; backend-candidate.json/.log.
- `node --test tests/frontend/*.test.mjs`: **331 passed**; frontend-candidate.json/.log.
- `npm run lint:js`: **PASS**; lint-candidate.json/.log.
- `npm run build:web`: **PASS**; build-candidate.json/.log; tracked `web/dist` без diff.
- `npm run test:backend:http`: **153 passed**,15 deselected; http.json/.log.
  Переиспользован для неизменённого HTTP-кода; финальные изменения после прогона —
  только validation технических лимитов, process registry и тестовая изоляция env.
- Адресные микропробы: предел30s+отдельный teardown, последовательный запуск;
  exit0 scripts означает успешную проверку assertions, не общий продуктовый PASS.
- `git diff --check`, локальные ссылки, source hashes, audit-copy и review —
  результаты doc-verification.json. Полный validator/GC/реальные LLM не запускались.
- Integration PostgreSQL: NOT_RUN, схема/БД не менялись; файловая проверка AC06
  не названа сохранностью настоящей БД. Browser fixtures исполнялись actual driver
  с controlled page adapter; настоящий браузер не нужен проверяемым свойствам.

## Ошибки входа и повторные проверки

Первый process-run упал на sandbox ps и отсутствующем STDOUT у test spy.
Собственные группы10581/10585/10589 остановлены адресно по записанным tree.json.
Причины исправлены; processes-fixed PASS. Исходные логи не удалены.

Дополнительный точный L04-test обнаружил утечку env из app-install fixture.
Первая попытка `monkeypatch.delenv` отсутствовавшего ключа не регистрировала откат;
после установления этой причины fixture использует `monkeypatch.setenv` до actual
install. Runtime guard не ослаблен. Адресный порядок app-install→original-L04
подтверждён PASS в app-env-isolation.log; оба прежних лога сохранены. Расширение
аудита остановлено; соседние задачи не запускались.

## Review и риски

Review checklist: границы и потребители просмотрены; изменены только12 code/test
путей из implementation-identity. Нет изменений опубликованных артефактов,
миграций, публичного API, норм M1/M7, admission или расчётов. Новые defaults —
исключительно технические пределы исполнителя. AGENT4K_SYNTHETIC_ONLY — внутренний
флаг environment owned test harness, не предметная настройка и не чтение credentials.

Риск: operation registry хранится в памяти конкретного gateway; исчерпанные entries
не удаляются/не продлеваются. Перезапуск с новым gateway не заявлен защищённым;
общая очередь и глобальная стоимость вне этой задачи. Process recovery проверен
после сохранённой регистрации, не для произвольно отделившихся процессов.

Откат: revert implementation commit926f1633; diagnostic state/evidence сохранить.
При неизвестном outcome сначала остановить свою зарегистрированную группу,
затем прочитать saved export/state; восстановление/удаление только штатным
`scripts/test_stand.py destroy --state <owned-state>` после проверки условий экспорта
и владельца. В данном прогоне БД нет и recovery данных не требуется.

## Передача / открытые зависимости

GitHub CLI: `gh repo view` exit4, авторизация отсутствует. GitHub plugin найден,
но не установлен/не подключён; подключение не выдумано. `git push` отклонён
автоматической проверкой разрешений до исполнения: она требует явного подтверждения
передачи конкретного payload в `https://github.com/VadikB/4K_MBTI.git`.
Никакого обхода через другой интерфейс не выполнялось; remote не изменён.

Номер PATCH2.1.8 запрошен отдельно по CONTRIBUTING, решения пока нет.
`npm run ready:prepare` / version bump / Ready / PR / обязательный CI — NOT_RUN
до необходимых разрешения и авторизации. Человеческое review ожидается.
Merge/deploy/artifact publication=false. Main/test не изменены; baseline не объявлен.
Локальная реализация и технические AC подтверждены; вся передача задания не закрыта.

Следующий минимальный шаг владельца: подтвердить payload/destination push и номер
кандидата, авторизовать GitHub. Затем один PR и обязательные checks точного head,
без автоматического merge/deploy или новых оценочных запусков.
