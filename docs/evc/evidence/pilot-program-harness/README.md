# Первичные проверки PATH-PILOT-HARNESS-01

- backend.txt — actual stdout/exit итогового backend:906 PASS.
- node.txt — общий validator:66 PASS, точные program refs и прежние AS/admission/stage negatives.
- integration.txt и owned-bootstrap/*.json —3 actual owned bootstrap/negative runs,
  distinct DB IDs, counts/27 original QA/cleanup. Future metadata SYNTHETIC.
- component-browser.txt и component-readback.json —1 component-only browser PASS,
  provider disabled/подстановка обозначена; не full PATH/pilot/LLM.
- container-cleanup.json — exact owned Docker label/ID, zero DB/connections before
  stop, AutoRemove/absence. Другие контейнеры/постоянная БД не затронуты.
- precommit-probe.json — exact file hashes и before/after reservation probe на
  рабочем содержимом до коммита; Git HEADf211e71 не является SHA изменённого runtime.
- VERIFY.py — offline replay без config/database/provider imports. Запускать из
  полного checkout переданного финального commit, а не неполного архива docs.

Реальные provider calls0. Схема/программа рабочей DB не менялась, новых publication/
активации/paid PATH нет. CI для нового commit NOT_RUN. Исторический PREP-DIAG-01 UNKNOWN.
Все изменения содержат только harness/tests/docs. База main3385145/2.0.65;
проект выпуска1.2 остаётся проектом. Общие release permissions сюда не включены.
