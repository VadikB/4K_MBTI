# Определения assessment

Каталог содержит версионированные определения, которые могут быть проверены и
опубликованы без чтения изменяемых методических настроек во время сессии.

## Промпт лаборатории M5

`prompts/m5_generation_lab/v1/prompt.md` хранит исходную инструкцию `m5-lab-v1`
без изменения байтов. Manifest содержит источник (commit и прежнюю константу),
владельца содержания, статус `draft`, область `laboratory_only` и SHA-256.
Это перенос существующей инструкции, не методологическое утверждение или допуск
к официальной оценке. Конкретное ответственное лицо ещё не назначено.

`Api/m5_generation_lab.py:load_lab_prompt` проверяет manifest, UTF-8, непустой текст
и checksum перед новым запуском, затем копирует весь текст и метаданные в snapshot.
Исполнение и чтение старых запусков не требуют файлов пакета. Встроенного fallback нет.
Файл намеренно не имеет завершающего перевода строки для сохранения исходного checksum.

Содержание версии не редактируется на месте: изменение начинается с нового каталога
и версии manifest, проходит review и проверки, после чего ссылка PROMPT_PACKAGE
переключается в составе выпуска. Сам текст меняется в артефакте, не в Python.
Новый пакет поставляется вместе с кодом; отдельной БД-миграции или env не требуется.

## Методология 4К 1.1

Draft-пакет находится в `methodologies/competencies_4k/1.1` и соответствует
`methodology-package-v2.schema.json`. Число `database_version: 2` является
целочисленной версией записи в существующей модели БД; предметная версия
сохраняется отдельно как `methodology_version: "1.1"`.

Пакет пересобирается командой:

```bash
.venv/bin/python scripts/build_methodology_1_1_package.py \
  --source-dir /path/to/M2 \
  --output-dir assessment_definitions/methodologies/competencies_4k/1.1
```

Конвертер использует только стандартную библиотеку Python. Он читает нормативные
поля основной матрицы каждого XLSX и структуру паспорта DOCX, проверяет иерархию,
полноту `L0–L3`, Evidence Pattern и контрольные количества. Временные Office-файлы
игнорируются. Исходные документы не копируются; manifest содержит их имена и
SHA-256.

Предметные правила сборки не зашиты в Python: `import-profile.json` задаёт формат
Red Flags и runtime-binding каждой компетенции, а `normative-control.json` —
идентичность пакета, определения L0–L3, контрольные количества и семантические
инварианты Red Flags. Manifest фиксирует SHA-256 обоих управляющих артефактов.
Отдельный `transformation-report.json` проверяет сохранение содержания: для
каждой исходной ячейки Red Flags checksum нормализованного текста совпадает с
checksum текста, обратно собранного из результата преобразования.

Пакет намеренно не содержит ролей и политики агрегации. Их отсутствие не должно
компенсироваться скрытыми defaults. Runtime v2 может исполнять только опубликованный
неизменяемый снимок при включённом kill switch. До появления утверждённых правил
агрегации и отчёта этот draft не может быть default configuration.

## Базовые роли М3 для 4К 1.1

Шесть BaseRoles находятся в `role_profiles/competencies_4k/1.1`. Это отдельный
draft-пакет RoleProfile: каждая роль содержит четыре поля основного описания и
17 полей карточки. `base_roles_source.md` и `role_profile_source.md` содержат
полную текстовую транскрипцию двух нормативных DOCX; `role_profile_contract.json`
фиксирует структуру карточки, проверки ролевой валидности, инварианты и способы
формирования. Пакет не задаёт уровни 4К и не опубликован как действующая
конфигурация оценки; локальный draft выбора ролей описан отдельно в документации М3.

Локальная пересборка из нормативных документов:

```bash
python3 scripts/build_m3_base_roles.py \
  --base-roles-docx /path/to/M3.BaseRoles_v1.0_FROZEN.docx \
  --role-profile-docx /path/to/M3.RoleProfile_v1.0_FROZEN.docx \
  --output-dir assessment_definitions/role_profiles/competencies_4k/1.1
```

Исходные DOCX не копируются в Git. Имена и SHA-256 обоих источников хранятся
в manifest. Три роли методологии 1.0 не сопоставляются с шестью BaseRoles М3.

## Контекст М4 для 4К 1.1

Draft-пакет M4 находится в `contexts/competencies_4k/1.1`. Он содержит полную
текстовую транскрипцию FROZEN DOCX, машинный контракт OrganizationContext,
UserContext и правил объединения, а также JSON Schema неизменяемого
PersonalizedProfile. Статус `draft` относится к интеграционному пакету проекта и
не изменяет FROZEN-статус нормативного источника.

