<!-- Производное текстовое представление source.docx; статус и применимость см. README.md. -->

# M1 — Архитектура и понятийная модель 4К

Methodology 4К 1.1 · FROZEN v1.4 · CURRENT=NO · 01.10.2026

| Параметр | Значение |
| --- | --- |
| ArtifactID | M1 |
| Версия | v1.4 |
| Статус / CURRENT | FROZEN / NO |
| Дата редакции | 01.10.2026 |
| Исходная версия | M1 v1.3 FROZEN от 22.09.2026; исходный FROZEN не изменяется |
| Основания синхронизации | M2 применяемые FROZEN паспорта/матрицы; M3 и M4 v1.0; M5 v1.1 FROZEN; M6 v1.8 FROZEN; M7 v1.3 FROZEN; M8 v1.2 REVIEW |
| Publication | FROZEN присвоен по решению владельца 01.10.2026; CURRENT=NO до отдельной публикации Sources → Registry → CURRENT → Manifest по M0 |

| Назначение этой FROZEN-редакции — синхронизировать понятийный контракт M1 с накопленными решениями M2–M8. В M1 фиксируются сущности, связи, инварианты и границы ответственности; алгоритмы, формулы, пороги, интерфейсы и операционные процедуры остаются в тематических модулях. |
| --- |

## M1.1. Назначение, принципы и архитектура

Назначение

M1 задаёт единый понятийный контракт Methodology 4К 1.1: основные сущности, их смысл, устойчивые связи и границы ответственности между M2–M8. M0 управляет версиями, Source of Truth, Change & Impact и публикацией.

Конкретные поля сущностей, алгоритмы извлечения Evidence, формулы агрегирования, пороги достаточности, правила маршрутизации и формы интерфейса не закрепляются в M1, если они не необходимы для различения самих понятий.

Сквозная архитектура

M0 Governance → M1 Architecture → M2 Construct / M3 RoleProfile / M4 Context / M5 Case & Interaction / M6 Evidence & Assessment / M7 Assessment Cycle / M8 Results & Reports

| Блок | Функция в понятийной архитектуре |
| --- | --- |
| M2 | Определяет K1–K4, Skills, Components, Indicators, L0–L3, Boundaries, Evidence Patterns и нормативные Red Flags. |
| M3 | Определяет RoleProfile и BaseRoles, их формирование, версии и ролевую валидность; связывает RoleProfile с отдельным RoleSkillTargetProfile. |
| M4 | Определяет OrganizationContext, UserContext и производный PersonalizedProfile; фиксирует происхождение и версии контекста. |
| M5 | Определяет CaseType, Case, Applicability, точные IndicatorIDs Case, Assessment Situation, проектные условия Indicator Observability, Dialogue и границы взаимодействия. |
| M6 | Проверяет фактическую возможность наблюдения, формирует Fragments, Behavioral Signals, Evidence, EB, итоговые IA, допустимые сводные вклады и Scores; определяет Confidence, Reliability и GC. |
| M7 | Определяет Assessment Cycle и Sessions, их принадлежность, план, покрытие, время, уточнения, паузы, продолжение и закрытие. |
| M8 | Фиксирует и представляет Results закрытого Cycle, целевые сравнения и Report, включая индивидуальные, продольные и групповые представления. |

Принципы

1.  Разделение слоёв: конструкт, контекст, инструмент, организация прохождения, наблюдаемый материал, Evidence, оценочные выводы и представление результатов имеют разные назначения.

2.  Доказательность: каждый оценочный вывод трассируется к фактическому материалу и условиям; отсутствие Evidence не равно L0.

3.  Инвариантность конструкта: Case, роль, контекст, временные параметры и целевые требования не меняют Indicators и их Level Descriptors.

4.  Фиксированность среза: Assessment Cycle представляет один срез одного человека и не объединяется с другими Cycles для создания нового фактического профиля.

5.  Прослеживаемость версий: сохраняются версии M2, RoleProfile, PersonalizedProfile, Case, механизма оценивания и правила расчёта, необходимые для восстановления результата.

6.  Неизменяемость факта: Report, цель сравнения и Recommendations не переписывают фактическое ядро Results.

## M1.2. Общая онтология Methodology 4К 1.1

Понятийная модель включает шесть классов сущностей. Классы задают назначение; физическая схема хранения и API в M1 не определяются.

| Класс | Ключевые сущности и связь |
| --- | --- |
| 1. Construct 4К | Competency → Skill → Component → Indicator → Indicator Level Descriptor. Для Indicator могут задаваться Evidence Pattern и Red Flag. |
| 2. Context | OrganizationContext + RoleProfile + UserContext → PersonalizedProfile. RoleSkillTargetProfile хранится отдельно от PersonalizedProfile. |
| 3. Instrument & interaction | CaseType(s) → Case [Applicability; точные IndicatorIDs + версии M2] + PersonalizedProfile → Assessment Situation [условия Indicator Observability] → Assessment Interaction → Dialogue → Turns. |
| 4. Assessment organization | Assessment Cycle → 1..N Assessment Sessions → 1..N Assessment Situations. Один Cycle — один срез одного человека с одним зафиксированным PersonalizedProfile. |
| 5. Observation & evidence | User Turn → Fragment → Behavioral Signal → Simple / Composite Evidence. Для каждой пары IndicatorID × AS существует EB с 0..N Evidence; сформированный IA связан с EB той же пары. EB сохраняет связь с AS, Dialogue и условиями независимо от наличия Evidence. |
| 6. Results & presentation | Закрытый Cycle после завершения расчётов → один логический Results. Results содержит AssessedSkillProfile с 0..N Skill Results, Competency Profiles, покрытие и ограничения; Skill Result может иметь полный SkillScore, частный SkillScore либо не иметь SkillScore. Results → 0..N Report. Отдельно RoleProfile → 0..N RoleSkillTargetProfile; сравнение допускает NOT_COMPARABLE без создания фиктивного Skill Result. |

Recommendations, Assessment Series, Longitudinal Report и Group Report являются производными блоками или областями представления в M8 и не вводятся как самостоятельные верхнеуровневые сущности M1.

