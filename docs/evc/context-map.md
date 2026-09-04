# Карта контекста EVC

Загружайте только необходимый для задачи контекст. Начните с общих файлов, затем добавьте один относящийся к задаче срез.

## Общие файлы

- `AGENTS.md` — контракт разработки и границы безопасности.
- `README.md` — запуск, настройка и эксплуатационное поведение.
- `CONTRIBUTING.md` — ветки, CI, среды и приёмка.
- `.github/PULL_REQUEST_TEMPLATE.md` — обязательные доказательства при передаче результата.

## Архитектура оценки и управление определениями

- `docs/adr/001-assessment-platform-architecture.md`
- `docs/architecture/assessment-runtime.md`
- `Api/assessment_configuration.py`
- `Api/assessment_runtime.py`
- `Api/assessment_authoring_service.py`
- `assessment_definitions/`
- `tests/unit/test_assessment_configuration.py`
- `tests/integration/test_assessment_authoring_workflow_db.py`

## Исполнение сессии и очереди

- `Api/assessment_service.py`
- `Api/assessment_preparation_queue.py`
- `Api/assessment_analysis_queue.py`
- `Api/assessment_prompt_resolver.py`
- соответствующие модульные и интеграционные тесты очередей

## Интервью и генерация кейсов

- `Api/assessment/interview/`
- `Api/assessment/case_generation/`
- только относящиеся к задаче контрактные/модульные тесты; не загружайте legacy-фасад, если не затронут путь совместимости

## HTTP и управление доступом

- целевой раздел `Api/routes.py`
- связанные модели в `Api/schemas.py`
- подходящий из `Api/auth_service.py`, `Api/platform_access.py` или `Api/org_access.py`
- тесты HTTP-контрактов и авторизации

## Frontend

- целевая точка входа или экран в `web/js/`
- общие модули, фактически импортируемые этим экраном
- соответствующие CSS и ресурсы preview
- `web/index.html` — только при изменении загрузки точки входа или статических контрактов

Не передавайте в контекст агента `.env`, дампы базы данных, логи, production-данные, весь сгенерированный `web/dist` или не относящиеся к задаче крупные legacy-модули.
