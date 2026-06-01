export const APP_RELEASE = "1.2.12";
export const PROFILE_NO_CHANGES_LABEL = "Профиль актуален";
export const PROFILE_NO_CHANGES_MESSAGE = "Профиль актуален";

export const ADMIN_PHONE = "89001000000";
export const PROFILE_HISTORY_PAGE_SIZE = 10;
export const ADMIN_REPORTS_PAGE_SIZE = 10;
export const ADMIN_METHODOLOGY_RISK_PAGE_SIZE = 10;
export const ADMIN_METHODOLOGY_CASES_PAGE_SIZE = 10;

export const processingAgentsBlueprint = [
    {
        id: "communication",
        title: "Агент коммуникации",
        focus: "Проверяет ясность, эмпатию, вопросы и согласование позиции.",
    },
    {
        id: "teamwork",
        title: "Агент командной работы",
        focus: "Анализирует распределение ролей, координацию и работу с командой.",
    },
    {
        id: "creativity",
        title: "Агент креативности",
        focus: "Ищет альтернативы, оригинальные идеи и гибкость мышления.",
    },
    {
        id: "critical",
        title: "Агент критического мышления",
        focus: "Оценивает критерии, риски, гипотезы и принятие решений.",
    },
];

export const processingPhases = [
    "Извлекаем релевантные фрагменты ответов пользователя по кейсам.",
    "Сопоставляем ответы с рубриками уровней и структурными признаками.",
    "Проверяем красные флаги и итоговые уровни по каждому навыку.",
    "Формируем итоговый профиль и подготавливаем результаты для интерфейса.",
];

export const loaderFlows = {
    lookupUser: [
        {
            label: "Ищем профиль пользователя",
            description:
                "Проверяем, есть ли пользователь в базе данных по номеру телефона.",
        },
        {
            label: "Готовим сценарий входа",
            description:
                "Определяем, нужно ли создать нового пользователя или актуализировать текущий профиль.",
        },
        {
            label: "Открываем следующий шаг",
            description:
                "Подготавливаем экран с агентом и состояние пользовательской сессии.",
        },
    ],
    createOrUpdateProfile: [
        {
            label: "Очищаем и нормализуем данные",
            description:
                "Приводим текст обязанностей и сферы деятельности к структурированному виду.",
        },
        {
            label: "Сохраняем выбранную роль",
            description:
                "Фиксируем роль, которую пользователь выбрал из списка при регистрации или обновлении профиля.",
        },
        {
            label: "Формируем расширенный профиль",
            description:
                "Собираем рабочий контекст пользователя для персонализации и дальнейшей оценки.",
        },
        {
            label: "Подготавливаем следующий экран",
            description:
                "Завершаем профиль и открываем следующий экран без лишнего ожидания.",
        },
    ],
    startAssessment: [
        {
            label: "Проверяем профиль оценки",
            description:
                "Уточняем активную роль и состояние текущей assessment-сессии пользователя.",
        },
        {
            label: "Подбираем релевантные кейсы",
            description:
                "При необходимости выбираем набор кейсов, покрывающий нужные навыки без лишних повторов.",
        },
        {
            label: "Персонализируем материалы",
            description:
                "При необходимости подставляем рабочий контекст пользователя в шаблоны кейсов.",
        },
        {
            label: "Генерируем системные промты",
            description:
                "При необходимости создаем промты для ведения интервью и записываем их в сессию.",
        },
        {
            label: "Подготавливаем интервью",
            description:
                "Открываем текущий или первый готовый кейс для ответа пользователя.",
        },
    ],
};

export const levelPercentMap = {
    L1: 45,
    L2: 70,
    L3: 92,
    "N/A": 0,
};

export const competencyOrder = [
    "Коммуникация",
    "Командная работа",
    "Креативность",
    "Критическое мышление",
];

export const levelThresholds = [
    { code: "L1", value: levelPercentMap.L1 },
    { code: "L2", value: levelPercentMap.L2 },
    { code: "L3", value: levelPercentMap.L3 },
];