## M1.3. Конструкт 4К

Competency → Skill → Component → Indicator → Indicator Level / Indicator Level Descriptor

Competency, Skill, Component, Indicator

Competency — интегральная способность для класса деятельности: K1 Коммуникация, K2 Командная работа, K3 Креативность, K4 Критическое мышление. Конкретная текущая структура Skills, Components и Indicators задаётся применяемыми FROZEN-паспортами и матрицами M2.

Skill — относительно самостоятельная функциональная способность. Component — существенная сторона Skill, группирующая Indicators и участвующая в агрегировании. Component не получает собственного формального L0–L3; для него может рассчитываться ComponentScore.

Indicator — нормативный критерий проявления способа действия. Он принадлежит одному Component. Фактический Behavioral Signal не является Indicator и не заменяет его нормативное содержание.

Уровни и доказательные признаки

Каждый Indicator имеет Level Descriptors L0–L3. L отражает качество фактически проявленного способа действия и не является сложностью Case, временным ограничением или требованием роли.

Evidence Pattern — нормативное описание наблюдаемых элементов и содержательных или временных связей, которые могут служить основанием интерпретации Indicator. Boundary — нормативное разграничение содержательно близких Indicators, Components или Skills. Red Flag — нормативный отрицательный поведенческий признак конкретного Indicator; отсутствие Evidence не является Red Flag и само по себе не задаёт L0. Эти элементы принадлежат M2. RedFlagObservability и Critical Constraint Violation в нормативную онтологию этой редакции не вводятся.

## M1.4. Контекст оценки

OrganizationContext + RoleProfile + UserContext → PersonalizedProfile

OrganizationContext

Общие подтверждённые условия организации, правила, терминология и ограничения использования информации, применимые к оценке. Состав и обязательность определяет M4.

RoleProfile

Версионируемое нормативное описание типа деятельности, ответственности, задач, объектов, полномочий, взаимодействий, ограничений и рисков. RoleProfile управляется M3, может опираться на BaseRole, не тождествен должности и не содержит Target Levels.

UserContext

Индивидуальные сведения конкретного оцениваемого для организации прохождения, релевантной персонализации и связи результата с человеком. Идентификационные и контактные сведения не передаются для формирования Cases и содержательного оценивания и не становятся Evidence. Сведения UserContext сами по себе не являются доказательством уровня; фактически предъявленные условия восстанавливаются по Assessment Situation и Dialogue.

PersonalizedProfile

Единственная производная сущность M4, объединяющая OrganizationContext, RoleProfile и UserContext с сохранением происхождения и версий. PersonalizedProfile фиксируется до первого использования для подбора или формирования Cases данного Cycle. Один Assessment Cycle использует один зафиксированный PersonalizedProfile; изменение источников после фиксации, в том числе до первого ответа, не переписывает использованный профиль автоматически.

RoleSkillTargetProfile не входит в PersonalizedProfile. Использование зафиксированного PersonalizedProfile в Recommendations допускается как последующий контекст M8; совместимость этой границы с M4 сохраняется как отдельная CHECK-зависимость до адресного закрытия в OwnerChat M4.

## M1.5. Инструмент оценки, применимость и наблюдаемость

CaseType

CaseType — типовая оценочная задача с устойчивым содержательным механизмом. Case может реализовывать 1..N CaseType; формат реализации не образует отдельный CaseType.

Case

Case — спроектированная сценарная конструкция для одной или нескольких допустимых ролевых ветвей. Case фиксирует Applicability на уровне SkillID / ComponentID и точный перечень оцениваемых IndicatorIDs применяемых версий M2. Для каждого IndicatorID должны быть спроектированы условия, в которых его самостоятельное проявление может быть наблюдаемо.

Перечень IndicatorIDs является частью версии Case. Ответы оцениваемого, фактически возникшие сигналы или поздний анализ M6 не расширяют этот перечень. Новая цель требует QA и новой версии Case до взаимодействия.

Assessment Situation

Assessment Situation (AS) — конкретная персонализированная реализация одного Case для одного оцениваемого в конкретном Cycle. AS сохраняет CaseID и версию, применённые версии M2, точные IndicatorIDs Case, зафиксированный PersonalizedProfile и одну допустимую ролевую ветвь.

Indicator Observability

До взаимодействия AS конкретизирует условия Indicator Observability для каждого IndicatorID из Case. M6 затем проверяет фактическую возможность: возникли ли необходимые условия в реальном Dialogue. Проектная Observability, фактическая возможность и Evidence являются разными характеристиками.

Applicability ≠ проектная Indicator Observability ≠ фактическая возможность ≠ Evidence

Multi-CT, multi-role и единая модель Dialogue → Turns сохраняются. Сложность Case не является L0–L3.

## M1.6. Assessment Interaction, Dialogue и состояния завершения

Единая модель взаимодействия

Assessment Situation → Assessment Interaction → Dialogue → Turns

Dialogue — последовательность ходов системы и оцениваемого в пределах одной AS. Одноходовое взаимодействие является частным случаем Dialogue. Turn — один ход участника с сохранённым авторством и порядком.

Реплики системы, персонажей, предъявленные материалы и события AS задают условия интерпретации. Явно выраженные проявления оцениваемого локализуются в пользовательских Turns. Доказанное невыполнение действия при фактической возможности может обосновываться полным релевантным Dialogue и условиями AS без создания вымышленного пользовательского Turn, Fragment или Behavioral Signal. Самостоятельная сущность Response в M1 не требуется: ответ является содержанием одного или нескольких пользовательских Turns.

Четыре разные границы

| Состояние | Понятийный смысл |
| --- | --- |
| Завершение основного сценария | M5 фиксирует предусмотренное конечное состояние сценарной задачи. Это не означает закрытие AS, достаточность Evidence или готовность итоговых IA. |
| Закрытие AS / Dialogue | Решение M7 прекращает приём новых Turns в этой AS. Только после закрытия M6 формирует итоговые IA по всему материалу AS. |
| Пауза / допустимое прерывание | AS, Session и Cycle могут оставаться открытыми; история и исходные условия сохраняются. Для открытой AS итоговый IA не выпускается. |
| Закрытие Cycle | M7 завершает сбор ответов для данного среза. Закрытие не означает полноту покрытия; последующие расчёты не открывают Cycle заново. |

