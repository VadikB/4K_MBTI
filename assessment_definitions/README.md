# Определения assessment

Каталог содержит версионированные определения, которые могут быть проверены и
опубликованы без чтения изменяемых методических настроек во время сессии.

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

`cases/competencies_4k/1.1` — файловый draft-пакет из комплекта M5 v0.4 WORKING.
Он не подключён к runtime оценки и не меняет подбор Case. Каталог CT сохраняет
исходный статус FROZEN; Case и синтетические AS не получают допуск автоматически.

Сборка и независимая проверка сохранённых файлов:

```bash
.venv/bin/python scripts/build_m5_case_package.py \
  --source-zip /path/to/M5_Исправления_QA_v0.4_WORKING_комплект.zip
.venv/bin/python scripts/build_m5_case_package.py --verify-only
```

Конвертер использует стандартную библиотеку для чтения Office и существующий
Pydantic для контрактов. БД и LLM не нужны. Исходные бинарные файлы не копируются
в Git; manifest содержит их имена и SHA-256. `source-workbooks.json` сохраняет
непустые ячейки с адресами, `source-texts.json` — извлечённые тексты.

`case-package.json` содержит 20 CaseType, 20 паспортов из 21 поля, 40 ролевых
ветвей/синтетических AS, 80 проектных связей Observability и 160 спецификаций QA.
Связи с M2/M3 проверяются. Для 14 незаполненных целей K2 перечислены возможные
индикаторы из M2, но назначение оставлено открытым для методического review.

Схемы Case, Assessment Situation и Observability сразу поддерживают несколько
индикаторов на один Case/AS независимо от числа CaseType. Эти схемы — контракты
следующих этапов, не готовые API подготовки и исполнения. Пакет не включает
алгоритм M7, правила выставления оценок M6 и автоматическое подтверждение QA.

Результат текущего этапа виден в `verification-report.md` и JSON рядом с ним.
Это статическая проверка файлов: runtime, БД, реальные Dialogue и M6 отмечены
как `NOT_RUN`. Отдельная лаборатория в Prompt Lab использует пакет для
синтетической генерации начального предъявления и сохраняет прогоны в
`m5_generation_lab_runs`. Её результаты не меняют статусы файлового отчёта.
Инструкция проверки лаборатории — `docs/evc/m5-generation-lab-test-runbook.md`;
общий план — `docs/evc/tasks/m5-case-and-assessment-situation-plan.md`.