Локальная пересборка:

```bash
python3 scripts/build_m4_context_package.py \
  --source-docx /path/to/M4.Context_v1.0_FROZEN.docx \
  --output-dir assessment_definitions/contexts/competencies_4k/1.1
```

Исходный DOCX не копируется в Git. Его имя и SHA-256, а также контрольные суммы
трёх производных артефактов находятся в `manifest.json`.

## Кейсы M5 для 4К 1.1

`cases/competencies_4k/1.1` — единственный актуальный файловый draft-пакет M5,
собранный из пяти комплексных Case v0.1 WORKING по контракту M5 v1.1/schema v2.
Точные `IndicatorID` входят в версию Case. Пакет доступен для изолированного QA,
но не получает допуск к оцениванию автоматически.

Сборка и независимая проверка сохранённых файлов:

```bash
.venv/bin/python scripts/build_m5_case_package.py \
  /path/to/M5_Командное_обсуждение_5_комплексных_кейсов_v0_1_WORKING.xlsx
```

Конвертер использует стандартную библиотеку и Pydantic, проверяет SHA-256 исходной
книги, 22 поля каждого паспорта, ссылки M2/M3, 43 назначения индикаторов и создаёт
неизменяемый source snapshot. БД и LLM для сборки не нужны. Приложение читает JSON,
а не XLSX.

`case-package.json` содержит пять Case, персонажей, данные, шаги сценария,
Applicability и точные цели. `admission-policy.json` отделяет правила допуска от
кода. Схемы фиксируют Case, Assessment Situation и C-34 envelope. Case 04 содержит
явное нерешённое методическое условие; диалоговый QA и пилот отмечены `NOT_RUN`.
Пакет не включает
алгоритм M7, правила выставления оценок M6 и автоматическое подтверждение QA.

Результат текущего этапа виден в `verification-report.json`.
Это статическая проверка файлов: runtime, БД, реальные Dialogue и M6 отмечены
как `NOT_RUN`. Отдельная лаборатория в Prompt Lab использует пакет для
синтетической генерации начального предъявления и сохраняет прогоны в
`m5_generation_lab_runs`. Её результаты не меняют статусы файлового отчёта.
Инструкция проверки лаборатории — `docs/evc/m5-generation-lab-test-runbook.md`;
общий план — `docs/evc/tasks/t08.6-m5-case-as-admission.md`.

## M6 Evidence QA

`prompts/m6_evidence/v1` — draft-пакет построения Fragment/BS/Evidence/EB,
не IA и не официальный evaluator. Manifest фиксирует исходный M6 и checksum prompt,
параметры вызова/лимита/lease. `Api/m6_package.py` валидирует пакет при постановке
явного синтетического QA request; дальнейшее исполнение читает сохранённый snapshot.
Проверка: `.venv/bin/python -m pytest tests/unit/test_m6_evidence.py`.
Provider smoke и утверждённые GC не входят в эту проверку.

## M6 Indicator Assessment QA

`prompts/m6_indicator_assessment/v1` — draft-пакет M6-B для промежуточного
разбора, итогового IA и содержательного C-54 поверх сохранённой ревизии M6-A.
Пакет не включён по умолчанию и не означает методологическую приёмку или выпуск.

## M7 Cycle Planning QA

`planning/m7_cycle_plan/v1` — draft-настройки детерминированного планирования Cycle:
источник M7, defaults времени, версия алгоритма, источник длительности и tie-break.

## M7 Assessment Clarification QA

`prompts/m7_assessment_clarification/v1` — draft-пакет инструкции для одного
оценочного вопроса PM-04 по semantic interim C-54. Manifest привязан к M7 v1.3 и
фиксирует SHA-256 prompt. Loader сохраняет prompt/schema/provider snapshot; пакет не
является опубликованной нормой и не включён в основной пользовательский путь.
Пакет используется только restricted QA-путём и не допускает WORKING Cases.

## M8 Basic Report QA

`reports/m8_basic_report/v1` — draft-шаблон детерминированного C-67 и PDF.
Manifest связан с M8 v1.2 и фиксирует checksum шаблона. Инварианты запрещают
Recommendations, вывод Skill Level и CompetencyScore и требуют сохранять точные
дроби. Пакет не публикует методологию и не подтверждает Reliability.

`reports/m8_basic_report/v1_1` — новая draft-версия индивидуального C-67 с
Recommendations. `recommendations/m8/v1` хранит детерминированные шаблоны по
M8.6–M8.6.1. Runtime сохраняет минимизированный input из Results и snapshot
PersonalizedProfile, точные ссылки на IA, текст и версию механизма. Пакеты не
изменяют IA, Scores, Gap или Results и не используют ФИО/контакты.