После завершения сценария M6 может выявить конкретную оценочную неопределённость. M7 решает, назначать ли уточнение, формулирует и останавливает его в границах M5. Уточнение входит в тот же Dialogue и не создаёт отдельного IA. Новое самостоятельное сценарное действие требует другой AS.

## M1.7. Fragment, Behavioral Signal и Evidence

Fragment и Behavioral Signal

Fragment — локализованный участок одного пользовательского Turn. Один пользовательский Turn может содержать 0..N Fragments; каждый Fragment принадлежит ровно одному Turn. Системные Turns и материалы AS не становятся Fragments поведения оцениваемого, но сохраняются как условия интерпретации.

Behavioral Signal — локальное наблюдаемое проявление, непосредственно основанное на одном Fragment. Один Fragment может содержать несколько Signals. Использование одного Signal для разных Indicators требует самостоятельного содержательного основания для каждого Evidence.

Типы Evidence

В Methodology 4К 1.1 используются два типа Evidence: Simple и Composite.

| Тип | Определение |
| --- | --- |
| Simple Evidence | Интерпретация одного локального проявления, достаточного для конкретного индикаторно-специфического вывода. |
| Composite Evidence | Единая интерпретация нескольких содержательно связанных проявлений одного IndicatorID в одной AS. Может включать порядок Turns, изменение поведения, изменение доступной информации и влияние уточняющих вопросов, если эти связи существенны для вывода. |

Самостоятельный тип Trajectory Evidence исключён. Последовательность и динамика не теряются: они являются возможным содержанием Composite Evidence. Тип Evidence сам по себе не задаёт уровень L.

Evidence Bundle

Evidence Bundle (EB) относится к одной паре IndicatorID × Assessment Situation и содержит 0..N фактических Evidence. EB может быть пустым. Evidence из разных AS в один EB не объединяются.

Отсутствующие Evidence, Behavioral Signals, Fragments и пользовательские Turns не создаются для заполнения доказательной цепочки. При доказанном невыполнении используются фактический Dialogue, условия возможности и реальные действия либо их отсутствие в пределах проверенного материала — по правилам M6.

## M1.8. Indicator Assessment, достаточность и качество основания

Indicator Assessment

Indicator Assessment (IA) — итоговый вывод по одному IndicatorID в одной закрытой AS. На пару IndicatorID × AS формируется не более одного итогового IA. Каждый сформированный IA связан с EB той же пары, включая пустой EB.

Допустимые состояния IA: L0, L1, L2, L3, INSUFFICIENT_EVIDENCE. Только L0–L3 являются уровнями. NOT_APPLICABLE не является состоянием IA.

Три различимых исхода на границе оценивания

1.  Обоснованный L0–L3: фактическая возможность и материал позволяют применить соответствующий Level Descriptor. L0 требует собственного прослеживаемого основания и не выводится из простого отсутствия Evidence.

2.  INSUFFICIENT_EVIDENCE: фактическая возможность существовала, но материал не позволяет обосновать ни один L0–L3; причина недостаточности сохраняется.

3.  Отсутствие IA: фактическая возможность не возникла и других достаточных оснований для оценочного вывода нет. Пробел учитывается M7 как покрытие, но не превращается в уровень.

Confidence и Reliability

Confidence — качественная характеристика обоснованности конкретного IA с учётом подтверждающих признаков, альтернативных интерпретаций и ограничений. Confidence не является весом Score и не усредняется в числовую «достоверность» без отдельной нормативной и эмпирической валидации.

Reliability — эмпирически проверяемая воспроизводимость конкретной версии механизма в проверенной области. Она характеризует механизм, а не человека, его Skill или уровень.

Golden Case (GC) — контрольный случай с фиксированным входом и независимо утверждённым экспертным эталоном для проверки конкретной версии механизма. GC, набор GC и фактический прогон проверки различаются; наличие утверждённого GC не означает, что проверка по нему исполнена.

## M1.9. Assessment Cycle, агрегация и результаты оценки

Assessment Cycle и Sessions

Assessment Cycle — один срез оценки одного человека. Он включает 1..N Assessment Sessions и использует один зафиксированный PersonalizedProfile. Принадлежность каждой Session к Cycle определяется до получения её ответов и не выводится из сходства результатов, дат или уровней.

Assessment Session — отдельный организованный эпизод прохождения одной или нескольких AS внутри конкретного Cycle. В Methodology 1.1 штатное завершение Session закрывает Cycle при любом покрытии. Additional Session продолжает только незавершённое прохождение в ещё открытом Cycle; закрытый Cycle не открывается для заполнения пробелов.

Время Cycle

До старта Cycle в плане фиксируются два независимых параметра: бюджет учитываемого времени прохождения и максимальная календарная длительность сбора. Для экспресс-оценки значения по умолчанию — 60 минут и 72 часа соответственно. Это не константы: эффективные значения могут быть переопределены настройками организации, программы или запуска до старта и после старта данного Cycle не меняются. Подробные правила учёта времени принадлежат M7.

Агрегация внутри одного Cycle

Итоговые IA разных AS не сливаются. Для одного IndicatorID внутри Cycle M6 может сформировать допустимый сводный вклад по нескольким исходным IA; такой вклад является производным элементом расчёта и не становится новым Indicator Assessment.

ComponentScore и SkillScore формируются только из допустимых вкладов по правилам M6. Каждый Score обозначается как полный либо частный. Score 0 является существующим числовым результатом и отличается от отсутствующего Score.

SkillScore не преобразуется автоматически в Skill Level. Skill Level может существовать только при отдельно установленном нормативном правиле его формирования; округление или пороги интерфейса таким правилом не являются. Component Level L0–L3 не вводится.

Четыре исхода по Skill

