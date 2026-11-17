# Карта вывода legacy REPORT_08

| Старый runtime | Замена / состояние |
| --- | --- |
| `GET /users/admin/reports`, `GET /users/admin/reports/{session_id}` | `410` после авторизации; список закрытых Cycle — `GET /users/admin/m8-access/reports`, точный detail — `GET /users/admin/m8-access/reports/{report_id}`. |
| `PATCH /users/admin/reports/{session_id}/expert-comment` | `410`; экспертный комментарий к старому ассессменту не переносится в сохранённый M8 Report. |
| `GET /users/admin/reports/{session_id}/dialogue.pdf`, `/expert.xls`, `/expert.pdf`, `/cases/{session_case_id}/dialogue.pdf` | `410`; старые expert/dialogue выгрузки закрыты. |
| `POST /users/admin/reports/expert-group.zip`, `GET /users/admin/reports/export/expert-group.zip`, `GET /users/admin/reports.pdf` | `410`; Group Report/массовая выгрузка исключены из пилота. |
| `GET /users/{user_id}/assessment/{session_id}/report.pdf` | `410` для владельца; сохранённый личный M8 PDF — `/users/assessment/m8/reports/{report_id}/pdf`. |
| `_build_admin_reports`, `_build_admin_report_detail`, `user_sessions` + `session_skill_assessments` для средних процентов | Удалены из отчётных маршрутов. Операционные счётчики dashboard читают `m5_cycles`/`m8_reports`; групповые проценты, инсайты и график удалены. |
| `web/js/screens/admin/report-detail.js`, `skill-radar.js`, `charts.js`, `entries/admin-report-detail.js`, панель и диалоги; старые PDF/Typst services/templates | Удалены из runtime/сборки. Общий личный M8 экран переиспользуется в customer projection. |
| `docs/user-admin-guide.md` с `4K score`, групповым PDF и старым скриншотом | Переписан на список закрытых Cycle и сохранённый M8 Report; приложен новый снимок. |

Сохранены исторические записи Git и `docs/evc/evidence`, таблицы и поля `user_sessions`, оценки/диалоги, M5–M8 результаты, revisions и audit. Миграции данных нет. Прямой доступ к новому detail/PDF каждый раз перепроверяет текущее admin membership организации исторического Cycle и активность организации. Откат — revert кода/сборки; сохранённые C-67 и исходные данные не менялись.
