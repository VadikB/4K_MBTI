# F02 — выпуск на main и TEST

Основание: прямое сообщение владельца **«выложи на main»** после локальной
передачи code `15232259d5915d564c7c9551dd80941862c3cd9a`, handoff
`54f4b5261c270acff723a48c1309f8d3848db7ef`. Дата11.11.2026.
Исходный код и локальные доказательства сохранены; SOURCE.txt не является
самостоятельным разрешением внешних действий.

Fresh origin/main `748be43e55587aa3b7e3a3945189c5ac737f59eb`,2.0.97.
Фактический GitHub actor `bvvfructus-jpg`; repository `VadikB/4K_MBTI`, push=true,
admin=false. Дубликатов PR ветки `codex/f02-delete-person` не найдено.

Допуск: branch_push/pr/merge/штатный TEST=true, необходимая подготовка версии=true,
artifact_publish/pilot=false. PATCH2.0.98 — непосредственный технический преемник
fresh main, выбран в пределах поручения на выпуск. Прямого push main/bypass нет.
После готового кода владелец поручил его продвижение; агент не объявляет от его
имени визуальную приёмку. Human visual PENDING.

Активно: canonical ready:prepare2.0.98 → release commit → один Ready PR →
exact-head mandatory CI → проверка свежей базы/review → squash merge →
штатный deploy-test и публичный version/asset readback → локальный main sync.
CI/main/TEST до исполнения этого этапа остаются NOT_RUN/748be43/новый выпускNOT_RUN.

Canonical `npm run ready:prepare -- --candidate 2.0.98` PASS. Обновлены только
4 release metadata файла; Api/scripts/tests/web/styles не менялись.
Независимая проверка46 dist modules после нормализации версии/content-hash имён:
совпадают целиком,0 missing/unexpected. JS lint и frontend261 PASS,
release unit11 PASS; `check_release_version.py --base-ref origin/main` PASS.
Прежний полный local minimum относится к неизменной функциональной реализации
1523225; обязательный GitHub full CI проверит exact release head.

Rules main прочитаны через API: squash-only PR, обязательные `frontend`, `pytest`,
`full-verification`, strict current base, required approval count0; bypass не
используется. Фактический PR review/status проверяется ещё раз перед merge.