| Исход | Минимальный смысл |
| --- | --- |
| Skill Result + полный SkillScore | Есть Skill Result; все обязательные Components имеют полный ComponentScore и выполнены требования M7 к полному результату. |
| Skill Result + частный SkillScore | Есть допустимый числовой агрегат, но полный обязательный состав либо требования полного результата не обеспечены. |
| Skill Result без SkillScore | Есть минимум один обоснованный итоговый IA L0–L3, допустимый для содержательной интерпретации, но общий числовой агрегат недопустим. |
| Отсутствие Skill Result | Нет ни одного обоснованного итогового IA L0–L3 по Skill, допустимого для содержательной интерпретации. Покрытие, INSUFFICIENT_EVIDENCE, отсутствующие IA и причины сохраняются. |

Минимум существования Skill Result — один обоснованный итоговый IA L0–L3, допустимый для содержательной интерпретации. Допуск этого IA к сводному числовому вкладу и Score проверяется отдельно.

Пять разрезов покрытия

| Разрез | Что считается | Знаменатель |
| --- | --- | --- |
| Фактические возможности | Уникальные IndicatorIDs, для которых возможность фактически возникла хотя бы в одной AS. | Обязательный состав IndicatorIDs выбранной области оценки. |
| Обоснованные IA | Уникальные IndicatorIDs с итоговым обоснованным IA L0–L3. | Тот же состав Indicators. |
| Допустимые сводные вклады | Уникальные IndicatorIDs, по которым M6 допустил сводный вклад в расчёт. | Тот же состав Indicators. |
| Components со Score | Обязательные Components с полным или частным ComponentScore. | Обязательные Components Skill. |
| Полные Components | Обязательные Components с полным ComponentScore. | Тот же состав Components. |

Для каждого разреза сохраняются числитель, знаменатель, включённые и отсутствующие IDs и версия состава. План Cycle и полный состав M2 сохраняются отдельно при различии. Исключение элемента из числового среднего не удаляет его из обязательного состава покрытия.

Results и профили

После закрытия Cycle и завершения расчётов M6 возникает один логический Results данного Cycle, в том числе если ни одного Skill Result не сформировано. Results сохраняет фактическое ядро: AssessedSkillProfile, Competency Profiles, покрытие, ограничения, причины, версии и сведения о закрытии. Один Cycle имеет один логический Results. Пересчёт по допустимым основаниям оформляется как отдельная прослеживаемая расчётная версия с сохранением прежней, причины, источников и правил; разные расчётные версии одного Cycle не являются разными срезами и не открывают сбор новых ответов.

AssessedSkillProfile — представление 0..N фактически сформированных Skill Results одного закрытого Cycle. Competency Profile — группировка Skill Results одной Competency внутри того же профиля; сама группировка не создаёт новый Competency Score или Competency Level.

Разные Cycles одного человека создают отдельные Results и не объединяются для получения нового фактического профиля. Продольное представление сопоставляет отдельные Results только после проверки сопоставимости.

Целевые требования, Skill Gap и Report

RoleProfile → 0..N RoleSkillTargetProfile. Целевой профиль версионируется отдельно, не входит в PersonalizedProfile и не влияет на фактические IA, сводные вклады, Scores или Skill Results.

Skill Gap — отдельное сопоставление фактического Skill Result с Target Requirement того же Skill. Если Target Level задан, но обоснованный фактический Skill Level отсутствует, состояние сравнения — NOT_COMPARABLE даже при полном SkillScore. Score не округляется и не переводится в Target Level автоматически.

Results — фактическое ядро; Report — производное представление конкретной расчётной версии Results для задачи и получателя. Один логический Results может иметь несколько Reports. Каждый Report указывает использованную расчётную версию Results. Изменение визуализации, цели сравнения или Recommendations не меняет фактическое ядро и не создаёт новый Cycle.

Recommendations — производный блок индивидуального Report, основанный на Results, соответствующем Skill Result, зафиксированном PersonalizedProfile и при наличии — допустимом целевом сравнении. Group Report не содержит Recommendations; переход к индивидуальным Reports относится к продуктовому уровню.

Longitudinal Report и Group Report используют отдельные Results и проверяют сопоставимость состава, версий, условий и времени. Assessment Series, Longitudinal Report и Group Report не являются новыми фактическими Results или отдельными верхнеуровневыми сущностями M1.

## M1.10. Сквозные связи и кардинальности

Кардинальности ниже отражают понятийный контракт, а не физическую модель базы данных.

| Связь | Кардинальность / ограничение |
| --- | --- |
| Competency → Skill → Component → Indicator | На каждом переходе 1 → N; каждый дочерний элемент принадлежит одному родителю. |
| Indicator → Level Descriptor | 1 → 4: L0, L1, L2, L3. Evidence Pattern / Red Flag — при наличии, с привязкой к Indicator. |
| RoleProfile → RoleSkillTargetProfile | 1 → 0..N; целевые профили версионируются отдельно и не входят в PersonalizedProfile. |
| OrganizationContext + RoleProfile + UserContext → PersonalizedProfile | Один фиксированный набор применимых версий источников; один RoleProfile внутри PersonalizedProfile данного ролевого контекста. |
| Assessment Cycle → PersonalizedProfile | Каждый Cycle использует ровно один зафиксированный PersonalizedProfile. |
| Assessment Cycle → Assessment Session | 1 → 1..N. Принадлежность Session задаётся до её ответов. |
| Assessment Session → Assessment Situation | 1 → 1..N в фактическом прохождении; AS принадлежит одному Session и одному Cycle. |
| CaseType — Case | Case реализует 1..N CaseType; один CaseType может использоваться в разных Cases. |
| Case → Applicability | 1 → 1..N целевых SkillID / ComponentID в пределах версии Case. |
| Case → IndicatorIDs | 1 → 1..N точных IndicatorIDs с версиями M2; перечень не расширяется по ответам. |
| Case + PersonalizedProfile → Assessment Situation | Каждая AS основана на одном Case и одном зафиксированном PersonalizedProfile; один Case может иметь много AS. |
| AS → проектная Indicator Observability | Для каждого IndicatorID Case AS конкретизирует условия до взаимодействия; M6 отдельно устанавливает факт возникновения возможности. |
| AS → Interaction → Dialogue → Turns | Одно прохождение AS имеет одну трассу Dialogue; Dialogue содержит 1..N Turns, включая одноходовый вариант. |
| User Turn → Fragment → Behavioral Signal | 0..N Fragments на пользовательский Turn; каждый Fragment в одном Turn; 0..N Signals на Fragment; Signal имеет непосредственное основание в одном Fragment. |
| Evidence | Одно Evidence относится ровно к одному IndicatorID и одной AS; Simple или Composite. |
| Evidence Bundle | Один IndicatorID × одна AS; 0..N Evidence; EB может быть пустым и сохраняет связь с AS, исходным Dialogue и условиями независимо от наличия Evidence. |
| Indicator Assessment | 0..1 итоговый IA на IndicatorID × AS; если IA сформирован, он связан ровно с одним EB той же пары. |
| Indicator внутри Cycle | 0..N исходных IA из разных AS; M6 может сформировать 0..1 допустимый сводный вклад для расчёта, который не является IA. |
| Skill Result | 0..1 на Skill внутри одного Cycle; существует только при наличии хотя бы одного обоснованного IA L0–L3, допустимого для интерпретации. Skill Result может иметь 0..1 SkillScore; отсутствие SkillScore не означает отсутствие Skill Result. |
| AssessedSkillProfile | Один профиль на Results; содержит 0..N Skill Results данного Cycle. |
| Cycle → Results | До финализации 0; после закрытия Cycle и завершения расчётов — один логический Results. Для одного логического Results сохраняется прослеживаемая история расчётных версий; другой Cycle создаёт другой Results. |
| Results — Report | Один логический Results может иметь 0..N Reports. Report указывает конкретную расчётную версию; один Report может представлять один либо несколько отдельных Results в M8, не сливая их в новый фактический Results. |

