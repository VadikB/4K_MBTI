## Задача

`docs/evc/tasks/exec-contour-fix-01.md` — F02–F04 исходного EXEC-CONTOUR-01.
Сохранены H1–H12 и standalone AC18. Методология и продуктовая схема не меняются.

## Изменение

- Введён строгий `assessment-execution-contour/2`: stage chain, source/first-case
  hash, owned Cycle/Session/AS, C-45/C-54/C-46, terminal DB readback,
  Results/Report revision/owner, process/cleanup/failure проверяются до PASS.
- Browser driver учитывает повторный ASK, закрытие из другой вкладки и закрытие
  по времени; Next ждёт действительно предъявленную AS.
- После старта исполнения cleanup требует сохранённый и прочитанный terminal
  export. При неизвестном исходе owned state/DB остаются для восстановления.

## Проверки

Подробности, H1–H12, Q01–Q08, source hashes и evidence manifest:
`docs/evc/reports/exec-contour-fix-01.md`.

- После rebase на EXEC-FIX-04 `main@43c5da5`: backend 1055 PASS;
  fractional H7 integration 7 PASS на отдельной test/pytest БД.
- Frontend 226 PASS; validator/normalizer 61 PASS; lint PASS.
- Release `2.0.94`: HTTP 144 PASS, backend 1055 PASS, frontend 226 PASS,
  lint/build/ready:prepare PASS.
- Controlled browser completion 2 PASS (включая повторный ASK), standalone PATH29 free 1 PASS.
- EXEC03 browser C1–C9: 3 PASS, включая C7–C9 на HTTP/PG/browser;
  после EXEC-FIX-04 повторено 3 PASS на `a5dfb995ec80c278cda210488411e78cbf12335c`.
- Offline F02: valid `/2` и historical standalone приняты; semantic mutations
  и incomplete `/1` normalizer отклонены.

Новый paid/provider composite не запускался по прямому запрету. Q01/02/04/05
остаются частичными в части полного paid пути и отдельных реальных browser
fault/calendar контрпримеров. H7 итогово PASS_CONTROLLED после EXEC-FIX-04;
длинный wall-clock и paid composite NOT_RUN.

## Выпуск и откат

База обновлена после EXEC-FIX-04, H7 подтверждён, PATCH-кандидат `2.0.94`
подготовлен штатным `ready:prepare`. До merge: полный CI и отдельное ревью
владельца этого PR. Merge запускает автоматический TEST deploy;
сохранить прежнее окно приёмки. Откат — revert PR. При `cleanup-deferred`
восстановить owned DB по marker, затем штатно удалить её; published артефакты
и исторические receipts не менять.
