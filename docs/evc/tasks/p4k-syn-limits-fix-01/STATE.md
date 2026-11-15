# Состояние P4K-SYN-LIMITS-FIX-01

Ветка: codex/p4k-syn-limits-fix-01. Base: 68a52a7c21bfe7759d2522a644ad194f7d111f4e.
Worktree: /private/tmp/p4k-syn-limits-fix-01; основной checkout не изменён.
run_id: P4K-SYN-LIMITS-FIX-01-20261115; владелец: текущий исполнитель.

Завершено: источник/audit сохранён и проверен по hash; исправления A–C;
адресные L01–L06, controlled app-install (включая missing adapter), actual SIGINT,
осиротевший потомок, recovery после os._exit, файловый export/readback + summary.
Локальный код зафиксирован: 926f16337186381c4497a4e466be5c1178405ecf.
Локальные проверки завершены. Активно: передача владельцу; push/PR заблокированы.

Ресурсы: DB/container/browser/собственные порты/volumes не создавались.
restart policy N/A (собственные subprocess без restart).
Микропробы: resources.jsonl рядом с evidence; внутренняя регистрация — временные
owner.json, PID/PGID и контрольные PID в targeted-final.log.
Штатная остановка: OwnedProcess(registry).recover()/stop(), своя группа SIGTERM,
grace1s, затем SIGKILL, внешняя ps-сверка. registry хранится до успешной остановки.
После hard crash повторный start сверяет сохранённую регистрацию; запись чужого
лидера с изменившимся временем старта не разрешает kill.
Не обещается обнаружение процессов, созданных до сохранения registry, или
произвольно отделившихся в другую session. Проверен сценарий исходного аудита.

Первая process-проба не прошла: ps запрещён sandbox; spy не имел STDOUT.
Собственные группы 10581/10585/10589 адресно остановлены по tree.json, без чужих kill.
Повтор после установленной причины: processes-fixed PASS; actual SIGINT export-runner PASS.
Исходные FAIL и последующие PASS сохранены раздельно.

Проверки code candidate: backend1112 PASS, frontend331 PASS, lint/build PASS.
HTTP153 PASS переиспользован в неизменённой области. Финальная external ps-сверка:
28 собственных групп проверено, оставшихся PID/PGID нет. Данные — CHECKS.md/evidence.
Runtime/framework/environment не устанавливались: существующие .venv/node_modules
подключены локальными symlink, в Git не включаются.

Открыто: PATCH-кандидат2.1.8 запрошен у владельца по CONTRIBUTING, ответ ожидается.
До ответа version_bump=false; Ready/full CI/release gate зависимы от номера.
branch_push/pr запрошены поручением, но push отклонён auto-review до исполнения;
нужен явный допуск payload/destination. GitHub CLI не авторизован, plugin не подключён.
merge/deploy/artifact_publish=false.
Audit worktree detached сохранён. Все нужные audit evidence доступны в Git-пакете,
единственных нужных материалов в старом worktree нет. Чат не используется как evidence.