Короткая сквозная цепочка

Сквозная связь задаётся не как обязательный линейный алгоритм, а как система отношений. OrganizationContext + RoleProfile + UserContext → PersonalizedProfile → Assessment Cycle → Session(s) → Assessment Situation(s) → Dialogue → User Turns. Для каждой пары IndicatorID × AS: итоговый IA при формировании связан ровно с одним EB; EB содержит 0..N Evidence и сохраняет связь с AS, Dialogue и условиями; Evidence опирается только на фактически существующие Fragments и Behavioral Signals. Skill Result основан минимум на одном обоснованном IA L0–L3, допустимом для интерпретации, и может иметь 0..1 SkillScore. После закрытия Cycle и завершения расчётов формируется один логический Results с AssessedSkillProfile [0..N Skill Results], Competency Profiles, покрытием и ограничениями; Results представляется через 0..N Reports.

## M1.11. Границы ответственности M2–M8

| Блок / владелец | Содержание и граница |
| --- | --- |
| M2 · Construct | Состав K1–K4, Skills/Components/Indicators, L0–L3, Boundaries, Evidence Patterns, нормативные Red Flags. Не владеет Case, Cycle или фактическими результатами. |
| M3 · RoleProfile | RoleProfile, BaseRoles, версии и ролевую валидность. Связывает RoleProfile с 0..N RoleSkillTargetProfile, но не формирует фактическую оценку. |
| M4 · Context | OrganizationContext, UserContext, PersonalizedProfile, правила источников и фиксации версий. Использование PersonalizedProfile для Recommendations требует отдельного CHECK в M4; M1 не меняет M4 задним числом. |
| M5 · Case & Interaction | CaseType, Case, Applicability, точные IndicatorIDs + версии M2, AS, проектные условия Indicator Observability, ролевые ветви, Dialogue, сценарные границы, допустимость уточнений и QA инструмента. |
| M6 · Evidence & Assessment | Фактическая возможность; Fragments/BS; Simple/Composite Evidence; EB; итоговые IA; сводные вклады, ComponentScore/SkillScore, четыре исхода Skill Result; Confidence, Reliability, GC и QA механизма. Не определяет принадлежность Sessions к Cycle. |
| M7 · Assessment Cycle | Cycle и Sessions, принадлежность до ответов, план и покрытие, подбор/маршрут, решение об уточнениях, время, паузы, продолжение и закрытие. Не присваивает L и не заменяет M6 в расчётах. |
| M8 · Results & Reports | Results закрытого Cycle, AssessedSkillProfile/Competency Profile, RoleSkillTargetProfile/Skill Gap, Recommendations как блок Report, индивидуальные/продольные/групповые представления и проверка сопоставимости. Не создаёт новые IA и не пересчитывает M6 ради удобства отчёта. |

Тематический блок может конкретизировать структуру, поля и процедуры, но изменение базового смысла или связи M1 требует новой версии M1 и Change & Impact по M0.

## Appendix A. Ontology Map

### A.1. Сквозная карта

CONSTRUCT: Competency → Skill → Component → Indicator → L0–L3 / Evidence Pattern / Red Flag

CONTEXT: OrganizationContext + RoleProfile + UserContext → PersonalizedProfile; RoleProfile → 0..N RoleSkillTargetProfile

INSTRUMENT: CaseType(s) → Case [Applicability + точные IndicatorIDs и версии M2] + PersonalizedProfile → Assessment Situation [проектная Indicator Observability]

ORGANIZATION: Assessment Cycle [один человек + один зафиксированный PersonalizedProfile] → 1..N Sessions → 1..N AS

INTERACTION: AS → Assessment Interaction → Dialogue → Turns

OBSERVATION: User Turn → Fragment → Behavioral Signal

EVIDENCE & IA: для каждой пары IndicatorID × AS формируется EB [0..N Evidence], связанный с AS, исходным Dialogue и условиями. Evidence при наличии — Simple / Composite и опирается на фактические Fragments / Behavioral Signals. Сформированный итоговый IA → ровно один EB; пустой EB допустим.

AGGREGATION: исходные IA одного Indicator внутри Cycle могут дать 0..1 допустимый сводный вклад; допустимые вклады могут формировать ComponentScore и SkillScore. Skill Result существует при наличии ≥1 обоснованного IA L0–L3, допустимого для интерпретации, и может иметь полный SkillScore, частный SkillScore либо не иметь SkillScore. Отсутствие Skill Result — отдельный исход по целевому Skill, а не разновидность существующего Skill Result.

