# Agent_4K

Интеллектуальная система оценки 4К-компетенций на основе кейсового интервью, профилирования пользователя и агентной пост-оценки навыков.

## Что есть в проекте

- backend на `FastAPI`
- база данных `PostgreSQL`
- веб-интерфейс на `HTML/CSS/JavaScript`
- интеграция с `DeepSeek`
- PDF-отчет по результатам оценки

## Требования

- Python `3.12+`
- PostgreSQL `15+`
- Bun для сборки фронтенда из `web/js/`

## Быстрый старт

### 1. Клонирование проекта

```bash
git clone https://github.com/nuclearys/4K-Assistant.git
cd 4K-Assistant
```

### 2. Создание виртуального окружения

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Скопируйте шаблон:

```bash
cp .env.example .env
```

Заполните в `.env`:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DEEPSEEK_API_KEY`
- при необходимости `DEEPSEEK_BASE_URL`
- при необходимости `DEEPSEEK_MODEL`
- `MBTI_ENABLED`
- `MBTI_FAISS_INDEX_DIR`
- при необходимости `MBTI_TOP_K`
- при необходимости `MBTI_FOLLOWUP_MODE`
- при необходимости `MBTI_FOLLOWUP_MAX_PER_CASE`
- при необходимости `MBTI_FOLLOWUP_SCORE_THRESHOLD`


### MBTI integration

Для MBTI-ветки нужен локальный FAISS-индекс книги.

Минимально:

```bash
MBTI_ENABLED=true
MBTI_FAISS_INDEX_DIR=/Users/vadim_bogachev/Desktop/mbti/mbti_rag/data/faiss
```

Дополнительно можно управлять генерацией уточняющих вопросов:

```bash
MBTI_FOLLOWUP_MODE=assist
MBTI_FOLLOWUP_MAX_PER_CASE=2
MBTI_FOLLOWUP_SCORE_THRESHOLD=60
```

Значения `MBTI_FOLLOWUP_MODE`:

- `off` — не задавать уточняющие вопросы
- `assist` — задавать только если данных недостаточно
- `strict` — всегда пытаться задать уточняющие вопросы после кейса

После каждого завершенного кейса API может вернуть:

- `mbti_case_result`
- `mbti_followup_questions`

После завершения всей сессии API может вернуть:

- `mbti_summary`

### 5. Подготовка базы данных

Создайте базу данных PostgreSQL и пользователя, затем восстановите дамп:

```bash
pg_restore -h localhost -p 5432 -U app_user -d app_db agent_4k_app_db_2026-04-14.dump
```

Если дампа нет, можно поднять пустую БД — необходимые служебные структуры веб-сессий будут созданы автоматически при старте приложения.

### 6. Запуск приложения

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Документация API:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Локальная разработка фронтенда

`web/index.html` подключает собранный модуль `web/dist/main.js` и lazy-loaded чанки из `web/dist/`, поэтому после изменений в `web/js/` нужно пересобрать фронтенд. Для удобной разработки держите сборщик в режиме watch во втором терминале:

```bash
bun run dev:web
```

Обычный локальный запуск тогда выглядит так:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
bun run dev:web
```

После изменений в JavaScript обновите страницу в браузере. Изменения CSS по-прежнему подхватываются напрямую из файлов `web/styles/` после обновления страницы.

### Превью экранов

Для проверки экранов без переходов по реальному пользовательскому сценарию можно включить dev-only галерею:

```bash
AGENT4K_ENABLE_SCREEN_PREVIEWS=1 uv run uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

После запуска откройте:

- [http://127.0.0.1:8010/__screens](http://127.0.0.1:8010/__screens)

Галерея использует текущие `web/index.html`, стили из `web/styles/` и собранный фронтенд из `web/dist/`, но подставляет фейковые ответы API.

## Основные файлы

- [main.py](/Users/andrey/PycharmProjects/Agent_4K/main.py) — точка входа приложения
- [Api/routes.py](/Users/andrey/PycharmProjects/Agent_4K/Api/routes.py) — HTTP API
- [Api/agent.py](/Users/andrey/PycharmProjects/Agent_4K/Api/agent.py) — логика интервьюера
- [Api/assessment_service.py](/Users/andrey/PycharmProjects/Agent_4K/Api/assessment_service.py) — подбор кейсов и кейсовое интервью
- [Api/communication_agent.py](/Users/andrey/PycharmProjects/Agent_4K/Api/communication_agent.py) — оценка навыков
- [Api/pdf_report_service.py](/Users/andrey/PycharmProjects/Agent_4K/Api/pdf_report_service.py) — генерация PDF
- [web/index.html](/Users/andrey/PycharmProjects/Agent_4K/web/index.html) — интерфейс

## Примечания по развертыванию

- Перед деплоем после изменений в `web/js/` нужно пересобрать браузерный бандл:

```bash
bun run build:web
```

Команда собирает модульный фронтенд из `web/js/main.js` в `web/dist/main.js` и дополнительные lazy-loaded файлы в `web/dist/`. В деплой-коммит должны попасть `web/index.html` и весь свежий каталог `web/dist/`, иначе браузер не загрузит актуальный интерфейс.

- Чтобы поднять новый номер релиза согласованно в backend и frontend, используйте:

```bash
./.venv/bin/python scripts/bump_version.py 2.1.1
```

или:

```bash
npm run bump:version -- 2.1.1
```

Скрипт обновляет:
  - `pyproject.toml`
  - `uv.lock`
  - `web/js/config.js`

После изменения версии пересоберите фронтенд и перезапустите приложение, чтобы в главном окне отобразилась уже запущенная версия.

- Для окружений можно использовать готовые шаблоны:
  - `.env.local.example` — локальная разработка и ngrok/dev magic link
  - `.env.production.example` — production с реальной email-доставкой через Postmark

Простой способ переключения:

```bash
cp .env.local.example .env
```

или:

```bash
cp .env.production.example .env
```

- Для production логирование теперь лучше разделено на два канала:
  - `runtime logs` приложения идут в `stdout` и/или файлы
  - `audit logs` по важным действиям и ошибкам остаются в таблице `system_logs`

- Рекомендуемые настройки для `.env`:

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

- При такой схеме:
  - ежедневные runtime-логи пишутся в каталог `logs/`
  - старые файлы ротируются автоматически
  - PostgreSQL не засоряется каждым техническим сообщением и запросом к статике

- Если приложение запускается под `systemd`, Docker или другим процесс-менеджером, предпочтительно оставить `LOG_TO_STDOUT=true` даже при включенных файловых логах.

- для production рекомендуется запускать приложение за reverse proxy
- реальные секреты не следует хранить в репозитории
- для передачи проекта на другой сервер используйте:
  - код проекта
  - `.env.example`
  - `requirements.txt`
  - дамп БД
