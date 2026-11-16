# POSTW02-01 — доработка шапки и цветов после визуальной сверки

Прямой запрос владельца после dc65d39. Та же ветка codex/p4k-postw02-01;
новая ветка/PR запрещены, merge/deploy=false, задания02–05 не входят.
Выполненные изменения сохраняются. Текущие data projection/композиция не меняются.

Источники: AGENTS/EVC workflow/matrix, task01 rev1.1, архитектурный readset TASK.md,
exact v10e44fa78, UX-LK01/UX-UI01/UX-UI03, первичный P4K_UI_Baseline1.2 и
прямая новая постановка владельца. Статусы методологии не повышаются.

PR: list_artifacts пуст; gh pr list по head и по POSTW02 (state all) вернул[].
Ранее работа сохранялась локально без публикации. Ссылка/номер существующего PR
запрошены асинхронно; локальная работа не блокируется. Новый PR не создаётся.
Push допускается только для однозначно найденного PR/его уже согласованной ветки;
при отсутствии цели update/CI остаются NOT_RUN, не выполняется произвольный push.

Конфликт цвета: palette1.2/UX-UI03 задают neutral#F7F9FB и footer#68777C;
v10 задаёт#FAFAFA и rgb(100 116 139 /60%). В прошлой итерации оставлены1.2.
Теперь владелец прямо перечислил эти два целевых значения v10 и поручил исправление
через общие токены. Это основание применения новых participant semantic tokens
к затронутым элементам. Старые generic/ADMIN/W02 aliases не перекрашиваются.
Аватар#F0F0F0 также прямо задан владельцем. Значения живут только в tokens.css,
CSS общих компонентов использует var(), без локальных цветов/маскировки.

Готового общего JS/header renderer в репозитории нет: существующие .dashboard-topbar,
user-menu/user-chip и logout wiring повторяются в HTML. В Decision Registry и
применимых LK01/UI01/UI03 нет принятого требования сохранять тёмный квадрат32/36px
или конкретное сокращение имени. Выделяется reusable app-header identity/navigation
component на существующей разметке; не добавляется вторая шапка кабинета.
Вариант participant подключается только к кабинету, общий footer остаётся одним.
Прочие панели/их header markup/поведение не меняются. Реальный logout handler и IDs
сохраняются; desktop exit справа от account, mobile exit остаётся в общем user menu.

План: общий компонент/полное доступное имя+инициалы и fallback, participant tokens,
адресные frontend/HTML tests, bounded browser1440/390 с одинаковым synthetic payload,
known-name/fallback, nav GET-only, avatar/colors, body geometry reuse от dc65d39.
Новый fixture использует отличные от demo программу/организацию/даты/N=2,M=5,
чтобы подтвердить отсутствие demo-подстановок;320 только overflow.
Без изменения backend, таймеров, сохранённого плана/AS/данных, профилирования и отчётов.
Backend24/provenance/reference12/nav3 предыдущей итерации reuse по области.
Lint/build/diff и затронутые frontend; обязательный CI найденного PR не отключается.

Профиль:workers1/retries0,whole180/test60/idle60; local ephemeral HTTP, все/users stubbed;
DB/LLM/mail=0, owned teardown/afterAll.close. Откат — revert собственного follow-up commit.