RESULTS: закрытый Cycle + завершённые расчёты → один логический Results → AssessedSkillProfile [0..N Skill Results] + Competency Profiles + покрытие / ограничения → 0..N Reports. Пересчёт создаёт прослеживаемую расчётную версию того же логического Results, а не новый Cycle или новый фактический срез.

TARGET: RoleProfile → 0..N RoleSkillTargetProfile. Target Requirement сопоставляется с фактическим Skill Level при установленной сопоставимости; при отсутствии Skill Result или обоснованного Skill Level сохраняется NOT_COMPARABLE без фиктивного результата. Recommendations используют Results + зафиксированный PersonalizedProfile и, при наличии, допустимое целевое сравнение.

### A.2. Архитектурные инварианты

1.  Один Cycle — один срез одного человека; разные Cycles не объединяются для нового фактического профиля.

2.  Case задаёт точные IndicatorIDs до взаимодействия; AS не выбирает новый перечень по ответам.

3.  Проектная Indicator Observability, фактическая возможность, Evidence и IA различаются.

4.  Fragment существует только внутри одного пользовательского Turn; системные Turns остаются условиями интерпретации.

5.  Используются Simple и Composite Evidence; временная последовательность является возможной частью Composite, отдельного Trajectory Evidence нет.

6.  EB и итоговый IA ограничены одной парой IndicatorID × AS; каждый сформированный IA связан с EB, в том числе пустым.

7.  Обоснованный L0, INSUFFICIENT_EVIDENCE и отсутствие IA — разные исходы.

8.  Сводный вклад Indicator и Scores не являются новыми IA.

9.  Score 0 отличается от отсутствующего Score; Score не превращается автоматически в Skill Level или Component Level.

10.  Пять разрезов покрытия сохраняются независимо; исключение из среднего не удаляет элемент из обязательного состава.

11.  Confidence относится к обоснованности IA; Reliability — к проверенной версии механизма.

12.  GC и фактический прогон проверки не тождественны.

13.  Один Cycle имеет один логический Results; расчётные версии одного Results прослеживаются отдельно. Report и Recommendations не изменяют фактическое ядро и не открывают новый сбор.

14.  RoleSkillTargetProfile не входит в PersonalizedProfile и не влияет на фактическую оценку.

15.  Без обоснованного Skill Level сравнение с Target Level остаётся NOT_COMPARABLE, даже при наличии полного SkillScore.

## Appendix B. Change & Impact

### B.1. Основные изменения v1.3 → v1.4 FROZEN

| Область | Изменение | Impact / зависимость |
| --- | --- | --- |
| M1.1–M1.2 | Assessment Cycle и Session включены как отдельный организационный слой; M7 переименован по фактической зоне ответственности. | HARD: M7 v1.3; CHECK: M8. |
| M1.5 | Case теперь является источником точных IndicatorIDs и версий M2; AS сохраняет перечень и конкретизирует Observability. | Закрывает M1-14-04; HARD-проверка согласованности M5 v1.1 / M1 выполнена документно. |
| M1.6 | Разведены конец сценария, закрытие AS/Dialogue, пауза и закрытие Cycle; единый Dialogue → Turns сохранён. | HARD: M5/M7; CHECK: M6. |
| M1.7 | Trajectory Evidence исключён; последовательность и изменение поведения входят в Composite. Fragment локализован в одном пользовательском Turn. | Закрывает M1-14-01 и M1-14-02; HARD/CHECK M6. |
| M1.8 | IA формируется после закрытия AS; IA → EB обязательна, EB может быть пустым; уточнены L0 / INSUFFICIENT_EVIDENCE / отсутствие IA; добавлены границы Confidence / Reliability / GC. | Закрывает M1-14-03; HARD-проверка согласованности M6/M7 выполнена документно. |
| M1.9 | Введены Results, привязанные к Cycle, четыре исхода Skill Result, полный/частный Score, пять разрезов покрытия, правило Score ≠ Level, отдельность целевого сравнения и фактического ядра. | HARD-проверка согласованности M6 v1.8 / M7 v1.3 выполнена документно; CHECK M8 v1.2 REVIEW. |
| M1.9 Results | Results — один логический факт закрытого Cycle; Reports/Recommendations производны; разные Cycles не сливаются. | CHECK M8 v1.2 REVIEW; добавлено прослеживаемое версионирование расчёта без новой верхнеуровневой сущности. |
| M1.10 | Кардинальности дополнены Cycle, Sessions, точные IndicatorIDs, IA→EB, сводным вкладом и Results. | HARD-проверка согласованности M5–M8 выполнена документно в затронутом контракте. |
| M1.11 | Границы M5–M8 актуализированы по FROZEN M5/M6/M7 и REVIEW M8. | Change & Impact по M0. |
| M4 dependency | Использование зафиксированного PersonalizedProfile в Recommendations оставлено отдельным CHECK для M4. | OPEN CHECK · OwnerChat M4. |
| Excluded | RedFlagObservability и Critical Constraint Violation не введены. | Остаются вне нормативного содержания до отдельного решения. |
| QA 01.10.2026 | Исправлены карта и опциональные пути результата; добавлено версионирование расчёта Results; восстановлены контекстные границы и определения EP/Boundary/RF/GC; уточнены доказанное невыполнение, Group Report и адресный QA QA01–QA17. | Документная проверка согласованности M5 v1.1 / M6 v1.8 / M7 v1.3 / M8 v1.2 REVIEW — PASS в затронутой области. Продуктные, GC и пилотные прогоны — NOT_RUN. |

### B.2. Статусы исходных документов

