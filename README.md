# 4K MBTI

Сервис оценки 4К-компетенций и MBTI-профиля через персонализированное кейсовое интервью. Пользователь проходит ассессмент, система подбирает кейсы под роль и контекст, оценивает ответы, формирует отчет, MBTI-сводку и административную аналитику по организациям.

## Текущее состояние

- Backend: `FastAPI`, `PostgreSQL`.
- Frontend: plain `HTML/CSS/JavaScript`, сборка в `web/dist`.
- Авторизация: email magic link.
- Роли доступа: суперадмин, администратор организации, участник организации.
- Организации: создание, домены, админы, участники, CSV-импорт участников.
- Оценивание: персонализированные кейсы, диалоговый режим, таймеры, авто/ручное завершение кейсов.
- Отчеты: пользовательский отчет, админские детальные отчеты, PDF/ZIP exports.
- MBTI: FAISS/RAG индекс, summary по завершенной assessment-сессии, уточняющие вопросы.
- Регрессионные тесты в суперадминке: быстрый smoke и полный assessment-прогон.

## Репозиторий и ветки

Основной репозиторий:

```bash
git clone https://github.com/VadikB/4K_MBTI.git
cd 4K_MBTI
```

Рабочая схема:

- `main` — основная ветка разработки и деплоя.
- `dev/andrey` — ветка Андрея, синхронизируется с `main` по договоренности.
- Серверный проект подтягивает `main`.

Перед началом работы:

```bash
git checkout main
git pull --ff-only
```

## Версионирование

Правило проекта: каждый содержательный коммит увеличивает patch-версию на 1.

Один раз после клонирования включите git hooks:

```bash
./scripts/setup_git_hooks.sh
```

После этого `git commit` автоматически обновляет:

- `pyproject.toml`
- `uv.lock`
- `web/js/config.js`

Если нужно поднять версию вручную:

```bash
.venv/bin/python scripts/bump_patch_version.py
```

После деплоя версии нужен рестарт backend-процесса, потому что `/users/version` читает версию из `pyproject.toml` и кеширует ее в процессе приложения.

## Локальный запуск

### 1. Виртуальное окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка `.env`

Можно начать с шаблона:

```bash
cp .env.local.example .env
```

Ключевые параметры:

```env
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=app_db_mbti
DB_USER=app_user
DB_PASSWORD=...

DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=...
DEEPSEEK_MODEL=...

SUPERADMIN_EMAILS=your@email

MBTI_ENABLED=true
MBTI_FAISS_INDEX_DIR=/path/to/mbti/faiss
MBTI_TOP_K=5
MBTI_FOLLOWUP_MODE=assist
MBTI_FOLLOWUP_MAX_PER_CASE=2
MBTI_FOLLOWUP_SCORE_THRESHOLD=60
```

`SUPERADMIN_EMAILS` задает суперадминов через email. Несколько адресов можно перечислить через запятую.

### 3. База данных

Для локальной разработки используйте актуальный дамп или пустую БД с нужными справочниками/методологией. Production-подобная база сейчас называется `app_db_mbti`.

Пример восстановления:

```bash
pg_restore -h localhost -p 5432 -U app_user -d app_db_mbti dump_file.dump
```

