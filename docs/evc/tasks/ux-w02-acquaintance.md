# UX-W02 CLOSE — знакомство и готовность к оценке

## Результат и границы

- Ветка: `codex/ux-w02-close`, база — локальный R04 `7143c1d`, его база main —
  `39ffa2bdd43c002341a6630b905018d080f396ef`.
- R04 предоставляет только общий footer и вход. Он не считается источником цели,
  организатора, использования или получателей результатов.
- Реализован независимый объём W02: две server-side readiness, отрицательный ранний
  путь, последовательное знакомство, сохранение собственных ответов отдельно от M4,
  согласие, tenant-safe сообщение о неточности, подготовка без старта времени и
  явный старт подготовленной AS.
- Реальный положительный путь намеренно закрыт до опубликованного
  `OrganizationContext.participant_briefing`. `invitation_intro`, prompt и встроенный
  fallback не используются. Анкета администратора в эту задачу не добавлена.

## Источники и версии

- `UX-W02_CLOSE_2026-10-16.txt`, редакция 1.0,
  SHA-256 `5efe7e9b5372659f1bd3c7c9022c326aed566fb14627eff63605be4d78f64df9`.
- `UX-W02_Acquaintance_2026-10-15.txt`, редакция 1.4,
  SHA-256 `91d7def7a1b126fed9b117f1662fc515c132bb5ca55dbd418b972d5c71379dfc`.
- `P4K_Case_Return_Impact_Review_2026-10-15.txt`, редакция 1.1,
  SHA-256 `08e6af8ba0d53528dc11766c7a98cd836ae699df5148b1235fda68fd53ffbcec`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, ADR-002, Change 01/manifest, M1 v1.4,
  затронутые backend/frontend контракты и тесты.
- W01-прототип потребовал отдельной авторизации и не был доступен для проверки.
  Поэтому вопросы не встроены в код: positive fixture и runtime читают ровно три
  вопроса из опубликованного participant-facing briefing.

## Трассировка

| Правило | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| Ранняя readiness не зависит от M4 | membership + published OrganizationContext + явный `participant_briefing` | `Api/acquaintance.py::early_readiness`, journey | DB + browser |
| Нет источника — ожидание, не fallback | причина и безопасный текст | `wait_for_acquaintance_data`, «Проверить готовность», выход | browser 360 px |
| Ответы принадлежат участнику и живут до M4 | `participant_acquaintance_states.answers_json` | partial save, idempotent confirm | isolated PostgreSQL |
| Организационные данные readonly | briefing только читается | UI строит карточки, API принимает лишь `answer_1..3` | frontend + DB |
| Неточность получает реальный ответственный | `participant_data_issue_reports`, org admin required | tenant-scoped insert, без обещания email | isolated PostgreSQL |
| Поздняя readiness использует frozen M4 | `participant_profile.profile_for_start` | `late_readiness` | существующая M4/HTTP регрессия |
| Prepare не запускает время | prepared Cycle/Session | `/assessment/cycles/prepare` после подтверждения | M10 DB regression |
| Start предъявляет ту же AS | повторная readiness + prepared Cycle | `/assessment/cycles/start`; frontend не повторяет prepare | M10 DB + frontend |
| Числа только из плана | frozen M7 plan | route length, `planned_max_seconds`, budgets/window | frontend source regression |

## Изменённые пути

- Backend: `Api/acquaintance.py`, `Api/database.py`, `Api/routes.py`, `Api/schemas.py`.
- Frontend: `web/index.html`, `web/js/{dom,main,router,wiring}.js`,
  `web/js/screens/{onboarding,interview}.js`, onboarding CSS и собранный `web/dist`.
- Tests: W02 PostgreSQL/frontend, browser acceptance и существующая M10 регрессия.

## Проверки

- `py_compile Api/acquaintance.py Api/database.py Api/routes.py Api/schemas.py` — PASS.
- `node --check` для изменённых JS — PASS.
- `node --test tests/frontend/*.test.mjs` — 16 PASS.
- `pytest tests/unit/test_user_journey.py -q` — 5 PASS.
- `npm run lint:js` — PASS.
- `npm run build:web` — PASS.
- W02 isolated PostgreSQL — 1 PASS: отрицательная/положительная readiness,
  consent, partial/reload-safe answers, confirm без M4, tenant issue.
- M10 prepare/start isolated PostgreSQL — 1 PASS: prepared Cycle не расходует
  время, explicit start предъявляет ту же ситуацию.
- `npm run test:backend:http` — 55 PASS, 10 deselected.
- `auth-r03.spec.mjs` — 19 PASS, включая W02 direct URL/readiness retry/360 px.
- `git diff --check` — PASS.
- Полный `npm run test:backend` — NOT_RUN в этом цикле; предыдущий R04 прогон имел
  411 PASS / 13 известных baseline M6 FAIL (`INPUT_NOT_READY`,
  `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`), не связанных с W02.
- Полный runtime browser suite и две вкладки W02 positive — NOT_RUN.
- Реальные iOS/Android/Windows/macOS и мобильная клавиатура — NOT_RUN.
- Реальный participant-facing briefing/положительный test-контур — NOT_RUN:
  утверждённый источник заказчика отсутствует.

## Совместимость, риски и откат

- Новые таблицы аддитивны; опубликованные snapshots/Cycle/AS не изменяются.
- Сохранённые ответы и согласие остаются в БД при смене late-readiness.
- Existing started Cycle продолжает собственный frozen snapshot через journey.
- Главный продуктовый риск — до публикации briefing реальные участники увидят
  корректное ожидание. Это ожидаемая fail-closed граница задания.
- Откат: revert коммита. Новые таблицы можно оставить неиспользуемыми; удаление
  пользовательских ответов при откате не требуется и без отдельного допуска запрещено.

## Следующий шаг

После локального коммита: сначала принять/слить R04, затем push/PR W02, обязательный
GitHub CI и review. Для полного положительного запуска на test владелец должен
предоставить и опубликовать participant-facing briefing с тремя согласованными
вопросами; затем выполняются W02 positive, two-tabs и физическая browser matrix.