| Источник | Статус, использованный в этой сверке |
| --- | --- |
| M1 v1.3 | FROZEN; исходный файл не изменяется. CURRENT проверяется отдельно по M0. |
| M2 K1/K2/K3/K4 | M2.K1 v1.1; M2.K2 v1.0; M2.K3 v1.1; M2.K4 v1.0 — FROZEN паспорта и матрицы; конкретная версия Indicator сохраняется в Case/Cycle. |
| M3.RoleProfile v1.0 | FROZEN. |
| M4.Context v1.0 | FROZEN; CHECK по последующему использованию PersonalizedProfile для Recommendations остаётся отдельной зависимостью. |
| M5 v1.1 | FROZEN; CURRENT=NO в исходном файле. |
| M6 v1.8 | FROZEN; CURRENT=NO в исходном файле. |
| M7 v1.3 | FROZEN; CURRENT=NO в исходном файле. |
| M8 v1.2 | REVIEW; CURRENT=NO. |
| M1 v1.4 | FROZEN; CURRENT=NO. Зафиксирован 01.10.2026 по решению владельца после исправлений QA. Публикация по M0 выполняется отдельно. |

## Appendix C. QA и приёмка FROZEN

### C.1. Трассировка требований ТЗ

Сопоставление с исходным ТЗ M1 01–M1 07: M1 01 → R1; M1 02 → R1 и R7; M1 03 → R2; M1 04 → R3; M1 05 → R5 и R6; M1 06 → R1 и R4; M1 07 → R7 и межмодульную проверку согласованности. R1–R7 являются группировкой последнего ТЗ и не заменяют исходные идентификаторы требований.

| ID | Изменённые пункты M1 | Документная проверка | Результат / остаток |
| --- | --- | --- | --- |
| R1 Cycle · M1 01/02/06 | M1.2, M1.4, M1.9, M1.10, App.A | Один человек; 1..N Sessions; один зафиксированный PersonalizedProfile; принадлежность Session до ответов; один Results; разные Cycles. | PASS документа; продуктный прогон NOT_RUN. |
| R2 Case/Observability · M1 03 | M1.5, M1.10, App.A | Applicability Skill/Component; точные IndicatorIDs + версии M2 в Case; AS конкретизирует условия; M6 проверяет фактическую возможность; расширения по ответам нет. | PASS документа; существующие Cases требуют собственной миграции/QA. |
| R3 Observation/Evidence · M1 04 | M1.6–M1.8 | Fragment только в пользовательском Turn; Simple/Composite; Trajectory отсутствует; EB/IA Indicator×AS; пустой EB; без фиктивных Evidence; L0 / INSUFFICIENT_EVIDENCE / отсутствие IA различены. | PASS документа; прогон механизма NOT_RUN. |
| R4 Завершение и время · M1 06 | M1.6, M1.9 | Конец сценария ≠ закрытие AS ≠ пауза ≠ закрытие Cycle; итоговый IA после закрытия AS; уточнения M7; штатная Session закрывает Cycle; 60/72 — значения по умолчанию. | PASS документа; пилот времени NOT_RUN. |
| R5 Scores и четыре исхода · M1 05 | M1.9, M1.10 | Полный / частный / без Score / отсутствие Skill Result; минимум Skill Result = обоснованный IA; Score 0 ≠ отсутствие; Score ≠ Skill Level. | PASS документа; расчётный прогон NOT_RUN. |
| R6 Покрытие и качество основания · M1 05 | M1.8–M1.10 | Пять разрезов; IDs/знаменатели/версии; план отдельно от полного M2; Confidence не вес; Reliability относится к механизму; GC ≠ прогон. | PASS документа; прогон GC NOT_RUN. |
| R7 Results, целевые требования и отчёты · M1 02/07 | M1.9–M1.11 | Results ≠ Report; 0..N целевых профилей; NOT_COMPARABLE без Skill Level; Recommendations через Results + PersonalizedProfile; Group Report без Recommendations; новых верхнеуровневых сущностей нет. | PASS документа; CHECK M4 по Recommendations остаётся OPEN. |

### C.2. Закрытие backlog M1-14

| Backlog | Решение v1.4 | Статус |
| --- | --- | --- |
| M1-14-01 · типы Evidence | Оставлены Simple и Composite; временная последовательность включена в Composite; Trajectory исключён. | CLOSED: документная согласованность подтверждена; продуктный прогон NOT_RUN. |
| M1-14-02 · источник Fragment | Fragment только в одном пользовательском Turn; системный материал — контекст. | CLOSED: документная согласованность подтверждена; правило доказанного невыполнения уточнено в M1.6–M1.7. |
| M1-14-03 · завершение / итоговый IA | Разведены scenario / AS / pause / Cycle; итоговый IA после закрытия AS; уточнения остаются в том же Dialogue; промежуточный разбор не создаёт IA. | CLOSED: документная согласованность подтверждена; сквозной прогон NOT_RUN. |
| M1-14-04 · источник IndicatorIDs | Case v1.1 является источником точных IndicatorIDs + версий M2; AS конкретизирует Observability; M6 не расширяет перечень. | CLOSED на стороне M1 по M5 v1.1 + M6 v1.8; миграция существующих Cases остаётся отдельной задачей. |

### C.3. Контрольные случаи QA01–QA17

