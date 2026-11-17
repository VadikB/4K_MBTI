# P4K-POSTW02-QA-01 — состояние

17.11.2026. Прямое поручение пользователя: «возьми задание в работу» с файлом
P4K_POSTW02_QA01_Drafts_and_Dashboard_v1_0_2026-11-17.md (требования, не отдельное
полномочие). Исполнитель — текущий Codex на машине пользователя. Одна ветка
codex/p4k-postw02-qa-01, base свежего origin/main:
fffd501a51cae673a4e0ee87ec5d6cbc83069e21 / 2.1.26, fetch 17.11 выполнен.
Чужих незавершённых изменений нет. Прежняя ветка05 не используется.

Результат: две клиентские регрессии — поздний выбор черновика и обновление сведений
подготовки в dashboard. Индикатор бренда/подвал/методология/API/БД/таймеры исключены.
Черновик не Turn. Архитектурный адрес: PM-04, клиентский ввод LU-04.3/04.5 и
представление существующего состояния исполнения LU-04.2; новых LU нет.

Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/matrix/recipe/review/template/
decision-register; context/registry архитектуры1.0, Change01 WORKING README/И-4/6 и
карта LU, SourceSet manifest2026-10-01, M7v1.3 §§5.3–5.6; глоссарий WORKING30.09,
редакция2026-09-30-1 по сохранённому извлечению04/evidence/glossary-sections.txt;
карточки/STATE/отчёт UI04/05, настоящие draft/dashboard/preparation и их тесты.
Преемника в затронутой области не обнаружено; статусы источников не меняются.
Отдельные Principles10.10 и Task Rules14.11 найдены в Google Drive, но чтение
возвращает Operation timed out (включая вне sandbox); копии outputs также недоступны,
Downloads закрыт macOS. Их прочтение не заявляется. Технические критерии/пределы
полностью заданы текущей постановкой и EVC; новых предметных правил не вводим.
Восемь стоп-условий workflow: нет — адресные совместимые клиентские правки,
без новых норм/контрактов/хранилищ/миграций/прав/публикаций; откат revert.

Этап: локальная реализация, регрессии, lint/build/frontend и ограниченная browser
приёмка production bundle с управляемым API. Один worker, retries0, run≤300s,
шаг/HTTP≤20s, real LLM/mail0, synthetic данные. Собственный ephemeral HTTP server,
без БД/Docker/фонового preview, teardown в afterAll. CI имеет штатный профиль.
branch_push=true/pr=true в пределах принятого задания с одним PR;
merge/deploy/version_bump/artifact_publish=false. Будет draft PR: текущий процесс
требует отдельного номера перед Ready, поручение merge/номер отсутствует.

План: разведка, обе правки, регрессии, обязательный локальный JS минимум и визуальная
сверка390/1440 завершены. Code candidate/tested SHA46212e0a58e2a049a9144a1fcfcbcb0f9ff7c7c9.
404frontend/53targeted/6browser PASS, lint/build44/dist/diff PASS; оба дефекта
подтверждены failing регрессиями на base. Подробности и AC-A1–B4/R1 — REPORT.md.
Owned HTTP listeners закрыты, lsof подтвердил отсутствие; БД/LLM/mail/Docker0.
Сейчас — передача одного draft PR и наблюдение его CI; URL/head/итог CI будут в
передаче чата и outputs/p4k-postw02-qa-01-20261117/DELIVERY.json родительской папки.
Отдельный limitation: два дополнительных внешних источника остаются недоступными
для чтения; их соответствие не заявляется. Незакрытого технического AC нет.
Review/номер кандидата/Ready/merge владельца отдельно, TEST/Prod не менялись.
