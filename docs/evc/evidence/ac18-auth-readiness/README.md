# AC18-AUTH-READY-01: безопасные первичные результаты

Implementation c4a6a0cb1e28cda7a4188ac8d4efef33c237999c от main339aff9/2.0.74.
Before browser2 FAIL, final browser127 PASS, frontend146/backend956/HTTP108 PASS.
Нет нового CI/выпуска/реального LLM; это не PASS AC18.

`before-browser-results.json` — настоящие deterministic отказы исходного UI.
`final-browser-results.json` — полный бесплатный auth/admin/recovery synthetic HTTP
suite, retries0/flaky0. JUnit/manifest сборки сохраняют результаты остальных проверок.
`auth-readiness-diagnostic.json` — отдельное component воспроизведение; его
причинная идентичность actual failed run NOT_PROVEN.

`negative-run-failure.json`, `negative-run-cleanup-readback.json`,
`negative-run-http-observation.json` — оригинальные bytes из actual run2835475f…,
сохранённые отдельно, не переписанные после исправления. Все31 primary JSON/PNG
с manifest и pinned source bytes входят в отдельно переданный пакет (`remote/`).
Blank historical failure PNG не приписывается UI администратора.

`visual/` — synthetic pending/step2/safe-capture; password и token values не
выгружаются, helper-маска видна на failure PNG. Полные raw auth traces, .env,
state.json, cookies, ключи и generated passwords не входят в evidence.

Предварительные тестовые ошибки (syntax; затем ошибочное ожидание query URL)
сохранены в отдельном полном пакете как история, не объявляются продуктовым FAIL
и не заменяются итоговым PASS. [Отчёт](../../reports/ac18-auth-readiness.md).
