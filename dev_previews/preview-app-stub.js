(function () {
  const params = new URLSearchParams(window.location.search);
  const requestedScreen = params.get('screen') || 'auth';
  const appScreen = requestedScreen
    .replace('admin-methodology-passports', 'admin-methodology')
    .replace('admin-methodology-library', 'admin-methodology')
    .replace('admin-methodology-branches', 'admin-methodology')
    .replace('admin-prompt-lab-cases', 'admin-prompt-lab')
    .replace('admin-prompt-lab-dialog', 'admin-prompt-lab');

  const user = {
    id: 35,
    full_name: 'Мария Крылова',
    phone: '+7 900 100 00 00',
    email: 'maria@example.com',
    telegram: '@maria_product',
    job_description: 'Руководитель продукта',
    company_industry: 'B2B SaaS',
    raw_duties: 'Roadmap, discovery, запуск функций, синхронизация команд.',
  };

  const adminUser = {
    id: 1,
    full_name: 'Администратор системы',
    phone: '89001000000',
    email: 'admin@agent4k.local',
    job_description: 'Администратор',
    company_industry: '4K Assistant',
  };

  const dashboard = {
    greeting_name: 'Мария',
    active_assessment: {
      title: 'Компетенции 4К',
      description: 'Продолжите ассессмент: осталось два кейса и итоговая аналитика.',
      progress_percent: 60,
      completed_cases: 3,
      total_cases: 5,
      button_label: 'Продолжить',
    },
    available_assessments: [
      {
        title: 'Оценка 4К компетенций',
        description: 'Кейсовое интервью по коммуникации, кооперации, креативности и критическому мышлению.',
        duration_minutes: 45,
        status: 'Доступно',
      },
    ],
    reports_total: 2,
    reports: [],
  };

  const competencyAverage = [
    { label: 'Коммуникация', value: 82 },
    { label: 'Командная работа', value: 71 },
    { label: 'Креативность', value: 68 },
    { label: 'Критическое мышление', value: 75 },
  ];

  const adminDashboard = {
    title: 'Сводный отчет',
    subtitle: 'Комплексный анализ компетенций и ключевых метрик платформы.',
    metrics: [
      { label: 'Пользователи', value: '128', delta: '+14 за период' },
      { label: 'Завершено', value: '86', delta: '+9 за период' },
      { label: 'Средний 4K score', value: '76%', delta: '+4 п.п.' },
      { label: 'Активные сессии', value: '17', delta: 'сегодня' },
    ],
    competency_average: competencyAverage,
    mbti_distribution: [
      { label: 'ENTJ', value: 24 },
      { label: 'INTJ', value: 18 },
      { label: 'ENFP', value: 14 },
      { label: 'ISTJ', value: 11 },
    ],
    insights: [
      { title: 'Коммуникация лидирует', description: 'Средний уровень выше остальных компетенций на 8 п.п.' },
      { title: 'Критическое мышление растет', description: 'Новые кейсы дают больше evidence по анализу рисков.' },
      { title: 'Есть дефицит данных', description: 'Для лидерских ролей нужно больше завершенных сессий.' },
    ],
    activity_period_key: '30d',
    activity_period_label: 'Последние 30 дней',
    activity: [
      { label: '18 апр', value: 4 },
      { label: '25 апр', value: 7 },
      { label: '02 май', value: 9 },
      { label: '09 май', value: 11 },
      { label: '15 май', value: 8 },
    ],
  };

  const adminMethodology = {
    title: 'Библиотека кейсов',
    subtitle: 'Настройка библиотеки кейсов, веток тестирования и покрытия навыков.',
    metrics: [
      { label: 'Кейсов в базе', value: '42', delta: '31 ready' },
      { label: 'Паспорта типов', value: '9', delta: '7 активных' },
      { label: 'Покрытие навыков', value: '91%', delta: '+6 п.п.' },
    ],
    passports: [
      {
        type_code: 'PRIORITY_CONFLICT',
        type_name: 'Конфликт приоритетов',
        artifact_name: 'Trade-off memo',
        status: 'ready',
        interactivity_mode: 'Диалог',
        recommended_answer_length: '250-400 слов',
        selection_tags: ['prioritization', 'stakeholders', 'risk'],
        roles: ['Менеджер', 'Лидер'],
        ready_cases_count: 6,
        required_blocks_count: 5,
        red_flags_count: 4,
      },
      {
        type_code: 'UNCERTAIN_LAUNCH',
        type_name: 'Запуск при неполных данных',
        artifact_name: 'План эксперимента',
        status: 'ready',
        interactivity_mode: 'Письменный ответ',
        recommended_answer_length: '300-500 слов',
        selection_tags: ['hypothesis', 'data', 'decision'],
        roles: ['Линейный', 'Менеджер'],
        ready_cases_count: 5,
        required_blocks_count: 6,
        red_flags_count: 3,
      },
      {
        type_code: 'TEAM_RETRO',
        type_name: 'Командная ретроспектива',
        artifact_name: 'План улучшений',
        status: 'draft',
        interactivity_mode: 'Ситуационный кейс',
        recommended_answer_length: '200-350 слов',
        selection_tags: ['teamwork', 'trust', 'growth'],
        roles: ['Лидер'],
        ready_cases_count: 2,
        required_blocks_count: 4,
        red_flags_count: 5,
      },
    ],
    cases: [
      {
        case_id_code: 'CASE-PRD-01',
        title: 'Запуск функции при конфликте приоритетов',
        status: 'ready',
        qa_ready: true,
        passed_checks: 8,
        total_checks: 8,
        roles: ['Менеджер', 'Лидер'],
        skills: ['Ясность коммуникации', 'Принятие решений', 'Анализ информации'],
        difficulty_level: 'hard',
        estimated_time_min: 12,
        interactivity_mode: 'Диалог',
        recommended_answer_length: '250-400 слов',
        expected_artifact: 'Trade-off memo',
        selection_tags: ['roadmap', 'stakeholders', 'risk'],
      },
      {
        case_id_code: 'CASE-OPS-07',
        title: 'Срыв сроков в кросс-функциональной команде',
        status: 'ready',
        qa_ready: true,
        passed_checks: 7,
        total_checks: 8,
        roles: ['Лидер'],
        skills: ['Организация взаимодействия', 'Формирование доверия'],
        difficulty_level: 'base',
        estimated_time_min: 10,
        interactivity_mode: 'Письменный ответ',
        recommended_answer_length: '200-350 слов',
        expected_artifact: 'План синхронизации',
        selection_tags: ['teamwork', 'delivery'],
      },
      {
        case_id_code: 'CASE-DATA-03',
        title: 'Новая гипотеза без достаточных данных',
        status: 'draft',
        qa_ready: false,
        passed_checks: 5,
        total_checks: 8,
        roles: ['Линейный', 'Менеджер'],
        skills: ['Гибкость мышления', 'Анализ информации'],
        difficulty_level: 'base',
        estimated_time_min: 9,
        interactivity_mode: 'Диалог',
        recommended_answer_length: '250-400 слов',
        expected_artifact: 'План проверки гипотезы',
        selection_tags: ['hypothesis', 'metrics'],
      },
    ],
    branches: [
      { role_name: 'Линейный', case_count: 14, ready_case_count: 11, skill_coverage_percent: 86, competency_coverage_percent: 100 },
      { role_name: 'Менеджер', case_count: 16, ready_case_count: 13, skill_coverage_percent: 93, competency_coverage_percent: 100 },
      { role_name: 'Лидер', case_count: 12, ready_case_count: 7, skill_coverage_percent: 76, competency_coverage_percent: 75 },
    ],
    coverage: [
      { competency_name: 'Коммуникация', linear_value: '4/4', manager_value: '4/4', leader_value: '3/4' },
      { competency_name: 'Командная работа', linear_value: '3/3', manager_value: '3/3', leader_value: '2/3' },
      { competency_name: 'Креативность', linear_value: '3/3', manager_value: '3/3', leader_value: '3/3' },
      { competency_name: 'Критическое мышление', linear_value: '4/4', manager_value: '4/4', leader_value: '3/4' },
    ],
    skill_gaps: [
      { skill_name: 'Лидерство и поддержка роста команды', role_name: 'Лидер', competency_name: 'Командная работа', ready_case_count: 1, severity: 'critical' },
      { skill_name: 'Оценка и реализация идей', role_name: 'Лидер', competency_name: 'Креативность', ready_case_count: 1, severity: 'warning' },
    ],
    single_point_skills: [
      { skill_name: 'Принятие решений', competency_name: 'Критическое мышление', type_codes: ['PRIORITY_CONFLICT'], role_names: ['Менеджер', 'Лидер'], ready_case_count: 1 },
    ],
    case_quality_hotspots: [
      {
        title: 'Новая гипотеза без достаточных данных',
        case_id_code: 'CASE-DATA-03',
        type_code: 'UNCERTAIN_LAUNCH',
        issue_label: 'Часто требует уточнения формулировки задачи',
        assessments_count: 8,
        avg_red_flag_count: 1.4,
        avg_missing_blocks_count: 1.8,
        avg_block_coverage_percent: 68,
        low_level_rate_percent: 37,
      },
    ],
  };

  const adminReports = {
    title: 'Отдельные отчеты',
    subtitle: 'Управление и анализ индивидуальных результатов тестирования персонала.',
    items: [
      { session_id: 501, user_id: 35, full_name: 'Мария Крылова', group_name: 'Product', role_name: 'Руководитель продукта', status: 'Завершено', score_percent: 78, mbti_type: 'ENTJ', report_date: '2026-05-12T10:00:00', phone: '+7 900 100 00 00' },
      { session_id: 502, user_id: 36, full_name: 'Илья Петров', group_name: 'Analytics', role_name: 'Аналитик', status: 'Завершено', score_percent: 83, mbti_type: 'INTJ', report_date: '2026-05-10T12:30:00', phone: '+7 900 200 00 00' },
      { session_id: 503, user_id: 37, full_name: 'Анна Смирнова', group_name: 'Design', role_name: 'Дизайн-лид', status: 'В процессе', score_percent: 41, mbti_type: null, report_date: '2026-05-09T09:10:00', phone: '+7 900 300 00 00' },
    ],
  };

  const skillAssessments = [
    { skill_code: 'K1.1', skill_name: 'Ясность коммуникации и сообщений', competency_name: 'Коммуникация', assessed_level_code: 'L3', assessed_level_name: 'L3', evidence_excerpt: 'Сначала разделю запрос на бизнес-ценность, риски и стоимость задержки roadmap.', artifact_compliance_percent: 88, block_coverage_percent: 92 },
    { skill_code: 'K1.2', skill_name: 'Активное слушание и эмпатия', competency_name: 'Коммуникация', assessed_level_code: 'L2', assessed_level_name: 'L2', evidence_excerpt: 'Уточню ожидания sales, engineering и клиента.', artifact_compliance_percent: 75, block_coverage_percent: 78 },
    { skill_code: 'K2.2', skill_name: 'Организация и взаимодействие в команде', competency_name: 'Командная работа', assessed_level_code: 'L2', assessed_level_name: 'L2', evidence_excerpt: 'Соберу короткий синк и зафиксирую owner-ов.', artifact_compliance_percent: 74, block_coverage_percent: 70 },
    { skill_code: 'K3.1', skill_name: 'Гибкость мышления', competency_name: 'Креативность', assessed_level_code: 'L2', assessed_level_name: 'L2', evidence_excerpt: 'Предложу временный workaround для enterprise-клиента.', artifact_compliance_percent: 69, block_coverage_percent: 66 },
    { skill_code: 'K4.4', skill_name: 'Принятие решений', competency_name: 'Критическое мышление', assessed_level_code: 'L3', assessed_level_name: 'L3', evidence_excerpt: 'Решение нужно оформить как trade-off, а не победу одной стороны.', artifact_compliance_percent: 86, block_coverage_percent: 84 },
  ];

  const profileSummary = {
    user,
    total_assessments: 2,
    average_score_percent: 78,
    history: [
      { session_id: 501, status: 'completed', started_at: '2026-05-12T10:00:00', completed_cases: 5, total_cases: 5, overall_score_percent: 78, expert_comment: 'Уверенно структурирует коммуникацию и риски.' },
      { session_id: 411, status: 'completed', started_at: '2026-04-08T14:00:00', completed_cases: 5, total_cases: 5, overall_score_percent: 71, expert_comment: '' },
    ],
  };

  const adminReportDetail = {
    session_id: 501,
    user_id: 35,
    full_name: 'Мария Крылова',
    role_name: 'Руководитель продукта',
    group_name: 'Product',
    phone: '+7 900 100 00 00',
    telegram: '@maria_product',
    report_date: '2026-05-12T10:00:00',
    score_percent: 78,
    status: 'completed',
    mbti_type: 'ENTJ',
    mbti_summary: 'Стратегичный профиль с ориентацией на структуру и влияние.',
    insight_title: 'Сильная сторона: коммуникация в конфликтных ситуациях',
    insight_text: 'Пользователь переводит конфликт интересов в критерии решения и явно фиксирует ожидания.',
    basis_items: ['3 кейса с evidence по коммуникации.', 'Высокая полнота артефактов ответа.', 'Низкое количество red flags.'],
    strengths: ['Ясность коммуникации', 'Структурирование решений', 'Работа со стейкхолдерами'],
    growth_areas: ['Больше количественных критериев', 'Фиксация альтернативных сценариев'],
    quotes: ['Сначала разделю запрос на бизнес-ценность, риски и стоимость задержки roadmap.', 'Решение нужно зафиксировать как trade-off, а не как победу одной стороны.'],
    can_edit_expert_comment: true,
    expert_name: 'Елена Орлова',
    expert_contacts: 'expert@example.com',
    expert_assessed_at: '2026-05-12',
    expert_comment: 'Кандидат уверенно структурирует коммуникацию и хорошо работает с конфликтом приоритетов.',
    profile_summary: {
      position: 'Руководитель продукта',
      duties: 'Roadmap, discovery, запуск функций, синхронизация команд.',
      domain: 'B2B SaaS',
      processes: ['Discovery', 'Delivery planning', 'Stakeholder management'],
      tasks: ['Приоритизация гипотез', 'Коммуникация рисков', 'Запуск релизов'],
      stakeholders: ['Sales', 'Engineering', 'Customer Success'],
      constraints: ['Сжатые сроки', 'Enterprise SLA', 'Ограниченная команда'],
    },
    mbti_axes: [
      { left: 'Экстраверсия', right: 'Интроверсия', value: 62 },
      { left: 'Интуиция', right: 'Сенсорика', value: 71 },
      { left: 'Мышление', right: 'Чувство', value: 66 },
      { left: 'Суждение', right: 'Восприятие', value: 78 },
    ],
    case_items: [
      {
        session_case_id: 1001,
        case_number: 1,
        case_title: 'Запуск функции при конфликте приоритетов',
        case_id_code: 'CASE-PRD-01',
        status: 'completed',
        started_at: '2026-05-12T10:05:00',
        finished_at: '2026-05-12T10:17:00',
        personalized_context: 'Sales просит срочный запуск функции для enterprise-клиента.',
        personalized_task: 'Сформулируйте решение, вопросы и план коммуникации.',
        dialogue: [
          { role: 'assistant', message_text: 'Какие вопросы вы зададите перед решением?' },
          { role: 'user', message_text: 'Уточню влияние на выручку, риски для roadmap и доступные компромиссы.' },
        ],
        skill_results: skillAssessments.slice(0, 3),
      },
    ],
  };

  const promptLab = {
    production_prompt_text: 'Сформируй кейс с явным конфликтом приоритетов, ограничениями и ожидаемым артефактом ответа.',
    interviewer_prompt_text: 'Веди короткий кейсовый диалог и оценивай полноту ответа.',
    users: [{ id: 35, full_name: 'Мария Крылова', role_name: 'Руководитель продукта', position: 'Product Lead', company_industry: 'B2B SaaS', raw_duties: user.raw_duties, profile_summary: profileSummary }],
    role_options: [{ id: 1, name: 'Менеджер' }, { id: 2, name: 'Лидер' }],
    cases: adminMethodology.cases.map((item) => ({ case_id_code: item.case_id_code, type_code: 'PRIORITY_CONFLICT', title: item.title, interactivity_mode: item.interactivity_mode })),
  };

  const promptPreview = {
    id: 9001,
    total_cases: 1,
    case_items: [
      {
        case_number: 1,
        case: { case_id_code: 'CASE-PRD-01', title: 'Запуск функции при конфликте приоритетов' },
        base_context: 'У клиента появился срочный запрос.',
        base_task: 'Опишите решение и коммуникацию.',
        personalized_context: 'Sales просит срочный запуск функции для enterprise-клиента, но engineering предупреждает о риске срыва roadmap.',
        personalized_task: 'Сформулируйте критерии решения, вопросы к сторонам и план коммуникации.',
        case_quality: { case_text_quality_score: 4, template_fidelity_score: 5, personalization_score: 4, concreteness_score: 4, readability_score: 5, diversity_score: 4 },
      },
    ],
  };

  const dialogPreview = {
    case: { case_id_code: 'CASE-PRD-01', title: 'Запуск функции при конфликте приоритетов' },
    personalized_context: 'Sales просит срочный запуск функции для enterprise-клиента.',
    personalized_task: 'Какие вопросы вы зададите перед решением?',
    case_generation_prompt_text: promptLab.production_prompt_text,
    interviewer_prompt_text: promptLab.interviewer_prompt_text,
    required_answer_blocks: ['Критерии решения', 'Риски', 'План коммуникации'],
  };

  const jsonResponse = (payload, init) => new Response(JSON.stringify(payload), {
    status: init?.status || 200,
    headers: { 'Content-Type': 'application/json' },
  });

  const setupStorage = () => {
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith('agent4k.'))
      .forEach((key) => window.localStorage.removeItem(key));
    if (appScreen !== 'auth') {
      window.localStorage.setItem('agent4k.currentScreen', appScreen);
    }
    if (requestedScreen === 'admin-methodology-library') {
      window.localStorage.setItem('agent4k.adminMethodologyTab', 'library');
    } else if (requestedScreen === 'admin-methodology-branches') {
      window.localStorage.setItem('agent4k.adminMethodologyTab', 'branches');
    } else {
      window.localStorage.setItem('agent4k.adminMethodologyTab', 'passports');
    }
    if (appScreen === 'chat') {
      window.localStorage.setItem('agent4k.sessionId', 'preview-chat');
      window.localStorage.setItem('agent4k.pendingAgentMessage', 'Здравствуйте. Я помогу обновить профиль сотрудника перед оценкой компетенций. Подтвердите текущую роль или выберите более точную.');
      window.localStorage.setItem('agent4k.pendingRoleOptions', JSON.stringify([{ id: 1, name: 'Product Lead' }, { id: 2, name: 'Project Manager' }]));
    }
    if (appScreen === 'processing' || appScreen === 'report') {
      window.localStorage.setItem('agent4k.pendingUser', JSON.stringify(user));
      window.localStorage.setItem('agent4k.assessmentSessionId', '501');
    }
    if (appScreen === 'interview' || appScreen === 'prechat') {
      window.localStorage.setItem('agent4k.assessmentSessionCode', 'PREVIEW-SESSION');
      window.localStorage.setItem('agent4k.assessmentTotalCases', '5');
    }
    if (appScreen === 'admin-report-detail') {
      window.localStorage.setItem('agent4k.adminReportDetailSessionId', '501');
    }
  };

  setupStorage();

  window.fetch = async (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input.url, window.location.origin);
    const path = url.pathname;
    const method = String(init?.method || 'GET').toUpperCase();

    if (path === '/users/session/restore') {
      if (appScreen === 'auth') return jsonResponse({ authenticated: false });
      if (appScreen.startsWith('admin')) return jsonResponse({ authenticated: true, user: adminUser, is_admin: true, admin_dashboard: adminDashboard });
      return jsonResponse({ authenticated: true, user, dashboard: appScreen === 'dashboard' ? dashboard : null });
    }
    if (path === '/users/35/session-bootstrap') {
      return jsonResponse({ user, dashboard: appScreen === 'dashboard' ? dashboard : null });
    }
    if (path === '/users/1/session-bootstrap') {
      return jsonResponse({ user: adminUser, is_admin: true, admin_dashboard: adminDashboard });
    }
    if (path === '/users/admin/dashboard') return jsonResponse(adminDashboard);
    if (path === '/users/admin/methodology') return jsonResponse(adminMethodology);
    if (path.startsWith('/users/admin/methodology/cases/')) return jsonResponse({ case_id_code: 'CASE-PRD-01', title: 'Запуск функции при конфликте приоритетов' });
    if (path === '/users/admin/prompt-lab') return jsonResponse(promptLab);
    if (path === '/users/admin/prompt-lab/system-case-preview') return jsonResponse(promptPreview);
    if (path === '/users/admin/reports') return jsonResponse(adminReports);
    if (path === '/users/admin/reports/501') return jsonResponse(adminReportDetail);
    if (path === '/users/35/profile-summary') return jsonResponse(profileSummary);
    if (path === '/users/35/assessment/501/skill-assessments' || path === '/users/35/assessment/411/skill-assessments') return jsonResponse(skillAssessments);
    if (path === '/users/35/assessment/report-interpretation') return jsonResponse({
      summary_text: 'Глубокий анализ оценок по четырем направлениям и детализация результатов по каждому навыку.',
      strength_title: 'Сильная сторона: структурная коммуникация',
      strength_text: 'Ответы показывают умение переводить конфликт интересов в ясные критерии решения.',
      recommendations: ['Усилить работу с количественными критериями риска.', 'Добавлять явные контрольные точки для команды.'],
    });
    if (path === '/users/35/assessment/start' && method === 'POST') return jsonResponse({
      session_id: 501,
      session_code: 'PREVIEW-SESSION',
      case_number: 1,
      total_cases: 5,
      case_title: 'Запуск функции при конфликте приоритетов',
      message: 'Sales просит срочный запуск функции для enterprise-клиента. Какие вопросы вы зададите перед решением?',
      time_limit_minutes: 15,
    });
    if (path.startsWith('/users/operations/')) return jsonResponse({ status: 'completed', percent: 100, title: 'Готово', message: 'Preview data ready.' });
    if (path === '/users/session/logout') return jsonResponse({ ok: true });
    if (path.includes('/admin/prompt-lab/dialogue-preview')) return jsonResponse(dialogPreview);
    if (path.includes('/admin/prompt-lab/dialogue-turn')) return jsonResponse({ reply: 'Хорошо. Какие критерии решения вы зафиксируете?', history: [{ role: 'assistant', content: 'Какие вопросы вы зададите перед решением?' }] });
    if (method === 'POST' || method === 'PATCH') return jsonResponse({ ok: true });
    return jsonResponse({ detail: 'Preview stub: route not implemented: ' + path }, { status: 404 });
  };

  window.__AGENT4K_SCREEN_PREVIEW__ = {
    requestedScreen,
    appScreen,
    promptPreview,
    dialogPreview,
  };
}());
