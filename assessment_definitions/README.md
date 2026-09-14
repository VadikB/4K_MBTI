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