### 4. Backend

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 18000 --reload
```

Swagger:

- http://127.0.0.1:18000/docs

Если видите старый процесс на другом порту, проверьте:

```bash
ps aux | grep uvicorn
```

### 5. Frontend

`web/index.html` грузит собранный `web/dist/main.js`. После изменений в `web/js` нужна сборка:

```bash
npm run build:web
```

Для watch-режима:

```bash
npm run dev:web
```

Если `bun` недоступен, можно временно собрать через локальный `esbuild`, но штатный путь проекта — `npm run build:web`.

CSS из `web/styles` подключается напрямую, обычно достаточно обновить страницу. Для обхода кеша удобно добавлять query string:

```text
http://127.0.0.1:18000/?ui=dev
```

## Администрирование

### Суперадмин

Суперадмин определяется через `SUPERADMIN_EMAILS` в `.env`.

Может:

- создавать организации;
- добавлять домены организаций;
- назначать админов организаций;
- импортировать участников через CSV;
- видеть сводные отчеты по всем организациям;
- управлять методологией и кейсами;
- запускать регрессионные тесты.

### Админ организации

Админ организации видит только данные своей организации. Он может:

- добавлять участников своей организации;
- импортировать участников через CSV;
- смотреть отчеты по своей организации;
- проходить оценивание сам через кнопку **Пройти оценивание** в админской панели.

### Участники

Участники привязываются к организации:

- по email-домену организации;
- вручную админом;
- через CSV-импорт.

## CSV-импорт участников

Ожидаемый формат:

```csv
email,full_name,role_description,job_instructions
user@example.com,Иван Иванов,Руководитель поддержки,Описание обязанностей
```

Обязательное поле только `email`. Остальные поля опциональны.

Поддерживаемые синонимы заголовков:

- `email`, `e-mail`, `mail`
- `full_name`, `name`, `fio`, `фио`
- `role_description`, `position`, `job_title`, `role`, `должность`, `роль`
- `job_instructions`, `duties`, `instructions`, `job_description`, `обязанности`, `инструкции`

Защита от дублей:

- email нормализуется;
- существующий пользователь переиспользуется;
- повторная привязка к той же организации не создает дубль membership.

Если один и тот же человек должен быть админом организации, сначала можно импортировать его как участника, затем добавить тот же email в поле администратора организации.

## Регрессионные тесты

Раздел доступен суперадмину: **Админка → Регрессионные тесты**.

Есть два режима:

- **Запустить smoke** — быстрый тест без реального LLM-прохождения кейсов. Создает тестовую организацию, 3 пользователей, технические completed-сессии с MBTI payload, проверяет отчеты и очищается вручную кнопкой очистки.
- **Полный прогон** — создает `__autotest__` организацию и 3 пользователей, запускает реальные assessment-сессии через основной `assessment_service`, отвечает автоответами по кейсам, завершает сессии, проверяет результаты кейсов и MBTI summary.

Перед полным прогоном интерфейс просит подтверждение, потому что режим делает реальные LLM-вызовы и может занять несколько минут.

Тестовые данные имеют префикс:

```text
__autotest__
```

Их можно удалить кнопкой **Очистить __autotest__**.

## MBTI

MBTI включается переменной:

```env
MBTI_ENABLED=true
```

Индекс задается так:

```env
MBTI_FAISS_INDEX_DIR=/path/to/faiss
```

Режим уточняющих вопросов:

```env
MBTI_FOLLOWUP_MODE=off|assist|strict
```

- `off` — не задавать уточняющие вопросы.
- `assist` — задавать, если данных недостаточно.
- `strict` — пытаться задавать после каждого кейса.

После кейсов API может вернуть `mbti_case_result` и `mbti_followup_questions`. После завершения всей сессии формируется `mbti_summary`.

## Деплой

Текущий production/pilot сервер:

```bash
ssh -i ~/.ssh/mobius_ssh.key user1@176.123.166.242
cd /home/user1/projects/4K-Mbti
```

Сайт:

- http://pilot.4k-assistant.ru/

Типовой деплой:

```bash
git pull --ff-only
sudo systemctl restart agent4k-mbti.service
systemctl is-active agent4k-mbti.service
curl -fsS http://127.0.0.1:8000/users/version
```

Публичная проверка:

```bash
curl -fsS http://pilot.4k-assistant.ru/users/version
```

Если менялся frontend в `web/js`, перед коммитом обязательно:

```bash
npm run build:web
git add web/dist web/index.html web/js web/styles
```

`web/dist` хранится в git, поэтому серверу достаточно `git pull` и restart.

## Версия

Текущий runtime endpoint:

```text
/users/version
```

Для согласованного bump backend/frontend версии:

```bash
./.venv/bin/python scripts/bump_version.py 2.1.1
```

или:

```bash
npm run bump:version -- 2.1.1
```

После bump версии пересоберите frontend и перезапустите сервис.

## Важные файлы

- `main.py` — точка входа FastAPI.
- `Api/routes.py` — HTTP API.
- `Api/agent.py` — логика профилирования и интервьюера.
- `Api/assessment_service.py` — подбор кейсов, assessment-сессии, обработка ответов.
- `Api/regression_tests.py` — smoke/full регрессионные тесты.
- `Api/org_access.py` — организации, scope, суперадмины.
- `Api/mbti/` — MBTI/RAG/FAISS-логика.
- `Api/pdf_report_service.py` — пользовательский PDF.
- `Api/admin_report_*` — админские PDF/экспорты.
- `web/index.html` — основная HTML-страница.
- `web/js/` — модульный frontend.
- `web/styles/` — стили.
- `web/dist/` — собранный frontend, хранится в git.

## Логи

Рекомендуемые production-настройки:

```env
LOG_LEVEL=INFO
LOG_TO_STDOUT=true
LOG_TO_FILE=true
LOG_DIR=./logs
LOG_FILENAME=agent4k.log
LOG_ERROR_FILENAME=agent4k-error.log
LOG_ROTATION_WHEN=midnight
LOG_BACKUP_COUNT=14
AUDIT_LOGS_TO_DB=true
RUNTIME_LOGS_TO_DB=false
```

Runtime-логи пишутся в `logs/`, audit-события остаются в таблице `system_logs`.