| ID | Контрольный вход | Ожидаемый результат | Статус |
| --- | --- | --- | --- |
| QA01 | 2 Sessions одного Cycle; затем новая самостоятельная оценка. | Первые Sessions → один Results; новая оценка → новый Cycle и отдельный Results; EB/IA остаются в границах AS. | PASS документа / продуктный прогон NOT_RUN. |
| QA02 | C1: I1=2, I2=3, I3 без вклада; C2: I4=1, I5/I6 без допустимых вкладов; по I5 есть отдельный обоснованный IA; C3: I7–I9 без вкладов. | C1=2,5 частный; C2=1 частный; C3 без Score; SkillScore=(2,5+1)/2=1,75 частный. Обоснованные IA 4/9; допустимые вклады 3/9; Components со Score 2/3; полные 0/3. Плоское среднее 2 не применяется. | PASS документа; арифметика PASS / продуктный прогон NOT_RUN. |
| QA03 | Единственный допустимый вклад L0; отдельно — только INSUFFICIENT_EVIDENCE или отсутствие IA. | В первом случае возможны частный Score 0 и Skill Result; во втором Score и Skill Result отсутствуют, причины и покрытие сохраняются. | PASS документа / продуктный прогон NOT_RUN. |
| QA04 | Есть IA, обоснованные для интерпретации, но нет допустимого общего вклада и ComponentScore. | Skill Result без SkillScore; не смешивается с частным Score и отсутствием Skill Result. | PASS документа / продуктный прогон NOT_RUN. |
| QA05 | Все Components имеют число, но один ComponentScore частный; сокращённый план выполнен. | SkillScore остаётся частным; полнота плана и полный состав M2 различаются; Skill Level автоматически не выводится. | PASS документа / продуктный прогон NOT_RUN. |
| QA06 | Пустой EB при возникшей возможности; отдельно — невозникшая возможность; отдельно — пауза. | Сформированный IA связан с EB даже при пустом составе Evidence; нет возможности и иных оснований → нет IA; пауза → нет итогового IA. | PASS документа / продуктный прогон NOT_RUN. |
| QA07 | До старта заданы 45 минут и 48 часов; после 20 минут — прерывание; настройки изменены на 90 минут и 96 часов. | Остаётся 25 минут и исходный срок 48 часов; продолжение допустимо только в открытом незавершённом Cycle. | PASS документа; арифметика PASS / продуктный прогон NOT_RUN. |
| QA08 | Штатное завершение с неполным покрытием; позднее M6 исключает вклад. | Cycle остаётся закрытым; пересчёт оформляется прослеживаемой расчётной версией того же Results, без нового сбора или Additional Session. | PASS документа / продуктный прогон NOT_RUN. |
| QA09 | Confidence ограничен; Reliability использованной версии механизма не проверена. | Качественные ограничения явны; нет вымышленного процента достоверности; протокол другой версии не наследуется. | PASS документа / прогон GC и продукта NOT_RUN. |
| QA10 | SkillScore=2,4; Target Level=L2; нормативного правила Skill Level нет. | NOT_COMPARABLE; нет округления в L2, MEETS_TARGET или ABOVE_TARGET. | PASS документа / продуктный прогон NOT_RUN. |
| QA11 | Одинаковые Scores при разном составе и времени; Group Report включает все четыре исхода. | Сопоставимость проверяется отдельно; автоматического равенства/динамики нет; N, n, исходы и исключения сохраняются в M8. | PASS документа по M8 REVIEW / продуктный прогон NOT_RUN. |
| QA12 | Case содержит точные IndicatorIDs; вывод зависит от последовательности Turns одной AS. | AS конкретизирует условия по заданным IDs; последовательность входит в Composite Evidence; отдельного Trajectory Evidence нет. | PASS документа / продуктный прогон NOT_RUN. |
| QA13 | Для одного разреза покрытия знаменатель пуст; отдельно — счётчик не передан. | Пустой знаменатель не трактуется как 100%; неизвестный счётчик не подставляется как 0. Подробное представление остаётся в M8. | PASS границы M1 / продуктный прогон NOT_RUN. |
| QA14 | Cycle закрыт, итоговая обработка M6 продолжается. | Окончательный Results ещё не сформирован; ожидание расчёта не подменяется Score 0, INSUFFICIENT_EVIDENCE или отсутствием Skill Result. | PASS документа / продуктный прогон NOT_RUN. |
| QA15 | Есть блокирующее ожидание, фоновая работа AI и разрешённая пауза. | M1 сохраняет два параметра времени и делегирует детальный учёт M7; блокирующее ожидание и пауза не создают новые оценочные состояния. | PASS границы M1 против M7 / продуктный прогон NOT_RUN. |
| QA16 | Один Indicator имеет несколько AS; один вклад исключён из среднего. | Повторы не увеличивают число уникальных покрытых IndicatorIDs; исключение из среднего не удаляет Indicator из обязательного состава покрытия. | PASS документа / продуктный прогон NOT_RUN. |
| QA17 | M6 доказал невыполнение по полному релевантному Dialogue; отдельно AS окончательно прекращена. | Доказанное невыполнение допускает обоснованный L0 без фиктивного Turn/Fragment/BS; прекращение само по себе не выбирает IA. | PASS документа / продуктный прогон NOT_RUN. |

PASS в Appendix C означает документную согласованность M1 v1.4 FROZEN с прочитанными контрактами и ТЗ в проверенной области. Выполнены адресная проверка текста, карты, кардинальностей и синтетической арифметики QA02/QA07; обратная проверка согласованности M5 v1.1 / M6 v1.8 / M7 v1.3 / M8 v1.2 REVIEW по затронутому понятийному контракту — PASS. Это не подтверждение работы продукта, не фактический прогон M6–M8, не проверка Reliability и не приёмка на утверждённых GC. Непроведённые сквозные, продуктные и эмпирические проверки имеют статус NOT_RUN.

Условия фиксации FROZEN: замечания QA Q1–Q7 устранены; M1-14-01–04 закрыты на уровне документной согласованности; существенные HARD-зависимости с M5/M6/M7 проверены; владелец M1 01.10.2026 утвердил статус FROZEN. OPEN CHECK M4 по последующему использованию PersonalizedProfile для Recommendations сохраняется как интеграционная зависимость и не считается автоматически закрытым этой версией. M8 v1.2 остаётся REVIEW и используется только в заявленном статусе.

Условия публикации CURRENT: FROZEN-файл должен быть отдельно опубликован в Sources, Registry и CURRENT Manifest по M0. До этой операции CURRENT=NO; предыдущая версия не переводится в SUPERSEDED автоматически. Продуктные прогоны, GC и пилот остаются NOT_RUN и не подменяются документным QA.

## Appendix D. Основания сверки

Основания: M0 v1.0 FROZEN; M1 v1.3 FROZEN; M2.K1 v1.1, M2.K2 v1.0, M2.K3 v1.1, M2.K4 v1.0 FROZEN; M3.RoleProfile/BaseRoles v1.0 FROZEN; M4.Context v1.0 FROZEN; M5 v1.1 FROZEN; M6 v1.8 FROZEN; M7 v1.3 FROZEN; M8 v1.2 REVIEW; backlog M1/M4, ТЗ синхронизации 30.09.2026 и повторный QA M1 v1.4 от 01.10.2026.