export const competencyPalette = {
    Коммуникация: {
        stroke: "#4648d4",
        fill: "rgba(70, 72, 212, 0.1)",
        chartFill: "#4648d4",
    },
    "Командная работа": {
        stroke: "#16a34a",
        fill: "rgba(22, 163, 74, 0.1)",
        chartFill: "#16a34a",
    },
    Креативность: {
        stroke: "#ea580c",
        fill: "rgba(234, 88, 12, 0.11)",
        chartFill: "#ea580c",
    },
    "Критическое мышление": {
        stroke: "#7c3aed",
        fill: "rgba(124, 58, 237, 0.11)",
        chartFill: "#7c3aed",
    },
};

export const fallbackCompetencyPalette = {
    stroke: "#64748b",
    fill: "rgba(100, 116, 139, 0.08)",
    chartFill: "#64748b",
};

export const onboardingSteps = [
    {
        step: "Шаг 01",
        progressIndex: 0,
        title: "Познакомьтесь с AI-ассистентом",
        description:
            "Мульти-агентная система анализирует ответы и помогает быстро собрать профиль сотрудника для дальнейшей оценки компетенций.",
        features: [
            {
                icon: "/web/assets/icons/deep-analysis-icon.svg",
                title: "Глубокий анализ",
                text: "Система смотрит на ход рассуждений, аргументы и связи между решениями.",
            },
            {
                icon: "/web/assets/icons/specialized-agents-icon.svg",
                title: "Специализированные агенты",
                text: "Отдельные агенты фокусируются на разных компетенциях и собирают общий профиль.",
            },
        ],
        visual: '<div class="visual-grid"><div class="visual-card visual-main">Assistant v2.0</div><div class="visual-card">Аналитика</div><div class="visual-card muted"><span></span><span></span></div><div class="visual-chip"></div></div>',
    },
    {
        step: "Шаг 02",
        progressIndex: 1,
        title: "Решайте реальные\nкейсы",
        description:
            "После регистрации вы получите практические задачи и сможете отвечать в свободной форме, без тестов и шаблонов.",
        features: [
            {
                icon: "/web/assets/icons/free-form-writing-icon.svg",
                title: "Свободная форма",
                text: "Вы описываете решение своими словами, как в рабочей переписке или разборе задачи.",
            },
            {
                icon: "/web/assets/icons/mind-icon.svg",
                title: "Рабочий контекст",
                text: "Кейсы подаются как практические ситуации, где важны приоритеты, риски и логика действий.",
            },
        ],
        visual: '<div class="case-visual"><div class="case-bubble">Ассистент: Как бы вы оптимизировали логистику при росте спроса на 40%?</div><div class="case-sheet"><span></span><span></span></div><div class="case-progress">Пишу решение...</div></div>',
    },
    {
        step: "Шаг 03",
        progressIndex: 2,
        title: "Получите профиль компетенций",
        description:
            "Система оценит ваши навыки по модели 4K и сформирует персональный отчет с глубокой аналитикой потенциала.",
        features: [
            {
                icon: "/web/assets/icons/sparkles-icon.svg",
                title: "AI-интерпретация",
                text: "Ассистент выделяет сильные стороны, зоны роста и устойчивые паттерны решений.",
            },
            {
                icon: "/web/assets/icons/file-icon.svg",
                title: "Детальный отчет",
                text: "В финале вы видите профиль 4K с уровнями компетенций и рекомендациями по развитию.",
            },
        ],
        visual: '<div class="radar-visual"><div class="radar-ring radar-ring-outer"></div><div class="radar-ring radar-ring-middle"></div><div class="radar-ring radar-ring-inner"></div><div class="radar-shape"></div><span>Креативность</span><span>Коммуникация</span><span>Критическое мышление</span><span>Командная работа</span></div>',
        finalButton: "Перейти к профилю",
    },
];

export const staticAssessments = [
    {
        title: "MBTI Profile",
        description:
            "Типология личности Майерс-Бриггс для понимания командной динамики.",
        duration: "20 минут",
        tone: "warm",
    },
];
