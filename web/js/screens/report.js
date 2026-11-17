import { bindReportPdf, downloadReportPdf, resetReportDownload, withReportDeadline } from '../utils/report-download.js';
import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import {
  reportPanel,
  reportOverallScore,
  reportSummaryText,
  reportProfileAvatar,
  reportProfileName,
  reportProfileRole,
  reportMetadataList,
  reportRecommendations,
  reportCompetencyBars,
  reportCompetencyBarChartCanvas,
  reportCompetencyBarsFallback,
  reportCompetencyCompactQuery,
  reportStrengthTitle,
  reportStrengthText,
  reportTabs,
  reportTabSelect,
  reportDetailTitle,
  reportDetailList,
  reportInfoModal,
  reportInfoModalClose,
  reportInfoModalEyebrow,
  reportInfoModalTitle,
  reportInfoModalBody,
} from '../dom.js';
import { competencyOrder } from '../config.js';
import {
  escapeHtml,
  buildInitials,
  sanitizeDisplayRole,
  parseJsonArrayField,
  parseApiDateTime,
} from '../utils/format.js';
import { getLevelPercent } from '../utils/competency.js';
import { readApiResponse } from '../api.js';
import { hideAllPanels, syncUrlState, navigateToScreen } from '../router.js';
import { projectReportRadar, radarPoint, summarizeReportScores } from '../utils/report-radar.js';
import { openHomePage } from './ai-welcome.js';
import { openReports } from './reports.js';

const formatAdminChartLabel = (text) => {
  const rawText = String(text || 'Без названия').trim();
  const words = rawText.split(/\s+/).filter(Boolean);
  if (words.length < 2) {
    return rawText;
  }

  const lines = [];
  let currentLine = '';
  words.forEach((word) => {
    if (!currentLine) {
      currentLine = word;
      return;
    }
    if ((currentLine + ' ' + word).length <= 14) {
      currentLine += ' ' + word;
      return;
    }
    lines.push(currentLine);
    currentLine = word;
  });

  if (currentLine) {
    lines.push(currentLine);
  }
  return lines.length > 1 ? lines : rawText;
};

let reportCompetencyBarChart = null;
let reportInfoModalCloseTimer = null;

export const buildArtifactHint = (skill) => {
  const parts = [];
  if (skill.expected_artifact_names) {
    parts.push('Артефакт: ' + skill.expected_artifact_names);
  }
  if (skill.artifact_compliance_percent != null) {
    parts.push('Соответствие: ' + skill.artifact_compliance_percent + '%');
  }
  return parts.join(' • ');
};

const normalizeSkillDescriptionKey = (value) =>
  String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();

const reportSkillDescriptions = new Map([
  [
    'k1.1',
    'Умении четко, точно и понятно выражать мысли, эмоции и факты в устной, письменной и невербальной форме. Это предполагает создание сообщений, соответствующих восприятию и уровню знаний получателя, а также использование различных средств (жесты, мимика, интонация) для передачи смысла. Ясная коммуникация обеспечивает отсутствие двусмысленностей и недоразумений, что способствует эффективному достижению поставленных целей',
  ],
  [
    'ясность коммуникации и сообщений',
    'Умении четко, точно и понятно выражать мысли, эмоции и факты в устной, письменной и невербальной форме. Это предполагает создание сообщений, соответствующих восприятию и уровню знаний получателя, а также использование различных средств (жесты, мимика, интонация) для передачи смысла. Ясная коммуникация обеспечивает отсутствие двусмысленностей и недоразумений, что способствует эффективному достижению поставленных целей',
  ],
  [
    'k1.2',
    'Способность слушать и понимать не только вербальное содержание сообщения, но и эмоциональный контекст и скрытые намерения собеседника. Эффективное активное слушание и эмпатия способствуют формированию доверия и взаимопонимания, позволяя точнее реагировать на получаемую информацию.',
  ],
  [
    'активное слушание и эмпатия',
    'Способность слушать и понимать не только вербальное содержание сообщения, но и эмоциональный контекст и скрытые намерения собеседника. Эффективное активное слушание и эмпатия способствуют формированию доверия и взаимопонимания, позволяя точнее реагировать на получаемую информацию.',
  ],
  [
    'k1.3',
    'Способность эффективно использовать вопросы как инструмент познания, анализа ситуации и улучшения взаимопонимания. Это включает выбор подходящих формулировок, определение момента для задавания вопросов и использование ответов для углубления знаний и достижения целей.',
  ],
  [
    'вопрошание (умение задавать вопросы)',
    'Способность эффективно использовать вопросы как инструмент познания, анализа ситуации и улучшения взаимопонимания. Это включает выбор подходящих формулировок, определение момента для задавания вопросов и использование ответов для углубления знаний и достижения целей.',
  ],
  [
    'k2.1',
    'Умение создавать атмосферу, в которой участники команды чувствуют себя принятыми, услышанными и в безопасности. Основано на открытости, эмпатии, честности и уважении. Команда может открыто делиться мнениями и ошибками без страха осуждения.',
  ],
  [
    'формирование доверия и безопасной среды',
    'Умение создавать атмосферу, в которой участники команды чувствуют себя принятыми, услышанными и в безопасности. Основано на открытости, эмпатии, честности и уважении. Команда может открыто делиться мнениями и ошибками без страха осуждения.',
  ],
  [
    'k2.2',
    'Способность структурировать совместную деятельность команды: формулировать цели, планировать шаги, распределять роли и отслеживать прогресс. Обеспечивает прозрачность, предсказуемость и слаженность в работе.',
  ],
  [
    'организация и взаимодействие в команде',
    'Способность структурировать совместную деятельность команды: формулировать цели, планировать шаги, распределять роли и отслеживать прогресс. Обеспечивает прозрачность, предсказуемость и слаженность в работе.',
  ],
  [
    'k2.3',
    'Инициирование развития команды и её участников, даже без формальной власти. Включает наставничество, развитие инициативы и поддержку обучения. Способность вдохновлять команду, мотивировать членов команды, направлять их на достижение общих целей и обеспечивать их вовлеченность в командный процесс.',
  ],
  [
    'лидерство и поддержка роста команды',
    'Инициирование развития команды и её участников, даже без формальной власти. Включает наставничество, развитие инициативы и поддержку обучения. Способность вдохновлять команду, мотивировать членов команды, направлять их на достижение общих целей и обеспечивать их вовлеченность в командный процесс.',
  ],
  [
    'k3.1',
    'Навык воспринимать новые и непривычные идеи, рассматривать альтернативные подходы, допускать неоднозначность, быстро переключаться между различными точками зрения, уметь пересмотреть ранее полученный опыт.',
  ],
  [
    'гибкость мышления',
    'Навык воспринимать новые и непривычные идеи, рассматривать альтернативные подходы, допускать неоднозначность, быстро переключаться между различными точками зрения, уметь пересмотреть ранее полученный опыт.',
  ],
  [
    'k3.2',
    'Способность создавать новые, нестандартные идеи и решения, а также развивать «сырые» замыслы до работоспособного уровня, чтобы решить существующие проблемы или улучшить текущие процессы.',
  ],
  [
    'создание и видение идей',
    'Способность создавать новые, нестандартные идеи и решения, а также развивать «сырые» замыслы до работоспособного уровня, чтобы решить существующие проблемы или улучшить текущие процессы.',
  ],
  [
    'k3.3',
    'Способность творчески оценивать и дорабатывать идеи с учётом целей, ограничений и обратной связи, превращая их в реализуемые и ценные решения.',
  ],
  [
    'оценка и реализация идей',
    'Способность творчески оценивать и дорабатывать идеи с учётом целей, ограничений и обратной связи, превращая их в реализуемые и ценные решения.',
  ],
  [
    'k4.1',
    'Способность выявлять проблемы, анализировать их корни и искать оптимальные решения. Это включает в себя умение анализировать ситуации и выбирать такие методы, которые приведут к наиболее эффективному решению.',
  ],
  [
    'решение проблем',
    'Способность выявлять проблемы, анализировать их корни и искать оптимальные решения. Это включает в себя умение анализировать ситуации и выбирать такие методы, которые приведут к наиболее эффективному решению.',
  ],
  [
    'k4.2',
    'Способность собирать и систематизировать данные из различных источников, отделяя существенную информацию от незначимой. Важно уметь проводить анализ, выявлять паттерны и связи между различными данными для формирования более глубокой картины ситуации.',
  ],
  [
    'анализ информации',
    'Способность собирать и систематизировать данные из различных источников, отделяя существенную информацию от незначимой. Важно уметь проводить анализ, выявлять паттерны и связи между различными данными для формирования более глубокой картины ситуации.',
  ],
  [
    'k4.3',
    'Способность выстраивать логические цепочки для формирования обоснованных выводов. Это включает в себя умение работать с доказательствами и аргументами, а также умение структурировать информацию так, чтобы она вела к правильным выводам.',
  ],
  [
    'логическое мышление',
    'Способность выстраивать логические цепочки для формирования обоснованных выводов. Это включает в себя умение работать с доказательствами и аргументами, а также умение структурировать информацию так, чтобы она вела к правильным выводам.',
  ],
  [
    'k4.4',
    'Способность принимать решения на основе ограниченной или неполной информации, используя анализ рисков и интуицию. Это включает в себя способность действовать в условиях неопределенности и неполных данных, при этом минимизируя возможные негативные последствия.',
  ],
  [
    'принятие решений',
    'Способность принимать решения на основе ограниченной или неполной информации, используя анализ рисков и интуицию. Это включает в себя способность действовать в условиях неопределенности и неполных данных, при этом минимизируя возможные негативные последствия.',
  ],
  [
    'взаимодействие в команде',
    'Способность эффективно работать в группе и команде: соблюдение договорённостей, синхронизация действий, взаимопомощь, готовность делегировать и принимать обратную связь. Обеспечивает согласованность действий и взаимную ответственность.',
  ],
]);

export const getReportSkillDescription = (skill) => {
  const byCode = reportSkillDescriptions.get(normalizeSkillDescriptionKey(skill.skill_code));
  if (byCode) {
    return byCode;
  }
  return reportSkillDescriptions.get(normalizeSkillDescriptionKey(skill.skill_name)) || '';
};

const getReportEvidenceLabel = (item) => {
  if (typeof item === 'string') {
    return item.trim();
  }
  if (!item || typeof item !== 'object') {
    return '';
  }
  return String(
    item.evidence_description ||
      item.expected_signal ||
      item.related_response_block_name ||
      item.related_response_block_code ||
      '',
  ).trim();
};

const getReportSkillEvidenceExcerpt = (skill) =>
  String(skill?.evidence_excerpt || '')
    .replace(/\s+/g, ' ')
    .trim();

const formatReportDateTime = (value) => {
  if (!value) {
    return 'Без даты';
  }
  const date = parseApiDateTime(value);
  if (!date) {
    return 'Без даты';
  }
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatReportDuration = (startedAt, finishedAt) => {
  if (!finishedAt) {
    return 'В процессе';
  }
  const start = parseApiDateTime(startedAt);
  const finish = parseApiDateTime(finishedAt);
  if (!start || !finish || finish < start) {
    return 'Не рассчитано';
  }

  const totalMinutes = Math.max(0, Math.round((finish.getTime() - start.getTime()) / 60000));
  if (totalMinutes < 1) {
    return '<1 мин';
  }
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) {
    return days + ' д ' + hours + ' ч';
  }
  if (hours > 0) {
    return hours + ' ч ' + minutes + ' мин';
  }
  return minutes + ' мин';
};

const getReportSessionSummary = () => {
  const sessionId = Number(state.assessmentSessionId);
  const history = Array.isArray(state.profileSummary?.history) ? state.profileSummary.history : [];
  return history.find((item) => Number(item.session_id) === sessionId) || null;
};

const getReportStatusLabel = (status) => {
  if (status === 'completed') {
    return 'Завершена';
  }
  if (status === 'active') {
    return 'В процессе';
  }
  if (status === 'draft') {
    return 'Черновик';
  }
  return status ? String(status) : 'Нет статуса';
};

const renderReportMetadata = () => {
  if (!reportMetadataList) {
    return;
  }

  const summary = getReportSessionSummary();
  if (!summary) {
    reportMetadataList.innerHTML =
      '<div class="report-metadata-empty">Данные по сессии появятся после загрузки истории ассессментов.</div>';
    return;
  }

  const completedCases = Number(summary.completed_cases) || 0;
  const totalCases = Number(summary.total_cases) || 0;
  const rows = [
    ['Сессия', '#' + summary.session_id],
    ['Начата', formatReportDateTime(summary.started_at)],
    ['Завершена', summary.finished_at ? formatReportDateTime(summary.finished_at) : 'В процессе'],
    ['Кейсы', completedCases + '/' + totalCases],
    ['Время прохождения', formatReportDuration(summary.started_at, summary.finished_at)],
    ['Статус', getReportStatusLabel(summary.status)],
  ];

  reportMetadataList.innerHTML = rows
    .map(
      ([label, value]) =>
        '<div class="report-metadata-row">' +
        '<dt>' +
        escapeHtml(label) +
        '</dt>' +
        '<dd>' +
        escapeHtml(value) +
        '</dd>' +
        '</div>',
    )
    .join('');
};

export const openReportInfoModal = ({ eyebrow = 'Детали', title = 'Информация', bodyMarkup = '' }) => {
  if (!reportInfoModal || !reportInfoModalTitle || !reportInfoModalBody) {
    return;
  }
  if (reportInfoModalCloseTimer) {
    window.clearTimeout(reportInfoModalCloseTimer);
    reportInfoModalCloseTimer = null;
  }
  if (reportInfoModalEyebrow) {
    reportInfoModalEyebrow.textContent = eyebrow;
  }
  reportInfoModalTitle.textContent = title;
  reportInfoModalBody.innerHTML = bodyMarkup || '<p>Детали пока недоступны.</p>';
  reportInfoModal.classList.remove('hidden');
  reportInfoModal.classList.remove('is-closing');
  reportInfoModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('report-info-modal-open');
  window.requestAnimationFrame(() => {
    if (!reportInfoModal.classList.contains('is-closing')) {
      reportInfoModal.classList.add('is-open');
    }
  });
  if (reportInfoModalClose) {
    reportInfoModalClose.focus();
  }
};

export const closeReportInfoModal = () => {
  if (
    !reportInfoModal ||
    reportInfoModal.classList.contains('hidden') ||
    reportInfoModal.classList.contains('is-closing')
  ) {
    return;
  }
  reportInfoModal.setAttribute('aria-hidden', 'true');
  reportInfoModal.classList.remove('is-open');
  reportInfoModal.classList.add('is-closing');
  reportInfoModalCloseTimer = window.setTimeout(() => {
    reportInfoModal.classList.add('hidden');
    reportInfoModal.classList.remove('is-closing');
    document.body.classList.remove('report-info-modal-open');
    reportInfoModalCloseTimer = null;
  }, 180);
};

const buildReportRationaleMarkup = (rationale) => {
  const match = rationale.match(/^(.*?уровню\s+)(L[123])(\.|\s|$)(.*)$/i);
  if (!match) {
    return escapeHtml(rationale);
  }
  const [, prefix, levelCode, delimiter, rest = ''] = match;
  return (
    escapeHtml(prefix) +
    '<span class="report-evidence-level-pill">' +
    escapeHtml(levelCode.toUpperCase()) +
    '</span>' +
    escapeHtml(delimiter + rest)
  );
};

const buildReportInfoCard = (title, bodyMarkup, options = {}) => {
  if (!bodyMarkup) {
    return '';
  }
  const modifier = options.modifier ? ' report-info-card--' + options.modifier : '';
  return (
    '<section class="report-info-card' +
    modifier +
    '">' +
    '<span class="report-info-card-title">' +
    escapeHtml(title) +
    '</span>' +
    bodyMarkup +
    '</section>'
  );
};

const buildReportMetricMarkup = (items) => {
  const metrics = items.filter((item) => item.value !== null && item.value !== undefined && item.value !== '');
  if (!metrics.length) {
    return '';
  }
  return (
    '<dl class="report-info-metrics">' +
    metrics
      .map(
        (item) =>
          '<div>' +
          '<dt>' +
          escapeHtml(item.label) +
          '</dt>' +
          '<dd>' +
          escapeHtml(item.value) +
          '</dd>' +
          '</div>',
      )
      .join('') +
    '</dl>'
  );
};

const buildReportListMarkup = (items) => {
  const labels = items.map((item) => String(item || '').trim()).filter(Boolean);
  if (!labels.length) {
    return '';
  }
  return '<ul class="report-info-list">' + labels.map((label) => '<li>' + escapeHtml(label) + '</li>').join('') + '</ul>';
};

const buildReportChipListMarkup = (items) => {
  const labels = items.map((item) => String(item || '').trim()).filter(Boolean);
  if (!labels.length) {
    return '';
  }
  return '<span class="report-evidence-signals">' + labels.map((label) => '<span>' + escapeHtml(label) + '</span>').join('') + '</span>';
};

const formatPercentValue = (value) => {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return Math.round(numeric) + '%';
};

const getReportSkillScoreDetails = (skill, percent = null) => {
  const evidenceLabels = parseJsonArrayField(skill.found_evidence)
    .map(getReportEvidenceLabel)
    .filter(Boolean)
    .slice(0, 3);
  const detectedBlocks = parseJsonArrayField(skill.detected_required_blocks);
  const missingBlocks = parseJsonArrayField(skill.missing_required_blocks);
  const rationale = String(skill?.rationale || '')
    .replace(/\s+/g, ' ')
    .trim();
  const excerpt = getReportSkillEvidenceExcerpt(skill);
  const summaryMarkup = buildReportMetricMarkup([
    { label: 'Оценка', value: formatPercentValue(percent) },
    { label: 'Уровень', value: skill.assessed_level_name || skill.assessed_level_code },
  ]);
  const structureBody = [
    buildReportMetricMarkup([{ label: 'Покрытие', value: formatPercentValue(skill.block_coverage_percent) }]),
    detectedBlocks.length
      ? '<div class="report-info-card-group"><span>Найдены</span>' + buildReportChipListMarkup(detectedBlocks) + '</div>'
      : '',
    missingBlocks.length
      ? '<div class="report-info-card-group report-info-card-group--muted"><span>Не обнаружены</span>' +
        buildReportChipListMarkup(missingBlocks) +
        '</div>'
      : '',
  ].join('');
  const artifactBody = [
    skill.expected_artifact_names
      ? '<p class="report-info-card-text">' + escapeHtml(skill.expected_artifact_names) + '</p>'
      : '',
    buildReportMetricMarkup([{ label: 'Соответствие', value: formatPercentValue(skill.artifact_compliance_percent) }]),
  ].join('');
  const signalsMarkup = buildReportInfoCard('Найденные признаки', buildReportChipListMarkup(evidenceLabels));
  const rationaleMarkup = buildReportInfoCard(
    'Объяснение',
    rationale ? '<p class="report-evidence-rationale">' + buildReportRationaleMarkup(rationale) + '</p>' : '',
    { modifier: 'wide' },
  );
  const excerptMarkup = buildReportInfoCard(
    'Фрагмент ответа',
    excerpt ? '<p class="report-evidence-quote">' + escapeHtml(excerpt) + '</p>' : '',
    { modifier: 'wide' },
  );
  return {
    hasDetails: Boolean(
      evidenceLabels.length ||
        rationale ||
        excerpt ||
        detectedBlocks.length ||
        missingBlocks.length ||
        skill.block_coverage_percent != null ||
        skill.expected_artifact_names ||
        skill.artifact_compliance_percent != null,
    ),
    markup:
      '<div class="report-info-card-grid">' +
      buildReportInfoCard('Итог', summaryMarkup) +
      signalsMarkup +
      buildReportInfoCard('Структура ответа', structureBody) +
      buildReportInfoCard('Артефакт', artifactBody) +
      rationaleMarkup +
      excerptMarkup +
      '</div>',
  };
};

const normalizeReportInsightText = (value) =>
  String(value || '')
    .replace(/\s+/g, ' ')
    .trim();

const getReportInsightNarrative = (interpretation) => {
  const text = normalizeReportInsightText(interpretation?.insight_text);
  const pattern = normalizeReportInsightText(interpretation?.response_pattern);
  if (text && pattern && text.endsWith(pattern)) {
    return text.slice(0, -pattern.length).trim();
  }
  return text;
};

const buildReportInsightPills = (interpretation) =>
  '<div class="report-insight-pills">' +
  '<span>Сигнал: ' +
  escapeHtml(interpretation?.has_interpretation_signal ? 'достаточный' : 'слабый') +
  '</span>' +
  '<span>Компетенция: ' +
  escapeHtml(interpretation?.has_confident_strongest ? 'выделена' : 'не подтверждена') +
  '</span>' +
  '</div>';

const buildReportInsightMarkup = (interpretation) => {
  const narrative = getReportInsightNarrative(interpretation);
  const pattern = normalizeReportInsightText(interpretation?.response_pattern);
  const basisItems = Array.isArray(interpretation?.basis_items) ? interpretation.basis_items : [];

  if (!narrative && !pattern && !basisItems.length) {
    return (
      '<p class="report-info-text">' +
      escapeHtml(
        'По последней сессии пока не удалось выделить достаточно уверенную доминирующую компетенцию. После повторного прохождения с более содержательными и структурированными ответами здесь появится аналитический вывод.',
      ) +
      '</p>'
    );
  }

  return (
    '<div class="report-insight-compact">' +
    (narrative ? '<p class="report-insight-summary">' + escapeHtml(narrative) + '</p>' : '') +
    buildReportInsightPills(interpretation) +
    '<div class="report-insight-compact-grid">' +
    buildReportInfoCard('Паттерн ответа', pattern ? '<p class="report-info-card-text">' + escapeHtml(pattern) + '</p>' : '') +
    buildReportInfoCard('Основание', buildReportListMarkup(basisItems)) +
    '</div>' +
    '</div>'
  );
};

const buildReportSkillScoreMarkup = (skill, percent) => {
  const scoreText = escapeHtml(percent + '%');
  const details = getReportSkillScoreDetails(skill, percent);
  if (!details.hasDetails) {
    return '<span>' + scoreText + '</span>';
  }

  const ariaLabel = (skill.skill_name || 'Навык') + ': что повлияло на оценку ' + percent + '%';

  return (
    '<span class="report-skill-score-value">' +
    scoreText +
    '</span>' +
    '<button type="button" class="report-skill-score-text" aria-label="' +
    escapeHtml(ariaLabel) +
    '">?</button>'
  );
};

const buildReportSkillNameMarkup = (skill) => {
  const skillName = escapeHtml(skill.skill_name || 'Навык');
  const description = getReportSkillDescription(skill);
  if (!description) {
    return '<strong>' + skillName + '</strong>';
  }
  return (
    '<button type="button" class="report-skill-name-text" aria-label="' +
    escapeHtml('Описание навыка: ' + (skill.skill_name || 'Навык')) +
    '">' +
    '<span class="report-skill-name-label">' +
    skillName +
    '</span>' +
    '</button>'
  );
};

export const buildProfileSkillsMarkup = (skills) => {
  if (!skills.length) {
    return '<p class="report-empty-state">По выбранной сессии еще нет результатов оценки навыков.</p>';
  }

  const header =
    '<div class="profile-skill-columns report-detail-columns" aria-hidden="true">' +
    '<span class="report-detail-column-name">Навык</span>' +
    '<span class="report-detail-column-level">Уровень</span>' +
    '<span class="report-detail-column-progress">Прогресс</span>' +
    '</div>';

  const rows = skills
    .map((skill) => {
      const percent = getLevelPercent(skill.assessed_level_code);
      return (
        '<article class="profile-skill-row">' +
        '<div class="profile-skill-main">' +
        '<strong>' +
        skill.skill_name +
        '</strong>' +
        '<span>' +
        (skill.competency_name || 'Без категории') +
        '</span>' +
        (buildArtifactHint(skill) ? '<span class="skill-artifact-hint">' + buildArtifactHint(skill) + '</span>' : '') +
        '</div>' +
        '<div class="profile-skill-level">' +
        skill.assessed_level_name +
        '</div>' +
        '<div class="profile-skill-progress">' +
        '<div class="report-skill-progress-track"><div class="report-skill-progress-fill" style="width:' +
        percent +
        '%"></div></div>' +
        '<span>' +
        percent +
        '%</span>' +
        '</div>' +
        '</article>'
      );
    })
    .join('');

  return '<div class="profile-skill-grid">' + header + rows + '</div>';
};

const getCompetencySummary = () => {
  const grouped = new Map();

  competencyOrder.forEach((name) => {
    grouped.set(name, []);
  });

  state.skillAssessments.forEach((item) => {
    const competency = item.competency_name || 'Без категории';
    if (!grouped.has(competency)) {
      grouped.set(competency, []);
    }
    grouped.get(competency).push(item);
  });

  return Array.from(grouped.entries())
    .filter(([, skills]) => skills.length > 0)
    .map(([competency, skills]) => {
      const avgPercent = Math.round(
        skills.reduce((sum, skill) => sum + getLevelPercent(skill.assessed_level_code), 0) / skills.length,
      );
      const evidenceHits = skills.filter((skill) => parseJsonArrayField(skill.found_evidence).length > 0).length;
      const blockValues = skills
        .map((skill) => (skill.block_coverage_percent != null ? Number(skill.block_coverage_percent) || 0 : null))
        .filter((value) => value != null);
      const artifactValues = skills
        .map((skill) =>
          skill.artifact_compliance_percent != null ? Number(skill.artifact_compliance_percent) || 0 : null,
        )
        .filter((value) => value != null);
      const redFlagCounts = skills.map((skill) => parseJsonArrayField(skill.red_flags).length);
      const metrics = {
        evidenceHitRate: skills.length ? evidenceHits / skills.length : 0,
        avgBlockCoverage: blockValues.length
          ? blockValues.reduce((sum, value) => sum + value, 0) / blockValues.length
          : 0,
        avgArtifactCompliance: artifactValues.length
          ? artifactValues.reduce((sum, value) => sum + value, 0) / artifactValues.length
          : 0,
        avgRedFlagCount: redFlagCounts.length
          ? redFlagCounts.reduce((sum, value) => sum + value, 0) / redFlagCounts.length
          : 0,
      };
      return {
        competency,
        skills,
        avgPercent,
        metrics,
        insightScore: Math.round(
          avgPercent * 0.5 +
            metrics.evidenceHitRate * 100 * 0.2 +
            metrics.avgBlockCoverage * 0.15 +
            metrics.avgArtifactCompliance * 0.15 -
            Math.min(metrics.avgRedFlagCount * 10, 40),
        ),
      };
    });
};

const hasManifestedCompetencyResults = (summary) => summary.some((item) => item.avgPercent > 0);

const getReportSignalMetrics = () => {
  const skills = Array.isArray(state.skillAssessments) ? state.skillAssessments : [];
  if (!skills.length) {
    return {
      skillsCount: 0,
      evidenceHitRate: 0,
      avgBlockCoverage: 0,
      avgArtifactCompliance: 0,
      avgRedFlagCount: 0,
    };
  }

  let evidenceHits = 0;
  let blockCoverageSum = 0;
  let blockCoverageCount = 0;
  let artifactComplianceSum = 0;
  let artifactComplianceCount = 0;
  let redFlagCountSum = 0;

  skills.forEach((skill) => {
    if (parseJsonArrayField(skill.found_evidence).length > 0) {
      evidenceHits += 1;
    }
    if (skill.block_coverage_percent != null) {
      blockCoverageSum += Number(skill.block_coverage_percent) || 0;
      blockCoverageCount += 1;
    }
    if (skill.artifact_compliance_percent != null) {
      artifactComplianceSum += Number(skill.artifact_compliance_percent) || 0;
      artifactComplianceCount += 1;
    }
    redFlagCountSum += parseJsonArrayField(skill.red_flags).length;
  });

  return {
    skillsCount: skills.length,
    evidenceHitRate: evidenceHits / skills.length,
    avgBlockCoverage: blockCoverageCount ? blockCoverageSum / blockCoverageCount : 0,
    avgArtifactCompliance: artifactComplianceCount ? artifactComplianceSum / artifactComplianceCount : 0,
    avgRedFlagCount: redFlagCountSum / skills.length,
  };
};

const hasEnoughSignalForInterpretation = (summary) => {
  if (!hasManifestedCompetencyResults(summary)) {
    return false;
  }

  const metrics = getReportSignalMetrics();
  if (!metrics.skillsCount) {
    return false;
  }

  return (
    metrics.evidenceHitRate >= 0.2 &&
    metrics.avgBlockCoverage >= 25 &&
    metrics.avgArtifactCompliance >= 25 &&
    metrics.avgRedFlagCount <= 4
  );
};

const COMPETENCY_GROWTH_RECOMMENDATIONS = {
  'Коммуникация': {
    structure:
      'По коммуникации стоит усилить структуру ответа: фиксировать контекст, уточняющие вопросы, договоренности и следующий шаг.',
    artifact:
      'По коммуникации важно точнее попадать в ожидаемый формат артефакта: сообщение стейкхолдеру должно содержать статус, срок и понятный следующий шаг.',
    evidence:
      'По коммуникации полезно делать ответы более наблюдаемыми: явно формулировать позицию, вопросы и договоренности, чтобы навык проявлялся в тексте.',
    redflags:
      'По коммуникации стоит снизить число типовых ошибок: не игнорировать ограничения, не пропускать резюме и не оставлять ответ без следующего шага.',
    generic: 'Усилить коммуникацию: чаще фиксировать позицию, вопросы и договоренности в явном виде.',
  },
  'Командная работа': {
    structure:
      'По командной работе стоит делать ответ более структурным: явно показывать роли, точки синхронизации и контроль исполнения.',
    artifact:
      'По командной работе важно точнее попадать в артефакт плана действий: кто делает, в какой последовательности, по каким контрольным точкам.',
    evidence:
      'По командной работе полезно явнее проявлять координацию: показывать распределение ролей, поддержку участников и согласование действий.',
    redflags:
      'По командной работе стоит уменьшить число red flags: не пропускать роли, контрольные точки и критерии взаимодействия.',
    generic: 'Усилить командную работу: показывать распределение ролей, синхронизацию и поддержку участников.',
  },
  'Креативность': {
    structure:
      'По креативности стоит лучше структурировать ответ: выделять альтернативы, критерии отбора и следующий шаг по проверке идеи.',
    artifact:
      'По креативности важно точнее попадать в формат артефакта: идеи, пилоты и варианты должны быть оформлены как проверяемый план, а не как общее рассуждение.',
    evidence:
      'По креативности полезно явнее проявлять генерацию вариантов: предлагать альтернативы, пилоты и нестандартные решения в явном виде.',
    redflags:
      'По креативности стоит снизить число red flags: не оставлять ответ без альтернатив, критериев выбора и ограничений для проверки идеи.',
    generic: 'Усилить креативность: предлагать альтернативы, пилоты и нестандартные варианты решений.',
  },
  'Критическое мышление': {
    structure:
      'По критическому мышлению стоит лучше структурировать ответ: выделять критерии, риски, гипотезы и проверку решения.',
    artifact:
      'По критическому мышлению важно точнее попадать в формат артефакта: решение должно быть оформлено через критерии, риски и обоснованный выбор.',
    evidence:
      'По критическому мышлению полезно делать анализ наблюдаемым: явно показывать логику выбора, допущения и проверку гипотез.',
    redflags:
      'По критическому мышлению стоит снизить число red flags: не пропускать критерии, ограничения, риски и контроль решения.',
    generic: 'Усилить критическое мышление: добавлять критерии, риски, гипотезы и проверку решений.',
  },
};

const WEAK_SIGNAL_RECOMMENDATIONS = [
  'По последней сессии сигнал слишком слабый для корректной персональной интерпретации зон роста.',
  'Сначала стоит усилить структурность ответов: фиксировать вопросы, критерии, договоренности и следующий шаг.',
  'Важно попадать в ожидаемый формат ответа кейса: план, список вопросов, сообщение стейкхолдеру или приоритизация.',
  'Рекомендуется пройти ассессмент повторно и давать более содержательные ответы, чтобы в них проявлялись наблюдаемые действия и решения.',
];

const getCompetencyDominantDeficit = (item) => {
  if (!item) {
    return 'generic';
  }
  const metrics = item.metrics || {};
  if ((metrics.avgBlockCoverage || 0) < 50) {
    return 'structure';
  }
  if ((metrics.avgArtifactCompliance || 0) < 50) {
    return 'artifact';
  }
  if ((metrics.evidenceHitRate || 0) < 0.5) {
    return 'evidence';
  }
  if ((metrics.avgRedFlagCount || 0) > 2) {
    return 'redflags';
  }
  return 'generic';
};

const buildCompetencyGrowthRecommendation = (item) => {
  const competency = item.competency;
  const deficit = getCompetencyDominantDeficit(item);
  const mapping =
    COMPETENCY_GROWTH_RECOMMENDATIONS[competency] || COMPETENCY_GROWTH_RECOMMENDATIONS['Критическое мышление'];
  return mapping[deficit] || mapping.generic;
};

const getReportRecommendations = (summary) => {
  if (state.reportInterpretation?.growth_areas?.length) {
    return state.reportInterpretation.growth_areas;
  }
  if (!hasEnoughSignalForInterpretation(summary)) {
    return [...WEAK_SIGNAL_RECOMMENDATIONS];
  }

  const weakest = [...summary].sort((a, b) => a.avgPercent - b.avgPercent).slice(0, 3);
  if (!weakest.length) {
    return ['Завершите ассессмент, чтобы получить рекомендации по развитию.'];
  }

  return weakest.map((item) => buildCompetencyGrowthRecommendation(item));
};

export const destroyReportCompetencyBarChart = () => {
  if (reportCompetencyBarChart) {
    reportCompetencyBarChart.destroy();
    reportCompetencyBarChart = null;
  }
};

const drawCanvasRoundedRect = (context, x, y, width, height, radius) => {
  const safeRadius = Math.max(0, Math.min(radius, width / 2, height / 2));
  context.beginPath();
  if (typeof context.roundRect === 'function') {
    context.roundRect(x, y, width, height, safeRadius);
    return;
  }
  context.moveTo(x + safeRadius, y);
  context.lineTo(x + width - safeRadius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
  context.lineTo(x + width, y + height - safeRadius);
  context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
  context.lineTo(x + safeRadius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
  context.lineTo(x, y + safeRadius);
  context.quadraticCurveTo(x, y, x + safeRadius, y);
};

const drawWrappedCanvasText = (context, text, x, y, maxWidth, lineHeight) => {
  const words = String(text || '')
    .split(/\s+/)
    .filter(Boolean);
  const lines = [];
  let currentLine = '';

  words.forEach((word) => {
    const nextLine = currentLine ? currentLine + ' ' + word : word;
    if (currentLine && context.measureText(nextLine).width > maxWidth) {
      lines.push(currentLine);
      currentLine = word;
      return;
    }
    currentLine = nextLine;
  });

  if (currentLine) {
    lines.push(currentLine);
  }

  const visibleLines = lines.slice(0, 2);
  const firstBaseline = y - ((visibleLines.length - 1) * lineHeight) / 2;
  visibleLines.forEach((line, index) => {
    context.fillText(line, x, firstBaseline + index * lineHeight);
  });
};

const getReportCompetencyCardMetrics = (chart, meta, items) => {
  const chartArea = chart.chartArea;
  const count = Math.max(items.length, meta.data.length, 1);
  const slotWidth = chartArea.width / count;
  const cardGap = Math.min(8, Math.max(4, slotWidth * 0.025));
  const cardWidth = Math.max(112, slotWidth - cardGap);
  const trackInset = 8;
  const fillOffset = 3;
  const trackWidth = Math.min(48, Math.max(40, cardWidth * 0.25));
  const fillWidth = 34;

  return {
    cardWidth,
    fillOffset,
    fillWidth,
    trackInset,
    trackWidth,
    cardTop: 0,
    cardHeight: chart.height,
    trackTop: chartArea.top - trackInset,
    trackHeight: chartArea.bottom - chartArea.top + trackInset * 2,
    fillTop: chartArea.top + fillOffset,
    fillBottom: chartArea.bottom + fillOffset,
  };
};

const reportCompetencyCardsPlugin = {
  id: 'reportCompetencyCards',
  beforeDatasetsDraw(chart, args, pluginOptions) {
    const meta = chart.getDatasetMeta(0);
    const xScale = chart.scales?.x;
    if (!meta || meta.hidden || !xScale || !chart.chartArea) {
      return;
    }

    const context = chart.ctx;
    const items = Array.isArray(pluginOptions?.items) ? pluginOptions.items : [];
    const { cardWidth, trackWidth, cardTop, cardHeight, trackTop, trackHeight } = getReportCompetencyCardMetrics(
      chart,
      meta,
      items,
    );

    context.save();
    meta.data.forEach((bar, index) => {
      const centerX = typeof xScale.getPixelForValue === 'function' ? xScale.getPixelForValue(index) : bar.x;
      const cardLeft = centerX - cardWidth / 2;
      const cardGradient = context.createLinearGradient(0, cardTop, 0, cardTop + cardHeight);
      cardGradient.addColorStop(0, '#d9f6f8');
      cardGradient.addColorStop(1, '#b3ebef');

      context.fillStyle = cardGradient;
      drawCanvasRoundedRect(context, cardLeft, cardTop, cardWidth, cardHeight, 18);
      context.fill();

      context.fillStyle = 'rgba(255, 255, 255, 0.78)';
      drawCanvasRoundedRect(context, centerX - trackWidth / 2, trackTop, trackWidth, trackHeight, trackWidth / 2);
      context.fill();
    });
    context.restore();
  },
  beforeDatasetDraw(chart, args) {
    if (args.index === 0) {
      return false;
    }
    return undefined;
  },
  afterDatasetsDraw(chart, args, pluginOptions) {
    const meta = chart.getDatasetMeta(0);
    const xScale = chart.scales?.x;
    const yScale = chart.scales?.y;
    if (!meta || meta.hidden || !xScale || !yScale || !chart.chartArea) {
      return;
    }

    const dataset = chart.data.datasets[0];
    const context = chart.ctx;
    const chartArea = chart.chartArea;
    const items = Array.isArray(pluginOptions?.items) ? pluginOptions.items : [];
    const { cardWidth, fillBottom, fillOffset, fillWidth } = getReportCompetencyCardMetrics(chart, meta, items);
    const valueY = Math.max(22, chartArea.top - 50);
    const labelY = Math.max(valueY + 24, chartArea.top - 24);

    context.save();
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    meta.data.forEach((bar, index) => {
      const value = Number(dataset.data[index]) || 0;
      const centerX = typeof xScale.getPixelForValue === 'function' ? xScale.getPixelForValue(index) : bar.x;
      const item = items[index] || {};

      if (value > 0) {
        const fillTop = yScale.getPixelForValue(value) + fillOffset;
        const fillHeight = Math.max(0, fillBottom - fillTop);
        const fillGradient = context.createLinearGradient(0, fillBottom, 0, fillTop);
        fillGradient.addColorStop(0, '#18b8c6');
        fillGradient.addColorStop(0.54, '#18b8c6');
        fillGradient.addColorStop(1, '#18b8c6');
        context.fillStyle = fillGradient;
        drawCanvasRoundedRect(context, centerX - fillWidth / 2, fillTop, fillWidth, fillHeight, fillWidth / 2);
        context.fill();
      }

      context.fillStyle = '#18b8c6';
      context.font = '800 26px Inter, sans-serif';
      context.fillText(value + '%', centerX, valueY);

      context.fillStyle = '#222c30';
      context.font = '800 11px Inter, sans-serif';
      drawWrappedCanvasText(context, item.competency || 'Компетенция', centerX, labelY, cardWidth - 18, 14);
    });
    context.restore();
  },
};

const getReportCompetencyGradient = () => 'rgba(24, 184, 198, 0)';

const buildReportCompetencyFallbackMarkup = (summary) =>
  summary
    .map(
      (item) =>
        '<article class="card card--inset report-competency-bar-card">' +
        '<strong>' +
        item.avgPercent +
        '%</strong>' +
        '<span>' +
        escapeHtml(item.competency) +
        '</span>' +
        '<div class="report-competency-meter"><div class="report-competency-meter-fill" style="--report-competency-percent:' +
        item.avgPercent +
        '%;height:' +
        item.avgPercent +
        '%"></div></div>' +
        '</article>',
    )
    .join('');

const renderReportCompetencyBarChart = (summary = []) => {
  if (!reportCompetencyBars) {
    return;
  }

  destroyReportCompetencyBarChart();

  const items = (Array.isArray(summary) ? summary : []).map((item) => ({
    competency: String(item.competency || 'Компетенция'),
    avgPercent: Math.max(0, Math.min(100, Number(item.avgPercent) || 0)),
  }));

  if (reportCompetencyBarChartCanvas) {
    reportCompetencyBarChartCanvas.classList.add('hidden');
  }
  if (reportCompetencyBarsFallback) {
    reportCompetencyBarsFallback.classList.add('hidden');
    reportCompetencyBarsFallback.innerHTML = '';
  }

  if (!items.length) {
    if (reportCompetencyBarsFallback) {
      reportCompetencyBarsFallback.textContent = 'Показатели по компетенциям появятся после завершения ассессмента.';
      reportCompetencyBarsFallback.classList.remove('hidden');
    }
    return;
  }

  if (reportCompetencyCompactQuery?.matches || typeof window.Chart !== 'function' || !reportCompetencyBarChartCanvas) {
    if (reportCompetencyBarsFallback) {
      reportCompetencyBarsFallback.innerHTML = buildReportCompetencyFallbackMarkup(items);
      reportCompetencyBarsFallback.classList.remove('hidden');
    }
    return;
  }

  const context = reportCompetencyBarChartCanvas.getContext('2d');
  if (!context) {
    if (reportCompetencyBarsFallback) {
      reportCompetencyBarsFallback.innerHTML = buildReportCompetencyFallbackMarkup(items);
      reportCompetencyBarsFallback.classList.remove('hidden');
    }
    return;
  }

  reportCompetencyBarChartCanvas.classList.remove('hidden');
  reportCompetencyBarChart = new window.Chart(context, {
    type: 'bar',
    data: {
      labels: items.map((item) => formatAdminChartLabel(item.competency)),
      datasets: [
        {
          data: items.map((item) => item.avgPercent),
          backgroundColor: getReportCompetencyGradient,
          hoverBackgroundColor: getReportCompetencyGradient,
          borderColor: 'rgba(24, 184, 198, 0.32)',
          hoverBorderColor: 'rgba(24, 184, 198, 0.32)',
          borderWidth: 0,
          hoverBorderWidth: 0,
          borderRadius: 999,
          borderSkipped: false,
          clip: false,
          barThickness: 34,
          maxBarThickness: 34,
          barPercentage: 1,
          categoryPercentage: 1,
        },
      ],
    },
    plugins: [reportCompetencyCardsPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {
        padding: {
          top: 82,
          right: 0,
          bottom: 36,
          left: 0,
        },
      },
      plugins: {
        reportCompetencyCards: {
          items,
        },
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: '#222c30',
          displayColors: false,
          titleFont: {
            family: 'Inter',
            size: 13,
            weight: '600',
          },
          bodyFont: {
            family: 'Inter',
            size: 12,
            weight: '500',
          },
          callbacks: {
            title(contextItems) {
              const item = items[contextItems[0]?.dataIndex ?? 0];
              return item?.competency || 'Компетенция';
            },
            label(context) {
              return context.formattedValue + '%';
            },
          },
        },
      },
      scales: {
        x: {
          display: false,
          grid: {
            display: false,
          },
          border: {
            display: false,
          },
          ticks: {
            display: false,
          },
        },
        y: {
          display: false,
          beginAtZero: true,
          min: 0,
          max: 100,
          ticks: {
            display: false,
          },
          grid: {
            display: false,
          },
          border: {
            display: false,
          },
        },
      },
    },
  });
};

export const renderReport = () => {
  const summary = getCompetencySummary();
  const totalScore = summary.length
    ? Math.round(summary.reduce((sum, item) => sum + item.avgPercent, 0) / summary.length)
    : 0;
  const interpretation = state.reportInterpretation || null;


  reportOverallScore.textContent = totalScore + '%';
  reportSummaryText.textContent =
    'Глубокий анализ оценок по четырем направлениям и детализация результатов по каждому навыку пользователя.';
  reportProfileAvatar.textContent = buildInitials(state.pendingUser ? state.pendingUser.full_name : 'Пользователь');
  reportProfileName.textContent = state.pendingUser?.full_name || 'Пользователь';
  reportProfileRole.textContent =
    sanitizeDisplayRole(state.pendingUser?.job_description || '') || 'Должность не указана';
  renderReportMetadata();

  reportRecommendations.innerHTML = '';
  const recommendationItems = getReportRecommendations(summary);
  recommendationItems.forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    reportRecommendations.appendChild(item);
  });

  renderReportCompetencyBarChart(summary);

  reportStrengthTitle.textContent = interpretation?.insight_title || 'AI insights пока недоступны';
  reportStrengthText.innerHTML = buildReportInsightMarkup(interpretation);

  const availableTabs = summary.map((item) => item.competency);
  if (!availableTabs.includes(state.reportCompetencyTab)) {
    state.reportCompetencyTab = availableTabs[0] || 'Коммуникация';
  }

  reportTabs.innerHTML = '';
  if (reportTabSelect) {
    reportTabSelect.innerHTML = '';
  }
  availableTabs.forEach((competency) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'report-tab-button' + (state.reportCompetencyTab === competency ? ' active' : '');
    button.textContent = competency;
    button.addEventListener('click', () => {
      state.reportCompetencyTab = competency;
      renderReport();
    });
    reportTabs.appendChild(button);

    if (reportTabSelect) {
      const option = document.createElement('option');
      option.value = competency;
      option.textContent = competency;
      option.selected = state.reportCompetencyTab === competency;
      reportTabSelect.appendChild(option);
    }
  });
  if (reportTabSelect) {
    reportTabSelect.onchange = () => {
      state.reportCompetencyTab = reportTabSelect.value;
      renderReport();
    };
  }

  reportDetailTitle.textContent = state.reportCompetencyTab;
  reportDetailList.innerHTML = '';
  const selected = summary.find((item) => item.competency === state.reportCompetencyTab);
  if (!selected) {
    reportDetailList.innerHTML = '<p class="report-empty-state">Данные по выбранной компетенции пока недоступны.</p>';
    return;
  }

  selected.skills.forEach((skill) => {
    const percent = getLevelPercent(skill.assessed_level_code);
    const artifactHint = buildArtifactHint(skill);
    const item = document.createElement('article');
    item.className = 'report-skill-row';
    item.innerHTML =
      '<div class="report-skill-name">' +
      buildReportSkillNameMarkup(skill) +
      (artifactHint ? '<span class="skill-artifact-hint">' + escapeHtml(artifactHint) + '</span>' : '') +
      '</div>' +
      '<div class="report-skill-level">' +
      escapeHtml(skill.assessed_level_name) +
      '</div>' +
      '<div class="report-skill-progress">' +
      '<div class="report-skill-progress-track"><div class="report-skill-progress-fill" style="width:' +
      percent +
      '%"></div></div>' +
      buildReportSkillScoreMarkup(skill, percent) +
      '</div>';
    reportDetailList.appendChild(item);

    const descriptionButton = item.querySelector('.report-skill-name-text');
    const description = getReportSkillDescription(skill);
    if (descriptionButton && description) {
      descriptionButton.addEventListener('click', (event) => {
        event.stopPropagation();
        openReportInfoModal({
          eyebrow: 'Описание навыка',
          title: skill.skill_name || 'Навык',
          bodyMarkup: '<p class="report-info-text">' + escapeHtml(description) + '</p>',
        });
      });
    }

    const scoreButton = item.querySelector('.report-skill-score-text');
    const scoreDetails = getReportSkillScoreDetails(skill, percent);
    if (scoreButton && scoreDetails.hasDetails) {
      scoreButton.addEventListener('click', (event) => {
        event.stopPropagation();
        openReportInfoModal({
          eyebrow: 'Объяснение оценки',
          title: (skill.skill_name || 'Навык') + ' · ' + percent + '%',
          bodyMarkup: scoreDetails.markup || '<p class="report-info-text">Детали оценки пока недоступны.</p>',
        });
      });
    }
  });
};

let m8FreshnessController;

const correctionFieldLabels = {
  score: 'Показатель', outcome: 'Вывод', presentation: 'Пояснение вывода',
  comparison: 'Сопоставление', limitations: 'Ограничения', progress: 'Ход оценки',
  partial_limitations: 'Причины ограничения', summary: 'Краткий вывод', explanation: 'Наблюдения и объяснение',
};

const coverageNames = {
  opportunities: 'Возможность наблюдения', indicator_assessments: 'Оценённые индикаторы',
  admissible_contributions: 'Допущенные вклады', components_with_score: 'Компоненты с показателем',
  complete_components: 'Полные компоненты',
};
const comparisonNames = {
  NO_TARGET_REQUIREMENT: 'Для навыка нет целевого требования.',
  NO_SKILL_RESULT: 'Для навыка нет обоснованного результата.',
  NOT_COMPARABLE: 'Сопоставление с целью пока недоступно.',
};
const correctionLabel = (item) => {
  if (item.field?.startsWith('coverage:')) {
    const [, scope, name] = item.field.split(':');
    return `${coverageNames[name] || 'Полнота данных'} · ${scope === 'cycle_plan' ? 'план' : 'весь каталог'}`;
  }
  return correctionFieldLabels[item.field] || 'Изменение';
};

const correctionValue = (field, value) => {
  if (value == null || (Array.isArray(value) && !value.length)) return 'Не указано';
  if (field === 'score') return value.value == null ? 'Без числового показателя' :
    `${value.value}${value.denominator ? ` (${value.numerator}/${value.denominator})` : ''}`;
  if (field === 'presentation') {
    const parts = [value.label, ...(value.reasons || []).map((reason) => reason.message)].filter(Boolean);
    if (value.remaining_plan_relevant === true) parts.push('В оставшемся плане есть связанные ситуации.');
    if (value.remaining_plan_relevant === false) parts.push('В оставшемся плане связанных ситуаций нет.');
    return parts.join(' ') || 'Не указано';
  }
  if (field === 'outcome') return outcomeLabels[value] || value;
  if (field === 'comparison') return comparisonNames[value.status] || 'Сопоставление не указано';
  if (field === 'explanation') return value.map((item) => item.text).join('; ') || 'Не указано';
  if (field.startsWith('coverage:')) return `${value.numerator ?? 0} из ${value.denominator ?? 0}`;
  if (field === 'progress') return `${value.completed ?? 0} из ${value.planned ?? 0} ситуаций`;
  if (field === 'partial_limitations') return value.map((item) => item.message).join('; ') || 'Не указано';
  if (Array.isArray(value)) return value.join('; ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const renderM8Correction = (notice) => {
  const node = document.getElementById('m8-report-correction');
  if (!node) return;
  node.classList.toggle('hidden', !notice);
  if (!notice) { node.replaceChildren(); return; }
  const changes = (notice.changes || []).map((item) => `
    <article class="m8-correction-item"><strong>${escapeHtml(item.skill_name || 'Отчёт')} · ${escapeHtml(correctionLabel(item))}</strong>
      <div class="m8-correction-pair"><div><span>Было</span>${escapeHtml(correctionValue(item.field, item.before))}</div>
      <div><span>Стало</span>${escapeHtml(correctionValue(item.field, item.after))}</div></div></article>`).join('');
  node.innerHTML = `<h3>В отчёт внесено исправление</h3><p>${escapeHtml(formatParticipantDate(notice.created_at))} · ${escapeHtml(notice.reason)}</p>
    <details><summary>Посмотреть, что изменилось</summary><div class="m8-correction-list">${changes}</div></details>`;
};

export const downloadSelectedReportPdf = () => {
  const button = document.getElementById('report-download-button');
  const status = document.getElementById('report-download-status');
  const reportId = button.dataset.m8ReportId;
  const access = button.dataset.m8ReportAccess;
  if (!reportId) {
    status.textContent = 'PDF доступен после подготовки отчёта.';
    return;
  }
  return downloadReportPdf({ button, status,
    url: access === 'customer'
      ? '/users/admin/m8-access/reports/' + encodeURIComponent(reportId) + '/pdf'
      : '/users/assessment/m8/reports/' + encodeURIComponent(reportId) + '/pdf',
    filename: `4k-report-${reportId}.pdf`,
    isCurrent: () => button.dataset.m8ReportId === reportId && button.dataset.m8ReportAccess === access,
  });
};

export const openReport = (options = {}) => {
  const { returnTarget = 'home', m8CycleId = null, m8ReportId = null, customerAccess = false } = options;
  if (!m8CycleId) {
    void openReports();
    return;
  }
  const requestEpoch = ++state.reportRequestEpoch;
  const identityEpoch = state.identityEpoch;
  const ownerId = state.pendingUser?.id;
  const isCurrent = () => state.reportRequestEpoch === requestEpoch && state.identityEpoch === identityEpoch && state.pendingUser?.id === ownerId && state.currentScreen === 'report';
  state.reportReturnTarget = ['reports', 'admin-reports'].includes(returnTarget) ? returnTarget : 'home';
  setCurrentScreen('report');
  syncUrlState('report');
  hideAllPanels();
  reportPanel.classList.remove('hidden');
  reportPanel.classList.toggle('is-m8-report', Boolean(m8CycleId));
  if (m8CycleId) {
    m8FreshnessController?.abort();
    m8FreshnessController = new AbortController();
    m8SelectedSkillId = null;
    m8SelectedCompetencyId = null;
    m8ChartRenderContext = null;
    window.clearTimeout(reportInfoModalCloseTimer);
    reportInfoModalCloseTimer = null;
    reportInfoModal?.classList.add('hidden');
    reportInfoModal?.classList.remove('is-open', 'is-closing');
    reportInfoModal?.setAttribute('aria-hidden', 'true');
    reportInfoModalBody?.replaceChildren();
    document.body.classList.remove('report-info-modal-open');
    document.querySelectorAll('#m8-report-chart-modes button').forEach((button) => {
      button.disabled = true;
      button.onclick = null;
    });
    const legacy = document.getElementById('legacy-report-shell');
    const shell = document.getElementById('m8-report-shell');
    legacy?.classList.add('hidden'); shell?.classList.remove('hidden');
    requestAnimationFrame(() => document.getElementById('m8-report-title')?.focus({ preventScroll: true }));
    for (const id of ['m8-report-detail', 'm8-report-summary', 'm8-report-partial', 'm8-report-update', 'report-download-status', 'm8-report-metadata', 'm8-report-tabs', 'm8-report-tab-select', 'm8-report-chart', 'm8-report-chart-note', 'm8-report-skills', 'm8-report-coverage', 'm8-report-limitations', 'm8-report-recommendations', 'm8-report-recommendation-notices']) {
      document.getElementById(id)?.replaceChildren();
    }
    const comparisonButton = document.getElementById('m8-comparison-open');
    if (comparisonButton) { comparisonButton.disabled = true; comparisonButton.onclick = null; }
    const comparisonSelect = document.getElementById('m8-comparison-select');
    if (comparisonSelect) {
      comparisonSelect.disabled = true;
      comparisonSelect.onchange = null;
      comparisonSelect.innerHTML = '<option value="">Последняя завершённая</option>';
    }
    const comparisonContent = document.getElementById('m8-comparison-content');
    if (comparisonContent) comparisonContent.innerHTML = '<p>Сравнение доступно для завершённых оценок.</p>';
    document.getElementById('m8-report-state').textContent = 'Открываем результат…';
    document.getElementById('m8-report-tab-select').onchange = null;
    document.getElementById('m8-report-partial')?.classList.add('hidden');
    renderM8Correction(null);
    document.getElementById('m8-report-update')?.classList.add('hidden');
    const download = document.getElementById('report-download-button');
    resetReportDownload(download);
    delete download.dataset.m8ReportId;
    delete download.dataset.m8ReportAccess;
    download.disabled = true;
    const url = new URL(window.location.href); url.searchParams.set('screen', 'report'); url.searchParams.set('cycle_id', m8CycleId);
    if (m8ReportId) url.searchParams.set('report_id', m8ReportId);
    else url.searchParams.delete('report_id');
    if (customerAccess) url.searchParams.set('report_access', 'customer');
    else url.searchParams.delete('report_access');
    window.history.replaceState({}, '', url.pathname + '?' + url.searchParams.toString());
    const load = () => {
      if (!isCurrent()) return;
      document.getElementById('m8-report-state').textContent = 'Открываем результат…';
      void loadM8Report(m8CycleId, m8ReportId, isCurrent, ownerId, customerAccess).catch(() => {
        if (!isCurrent()) return;
        const stateNode = document.getElementById('m8-report-state');
        if (!stateNode) return;
        stateNode.innerHTML = 'Не удалось открыть результат. <button class="ghost-button compact-ghost" type="button">Повторить</button>';
        stateNode.querySelector('button')?.addEventListener('click', load, { once: true });
      });
    };
    load();
    return;
  }
};

const outcomeLabels = {
  full_score: 'Результат по полному составу навыка',
  partial_score: 'Результат по части навыка',
  result_without_score: 'Есть наблюдения без общего балла по навыку',
  no_result: 'Недостаточно оснований для результата',
};

const coverageLabels = {
  opportunities: 'Фактическая возможность наблюдения',
  indicator_assessments: 'Обоснованные оценки индикаторов',
  admissible_contributions: 'Ответы, которые можно учесть в результате',
  components_with_score: 'Компоненты с баллом',
  complete_components: 'Полностью оценённые компоненты',
};

let m8ChartMode = 'fill';
let m8SelectedCompetencyId = null;
let m8SelectedSkillId = null;
let m8ChartResizeObserver = null;
let m8ChartResizeHandler = null;
let m8ChartRenderContext = null;
let m8ObservedChartWidth = 0;

const splitRadarLabel = (skill) => {
  const words = String(skill.skill_name || 'Навык').trim().split(/\s+/).filter(Boolean);
  if (words.length < 2) return [words[0] || 'Навык'];
  const midpoint = Math.ceil(words.length / 2);
  return [words.slice(0, midpoint).join(' '), words.slice(midpoint).join(' ')];
};

const fitM8RadarLabels = (node) => {
  const svg = node?.querySelector('svg');
  if (!svg) return;
  const safeInset = 24;
  const gap = 8;
  const width = Number(svg.viewBox?.baseVal?.width) || 960;
  const height = Number(svg.viewBox?.baseVal?.height) || 560;
  const sides = { left: [], right: [] };
  svg.querySelectorAll('.m8-radar-label').forEach((label) => {
    label.removeAttribute('transform');
    const box = label.getBBox();
    const side = label.dataset.m8Side === 'left' ? 'left' : 'right';
    const anchorY = Number(label.dataset.m8AnchorY);
    const dx = Math.max(safeInset - box.x, Math.min(0, width - safeInset - box.x - box.width));
    sides[side].push({ label, box, anchorY, dx, top: anchorY - box.height / 2 });
  });
  Object.values(sides).forEach((entries) => {
    entries.sort((a, b) => a.anchorY - b.anchorY);
    let nextTop = safeInset;
    entries.forEach((entry) => {
      entry.top = Math.max(nextTop, entry.top);
      nextTop = entry.top + entry.box.height + gap;
    });
    let bottom = height - safeInset;
    for (let index = entries.length - 1; index >= 0; index -= 1) {
      const entry = entries[index];
      entry.top = Math.min(entry.top, bottom - entry.box.height);
      bottom = entry.top - gap;
    }
    entries.forEach(({ label, box, top, dx }) => {
      const dy = top - box.y;
      label.setAttribute('transform', `translate(${dx.toFixed(1)} ${dy.toFixed(1)})`);
      const leader = label.parentElement.querySelector('.m8-radar-leader');
      if (!leader) return;
      const left = box.x + dx;
      const right = left + box.width;
      const side = label.dataset.m8Side;
      const axisX = Number(label.dataset.m8AxisX);
      const axisY = Number(label.dataset.m8AxisY);
      const labelX = side === 'left' ? right + 6 : left - 6;
      const labelY = top + box.height / 2;
      leader.setAttribute('points', `${axisX},${axisY} ${labelX.toFixed(1)},${labelY.toFixed(1)}`);
    });
  });
};

const scheduleM8RadarLabelFit = (node) => {
  fitM8RadarLabels(node);
  window.requestAnimationFrame(() => fitM8RadarLabels(node));
  document.fonts?.ready?.then(() => fitM8RadarLabels(node));
};

const buildM8Bars = (skills) => `<div class="m8-score-bars" role="list">${projectReportRadar(skills).axes.map((axis, index) => {
  const skill = skills[index];
  const value = axis.value;
  const status = axis.status || outcomeLabels[skill.outcome] || 'Результат требует проверки';
  return `<article class="m8-score-bar" role="listitem"><button type="button" class="${String(skill.skill_id) === String(m8SelectedSkillId) ? 'is-selected' : ''}" data-m8-skill-id="${escapeHtml(String(skill.skill_id))}" aria-pressed="${String(skill.skill_id) === String(m8SelectedSkillId)}">${escapeHtml(skill.skill_name || 'Навык')}</button>` +
    (value == null
      ? `<span class="m8-score-missing">${escapeHtml(status)}</span>`
      : `<div class="m8-score-track" role="img" aria-label="${escapeHtml(`${axis.name}: ${axis.displayValue} из 3. ${status}`)}"><span class="${axis.partial ? 'is-partial' : ''}" style="--m8-score:${value / 3 * 100}%"></span></div><strong>${escapeHtml(axis.displayValue)}</strong>`) +
    `</article>`;
}).join('')}</div>`;

const buildM8Radar = (skills, mode, { compact = false, chartWidth = 960 } = {}) => {
  const { axes, runs } = projectReportRadar(skills);
  const values = axes.map((axis) => axis.value);
  const width = chartWidth;
  const height = compact ? Math.max(360, width * 1.16) : 560;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = compact ? Math.min(width * 0.30, height * 0.29, 132) : Math.min(170, width * 0.23);
  const count = skills.length;
  const angle = (index) => -Math.PI / 2 + index * Math.PI * 2 / count;
  const point = (index, value) => radarPoint(index, value, count, centerX, centerY, radius);
  const polygon = (level) => skills.map((_, index) => {
    const value = point(index, level);
    return `${value.x.toFixed(1)},${value.y.toFixed(1)}`;
  }).join(' ');
  const description = axes.map((axis) => `${axis.name}: ${axis.value == null ? 'без числового показателя' : `${axis.displayValue} из 3${axis.partial ? ', частичный показатель' : ''}`}`).join('. ');
  const selectedMarkup = (skill) => String(skill.skill_id) === String(m8SelectedSkillId) ? ' class="is-selected" aria-current="true"' : '';
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="m8-radar-title m8-radar-description"><title id="m8-radar-title">Показатели навыков выбранной компетенции</title><desc id="m8-radar-description">Шкала от 0 до 3. ${escapeHtml(description)}. Полный текстовый список расположен после графика.</desc>`;
  for (let level = 1; level <= 3; level += 1) {
    svg += `<polygon points="${polygon(level)}" class="m8-radar-grid"/><text x="${centerX + 8}" y="${centerY - radius * level / 3 + 4}" class="m8-radar-scale">${level}</text>`;
  }
  svg += `<text x="${centerX + 8}" y="${centerY + 14}" class="m8-radar-scale">0</text>`;
  skills.forEach((skill, index) => {
    const end = point(index, 3);
    if (compact) {
      const marker = point(index, 3.85);
      svg += `<line x1="${centerX}" y1="${centerY}" x2="${end.x}" y2="${end.y}" class="m8-radar-axis"/>` +
        `<a href="#m8-skill-detail"${selectedMarkup(skill)} data-m8-skill-id="${escapeHtml(String(skill.skill_id))}" aria-label="${escapeHtml(`${index + 1}. ${skill.skill_name || 'Навык'}. Открыть подробности`)}">` +
        `<circle cx="${marker.x.toFixed(1)}" cy="${marker.y.toFixed(1)}" r="15" class="m8-radar-marker-bg"/>` +
        `<text x="${marker.x.toFixed(1)}" y="${marker.y.toFixed(1)}" class="m8-radar-marker" text-anchor="middle" dominant-baseline="central">${index + 1}</text></a>`;
      return;
    }
    const label = point(index, 3.84);
    const side = Math.cos(angle(index)) < 0 ? 'left' : 'right';
    const labelX = side === 'left' ? 20 : width - 20;
    const lines = splitRadarLabel(skill);
    const startY = label.y - (lines.length - 1) * 8;
    const labelMarkup = lines.map((line, lineIndex) =>
      `<tspan x="${labelX}" y="${startY + lineIndex * 16}">${escapeHtml(line)}</tspan>`
    ).join('');
    svg += `<line x1="${centerX}" y1="${centerY}" x2="${end.x}" y2="${end.y}" class="m8-radar-axis"/><a href="#m8-skill-detail"${selectedMarkup(skill)} data-m8-skill-id="${escapeHtml(String(skill.skill_id))}" aria-label="${escapeHtml(`${skill.skill_name || 'Навык'}. Открыть подробности`)}"><polyline class="m8-radar-leader"/><text x="${labelX}" y="${startY}" text-anchor="${side === 'left' ? 'start' : 'end'}" class="m8-radar-label" data-m8-side="${side}" data-m8-anchor-y="${label.y.toFixed(1)}" data-m8-axis-x="${end.x.toFixed(1)}" data-m8-axis-y="${end.y.toFixed(1)}">${labelMarkup}</text></a>`;
  });
  runs.forEach((run) => {
    const points = run.indexes.map((index) => point(index, values[index]));
    if (mode === 'fill' && points.length >= 2) {
      const fillPoints = run.closed ? points : [{ x: centerX, y: centerY }, ...points];
      svg += `<polygon points="${fillPoints.map((item) => `${item.x},${item.y}`).join(' ')}" class="m8-radar-fill"/>`;
    }
    if (points.length >= 2) {
      const tag = run.closed ? 'polygon' : 'polyline';
      svg += `<${tag} points="${points.map((item) => `${item.x},${item.y}`).join(' ')}" class="m8-radar-line"/>`;
    }
  });
  skills.forEach((skill, index) => {
    if (values[index] == null) return;
    const value = point(index, values[index]);
    svg += `<a href="#m8-skill-detail"${selectedMarkup(skill)} data-m8-skill-id="${escapeHtml(String(skill.skill_id))}" aria-label="${escapeHtml(`${skill.skill_name || 'Навык'}: ${axes[index].displayValue} из 3${axes[index].partial ? ', частичный показатель' : ''}. Открыть подробности`)}"><circle cx="${value.x}" cy="${value.y}" r="16" class="m8-radar-hit"/>${String(skill.skill_id) === String(m8SelectedSkillId) ? `<circle cx="${value.x}" cy="${value.y}" r="11" class="m8-radar-selection"/>` : ''}<circle cx="${value.x}" cy="${value.y}" r="6" class="m8-radar-point${skill.outcome === 'partial_score' ? ' is-partial' : ''}"/></a>`;
  });
  const key = compact ? `<ol class="m8-radar-key" aria-label="Навыки на схеме">${skills.map((skill, index) =>
    `<li><a href="#m8-skill-detail"${selectedMarkup(skill)} data-m8-skill-id="${escapeHtml(String(skill.skill_id))}">` +
    `<span class="m8-radar-key-marker" aria-hidden="true">${index + 1}</span>` +
    `<span class="m8-radar-key-name">${escapeHtml(skill.skill_name || 'Навык')}</span>` +
    `<span class="m8-radar-key-value">${values[index] == null ? 'Нет числового показателя' : `${escapeHtml(axes[index].displayValue)} из 3${skill.outcome === 'partial_score' ? ' · частичный результат' : ''}`}</span>` +
    `</a></li>`).join('')}</ol>` : '';
  return `${svg}</svg>${key}`;
};

const focusM8Skill = (skillId) => {
  if (!m8ChartRenderContext?.c67?.skills?.some((skill) => String(skill.skill_id) === String(skillId))) return;
  m8SelectedSkillId = skillId;
  renderM8Skills(m8ChartRenderContext.c67, m8ChartRenderContext.competencyId);
  renderM8Chart(m8ChartRenderContext.c67, m8ChartRenderContext.competencyId);
  document.getElementById('m8-skill-detail')?.focus({ preventScroll: true });
};

const renderM8Chart = (c67, competencyId) => {
  const node = document.getElementById('m8-report-chart');
  const note = document.getElementById('m8-report-chart-note');
  const style = window.getComputedStyle(node);
  const contentWidth = node.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  const compact = competencyId !== 'all' && (window.matchMedia('(max-width: 960px)').matches || contentWidth < 800);
  const mobileOverview = competencyId === 'all' && window.matchMedia('(max-width: 720px)').matches;
  m8ChartRenderContext = { c67, competencyId, compact, mobileOverview };
  document.querySelectorAll('#m8-report-chart-modes [data-chart-mode]').forEach((button) => {
    button.disabled = mobileOverview && button.dataset.chartMode !== 'bars';
  });
  if (!m8ChartResizeHandler) {
    m8ChartResizeHandler = () => {
      const context = m8ChartRenderContext;
      if (!context) return;
      renderM8Chart(context.c67, context.competencyId);
    };
    window.addEventListener('resize', m8ChartResizeHandler);
  }
  m8ObservedChartWidth = Math.round(contentWidth);
  if (!m8ChartResizeObserver && typeof ResizeObserver !== 'undefined') {
    m8ChartResizeObserver = new ResizeObserver(([entry]) => {
      const nextWidth = Math.round(entry.contentRect.width);
      if (!nextWidth || !m8ChartRenderContext) return;
      const nextCompact = m8ChartRenderContext.competencyId !== 'all' && (window.matchMedia('(max-width: 960px)').matches || nextWidth < 800);
      const nextMobileOverview = m8ChartRenderContext.competencyId === 'all' && window.matchMedia('(max-width: 720px)').matches;
      if (nextWidth === m8ObservedChartWidth && nextCompact === m8ChartRenderContext.compact && nextMobileOverview === m8ChartRenderContext.mobileOverview) return;
      m8ObservedChartWidth = nextWidth;
      if (nextCompact || nextCompact !== m8ChartRenderContext.compact || nextMobileOverview !== m8ChartRenderContext.mobileOverview) {
        renderM8Chart(m8ChartRenderContext.c67, m8ChartRenderContext.competencyId);
      } else if (m8ChartMode !== 'bars') {
        scheduleM8RadarLabelFit(node);
      }
    });
    m8ChartResizeObserver.observe(node);
  }
  const isOverview = competencyId === 'all';
  const chartWidth = Math.max(200, Math.floor(contentWidth));
  const skills = isOverview
    ? (c67.skills || [])
    : (c67.skills || []).filter((skill) => String(skill.competency_id) === String(competencyId));
  const mode = mobileOverview ? 'bars' : m8ChartMode;
  document.querySelectorAll('#m8-report-chart-modes [data-chart-mode]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.chartMode === mode));
  });
  node.classList.toggle('is-overview', isOverview);
  node.classList.toggle('is-compact', compact);
  const summary = summarizeReportScores(skills);
  if (!summary.hasScores) {
    node.innerHTML = '<div class="m8-chart-empty"><strong>Числовых показателей нет</strong><p>Доступные наблюдения и причины отсутствия результата приведены в списке ниже.</p></div>';
    note.textContent = 'Отсутствующие значения не заменяются нулями.';
  } else {
    node.innerHTML = mode === 'bars' ? buildM8Bars(skills) : buildM8Radar(skills, mode, { compact, chartWidth });
    if (mode !== 'bars' && !compact) scheduleM8RadarLabelFit(node);
    note.textContent = mobileOverview
      ? 'Все навыки показаны шкалами. Выберите компетенцию, чтобы увидеть её радиальную схему.'
      : summary.missingCount
        ? 'Пропуски оставлены открытыми: линия и заливка через них не продолжаются.'
        : 'Каждая ось — отдельный навык. Площадь фигуры не является общим баллом.';
  }
  node.querySelectorAll('[data-m8-skill-id]').forEach((item) => item.addEventListener('click', (event) => {
    event.preventDefault();
    focusM8Skill(item.dataset.m8SkillId);
  }));
};

const formatParticipantDate = (value) => {
  const date = parseApiDateTime(value);
  return date ? date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' }) : 'Дата не указана';
};

const formatExactScore = (score) => {
  if (!score || score.value == null) return 'Числовой показатель не сформирован';
  return `${score.value}`;
};

const coverageLabel = (cut) => {
  if (!cut || cut.denominator == null) return 'не передано';
  if (cut.denominator === 0 || cut.ratio == null) return `${cut.numerator}/${cut.denominator} · доля не определена`;
  return `${cut.numerator}/${cut.denominator} · ${(cut.ratio * 100).toFixed(1)}%`;
};

const coverageContextLabel = (cut) => {
  if (!cut || cut.denominator == null) return 'не передано';
  return `${cut.numerator}/${cut.denominator}`;
};

const comparisonReasonLabels = {
  different_role: 'Роли в оценках различаются.',
  role_snapshot_missing: 'Не сохранено достаточное подтверждение роли.',
  m2_composition_not_confirmed: 'Совпадение состава навыков не подтверждено.',
  m2_sources_not_confirmed: 'Совпадение версий методологии не подтверждено.',
  m6_rules_not_confirmed: 'Совпадение правил расчёта не подтверждено.',
  assessment_context_not_confirmed: 'Сопоставимость условий оценки не подтверждена.',
  role_requirements_not_confirmed: 'Сопоставимость требований роли не подтверждена.',
  partial_cycle: 'Одна из оценок завершена не полностью.',
  full_score_required: 'Для одного из срезов нет полного результата по навыку.',
  numeric_score_missing: 'В одном из срезов нет числового результата.',
  skill_definition_not_confirmed: 'Совпадение определения навыка не подтверждено.',
  skill_absent_in_previous_cycle: 'В предыдущей оценке навык отсутствует.',
  skill_absent_in_current_cycle: 'В текущей оценке навык отсутствует.',
  skill_composition_not_confirmed: 'Состав показателя по навыку не подтверждён.',
  skill_composition_changed: 'Обязательный или включённый состав показателя изменился.',
  score_completeness_changed: 'Полный и частичный результаты не являются одним показателем.',
};

const comparisonScore = (value) => value == null ? 'Нет результата' : String(value);

const comparisonRole = (reference) => reference?.name || reference?.title || reference?.role_name || 'Роль не указана';

const renderM8Comparison = (comparison, isCurrent) => {
  const node = document.getElementById('m8-comparison-content');
  if (!node) return;
  const allowed = comparison.skills.filter((item) => item.comparability.status === 'allowed');
  const separate = comparison.skills.filter((item) => item.comparability.status !== 'allowed');
  const periods = `<dl class="m8-comparison-periods"><div><dt>Предыдущее прохождение</dt><dd>${escapeHtml(comparison.previous.program_name || 'Оценка 4К')}</dd><dd>${escapeHtml(formatParticipantDate(comparison.previous.closed_at || comparison.previous.created_at))}</dd><dd>${escapeHtml(comparisonRole(comparison.previous.role_ref))}</dd></div>` +
    `<div><dt>Текущее прохождение</dt><dd>${escapeHtml(comparison.current.program_name || 'Оценка 4К')}</dd><dd>${escapeHtml(formatParticipantDate(comparison.current.closed_at || comparison.current.created_at))}</dd><dd>${escapeHtml(comparisonRole(comparison.current.role_ref))}</dd></div></dl>`;
  const table = allowed.length ? `<div class="m8-comparison-table-wrap"><table class="m8-comparison-table"><thead><tr><th>Навык</th><th>Предыдущая</th><th>Текущая</th><th>Разница</th></tr></thead><tbody>${allowed.map((item) =>
    `<tr><th>${escapeHtml(item.skill_name)}</th><td>${escapeHtml(comparisonScore(item.previous))}</td><td>${escapeHtml(comparisonScore(item.current))}</td><td>${escapeHtml(String(item.difference))}</td></tr>`
  ).join('')}</tbody></table></div>` : '';
  const slices = separate.length ? `<div class="m8-comparison-slices"><p><strong>${allowed.length ? 'Остальные навыки показаны отдельными срезами' : 'Числовое сравнение недоступно'}</strong></p>${separate.map((item) =>
    `<article><strong>${escapeHtml(item.skill_name)}</strong><span>Предыдущая: ${escapeHtml(comparisonScore(item.previous))}</span><span>Текущая: ${escapeHtml(comparisonScore(item.current))}</span><p>${escapeHtml(comparisonReasonLabels[item.comparability.reason] || 'Сопоставимость не подтверждена.')}</p></article>`
  ).join('')}</div>` : '';
  const pdfQuery = `?previous_report_id=${encodeURIComponent(comparison.previous.report_id)}`;
  const pdf = '<div class="report-pdf-action"><button type="button" class="ghost-button compact-ghost">Скачать сравнение PDF</button><span class="report-pdf-status" role="status"></span></div>';
  const scale = `<div class="m8-comparison-scales"><h4>Показатели по навыкам</h4><p>Сравнимые значения показаны с разностью. Остальные — раздельно с причиной.</p>${comparison.skills.map((item) => {
    const bar = (value, label, kind) => `<div class="m8-comparison-scale-line"><span>${label}</span><span class="m8-comparison-track"><span class="${kind}" style="width:${value == null ? 0 : Math.max(0, Math.min(100, Number(value) / 3 * 100))}%"></span></span><strong>${escapeHtml(comparisonScore(value))}</strong></div>`;
    return `<div class="m8-comparison-scale"><strong>${escapeHtml(item.skill_name)}</strong>${bar(item.previous, 'Ранее', 'm8-comparison-past')}${bar(item.current, 'Сейчас', 'm8-comparison-now')}${item.comparability.status !== 'allowed' ? `<small>${escapeHtml(comparisonReasonLabels[item.comparability.reason] || 'Сопоставимость не подтверждена.')}</small>` : ''}</div>`;
  }).join('')}</div>`;
  node.innerHTML = periods + `<p class="m8-comparison-note">Разность расчётных показателей не доказывает развитие навыка и не означает процент роста.</p>` + scale + table + slices + pdf;
  bindReportPdf(node.querySelector('.report-pdf-action button'), {
    status: node.querySelector('.report-pdf-status'), isCurrent,
    url: `/users/assessment/m8/reports/${encodeURIComponent(comparison.current.report_id)}/comparison.pdf${pdfQuery}`,
    filename: `4k-report-comparison-${comparison.current.report_id}.pdf`,
  });
};

const loadM8Comparison = async (reportId, previousReportId = '', isCurrent = () => true) => {
  const node = document.getElementById('m8-comparison-content');
  if (!node) return;
  node.innerHTML = '<p>Загружаем предыдущую завершённую оценку…</p>';
  try {
    const suffix = previousReportId ? `?previous_report_id=${encodeURIComponent(previousReportId)}` : '';
    const response = await fetch(`/users/assessment/m8/reports/${encodeURIComponent(reportId)}/comparison${suffix}`);
    if (!isCurrent()) return;
    if (response.status === 404) {
      node.innerHTML = '<p><strong>Предыдущей завершённой оценки пока нет.</strong></p>';
      return;
    }
    const comparison = await readApiResponse(response, 'Не удалось загрузить сравнение оценок.');
    if (isCurrent() && String(comparison.current?.report_id) === String(reportId)
      && String(comparison.previous?.report_id) === String(previousReportId)) renderM8Comparison(comparison, isCurrent);
    else if (isCurrent()) node.innerHTML = '<p>Выбранную пару оценок не удалось подтвердить.</p>';
  } catch (_error) {
    if (isCurrent()) node.innerHTML = '<p><strong>Сравнение временно недоступно.</strong> Попробуйте ещё раз.</p>';
  }
};

const setupM8ComparisonOptions = async (cycleId, reportId, isCurrent) => {
  const select = document.getElementById('m8-comparison-select');
  const button = document.getElementById('m8-comparison-open');
  if (!select || !button) return;
  try {
    const history = await readApiResponse(await fetch('/users/assessment/m8/history'), 'Не удалось загрузить историю оценок.');
    if (!isCurrent()) return;
    const current = history.cycles.find((item) => String(item.cycle_id) === String(cycleId));
    const candidates = history.cycles.filter((item) => String(item.cycle_id) !== String(cycleId)
      && item.report_id && item.collection_closed_at && item.status !== 'failed'
      && current?.collection_closed_at && new Date(item.collection_closed_at) < new Date(current.collection_closed_at));
    select.innerHTML = candidates.map((item) => `<option value="${escapeHtml(item.report_id)}">${escapeHtml(item.program_name || 'Оценка 4К')} · ${escapeHtml(formatParticipantDate(item.collection_closed_at))}</option>`).join('') || '<option value="">Других завершённых оценок нет</option>';
    select.disabled = candidates.length === 0;
  } catch (_error) {
    if (!isCurrent()) return;
    select.innerHTML = '<option value="">Последняя завершённая</option>';
    select.disabled = true;
  }
  button.disabled = select.disabled;
  let selectionEpoch = 0;
  select.onchange = () => {
    selectionEpoch += 1;
    const content = document.getElementById('m8-comparison-content');
    if (content) content.innerHTML = '<p>Выберите «Сравнить оценки», чтобы открыть эту пару.</p>';
  };
  button.onclick = () => {
    const selectedId = select.value;
    const epoch = ++selectionEpoch;
    void loadM8Comparison(reportId, selectedId, () => isCurrent() && epoch === selectionEpoch && select.value === selectedId);
  };
};

const buildSkillNarrative = (claims) => [
  ['observation', 'Наблюдавшееся действие'],
  ['explanation', 'Что означает результат'],
  ['context', 'Как это связано с вашей работой'],
].map(([kind, heading]) => {
  const items = claims.filter((item) => item.kind === kind && item.text);
  return items.length ? `<section class="m8-skill-narrative"><h5>${heading}</h5>${items.map((item) => `<p>${escapeHtml(item.text)}</p>`).join('')}</section>` : '';
}).join('');

const buildSkillDetails = (skill, claims) => {
  const excerpts = claims.filter((item) => item.kind === 'quote' && item.text);
  const limitations = [...new Set([
    ...(Array.isArray(skill.limitations) ? skill.limitations : []),
    ...claims.filter((item) => item.kind === 'limitation' && item.text).map((item) => item.text),
    ...claims.flatMap((item) => item.limitations || []),
  ])];
  if (!excerpts.length && !limitations.length) return '';
  return `<details class="m8-skill-basis"><summary>Почему сделан такой вывод</summary>` +
    excerpts.map((item) => `<p class="m8-evidence-caption">Ваш ответ в оценочной ситуации</p><blockquote>${escapeHtml(item.text)}</blockquote>`).join('') +
    limitations.map((value) => `<p class="m8-local-limitation">${escapeHtml(value)}</p>`).join('') +
    `</details>`;
};

const renderM8Skills = (c67, competencyId) => {
  const skillsNode = document.getElementById('m8-report-skills');
  const claims = Array.isArray(c67.descriptive?.claims) ? c67.descriptive.claims : [];
  const isOverview = competencyId === 'all';
  const competencyOrder = new Map((c67.competencies || []).map((item, index) => [String(item.competency_id), index]));
  const selected = isOverview
    ? [...(c67.skills || [])].sort((left, right) =>
      (competencyOrder.get(String(left.competency_id)) ?? Number.MAX_SAFE_INTEGER)
      - (competencyOrder.get(String(right.competency_id)) ?? Number.MAX_SAFE_INTEGER))
    : (c67.skills || []).filter((skill) => String(skill.competency_id) === String(competencyId));
  if (!selected.some((skill) => String(skill.skill_id) === String(m8SelectedSkillId))) {
    m8SelectedSkillId = selected[0]?.skill_id || null;
  }
  let lastCompetencyId = null;
  const rows = selected.map((skill) => {
    const groupHeading = isOverview && String(skill.competency_id) !== String(lastCompetencyId)
      ? `<h4 class="m8-competency-heading">${escapeHtml(skill.competency_name || 'Группа навыков')}</h4>`
      : '';
    lastCompetencyId = skill.competency_id;
    const selectedNow = String(skill.skill_id) === String(m8SelectedSkillId);
    return `${groupHeading}<button class="m8-skill-row${selectedNow ? ' is-selected' : ''}" type="button" id="m8-skill-${escapeHtml(String(skill.skill_id))}" data-skill-id="${escapeHtml(String(skill.skill_id))}" aria-expanded="${selectedNow}" aria-controls="m8-skill-detail"><span><strong>${escapeHtml(skill.skill_name || 'Навык без названия')}</strong><small>${escapeHtml(skill.presentation?.label || outcomeLabels[skill.outcome] || 'Результат требует проверки')}</small>${(skill.presentation?.reasons || []).map((reason) => `<small>${escapeHtml(reason.message || 'Причина ограничения требует уточнения.')}</small>`).join('')}</span><span class="m8-skill-row-value">${escapeHtml(formatExactScore(skill.score))}</span></button>`;
  }).join('');
  const skill = selected.find((item) => String(item.skill_id) === String(m8SelectedSkillId));
  const related = skill ? claims.filter((item) => (item.skill_ids || []).map(String).includes(String(skill.skill_id))) : [];
  const narrative = buildSkillNarrative(related);
  const basisMarkup = skill && (buildSkillDetails(skill, related)
    || (c67.descriptive?.status === 'failed' ? '<p>Пояснение временно недоступно. Сохранённый показатель и ограничения показаны выше.</p>' : ''));
  const exact = skill?.score?.value == null ? '' : `<details><summary>Как получен результат</summary><p>Точное значение: ${escapeHtml(String(skill.score.value))}; числитель: ${escapeHtml(String(skill.score.numerator))}; знаменатель: ${escapeHtml(String(skill.score.denominator))}.</p></details>`;
  const reasons = (skill?.presentation?.reasons || []).map((reason) => `<p class="m8-local-limitation">${escapeHtml(reason.message || 'Причина ограничения требует уточнения.')}</p>`).join('');
  const panel = skill ? `<aside id="m8-skill-detail" class="m8-skill-detail" aria-label="Подробности навыка" tabindex="-1"><button type="button" class="m8-skill-back">← К списку навыков</button><p class="section-label">${escapeHtml(skill.competency_name || 'Навык')}</p><h4>${escapeHtml(skill.skill_name || 'Навык без названия')}</h4>${skill.skill_description ? `<p>${escapeHtml(skill.skill_description)}</p>` : ''}${narrative}<div class="m8-skill-result"><strong>${escapeHtml(formatExactScore(skill.score))}</strong><p>${escapeHtml(skill.presentation?.label || outcomeLabels[skill.outcome] || 'Результат требует проверки')}</p></div>${reasons}${basisMarkup}${exact}</aside>` : '<p>В этой группе нет навыков, включённых в сохранённый результат.</p>';
  skillsNode.innerHTML = `<div class="m8-skill-list">${rows}</div>`;
  const detailNode = document.getElementById('m8-report-detail');
  if (detailNode) {
    detailNode.innerHTML = panel;
    detailNode.querySelector('.m8-skill-back')?.addEventListener('click', () => {
      document.getElementById(`m8-skill-${m8SelectedSkillId}`)?.focus();
    });
  }
  skillsNode.querySelectorAll('[data-skill-id]').forEach((button) => button.addEventListener('click', () => {
    m8SelectedSkillId = button.dataset.skillId;
    renderM8Skills(c67, competencyId);
    renderM8Chart(c67, competencyId);
    document.getElementById('m8-skill-detail')?.focus({ preventScroll: true });
  }));
};

const setupM8CompetencyNavigation = (c67) => {
  const savedGroups = Array.isArray(c67.competencies) && c67.competencies.length
    ? c67.competencies
    : [...new Map((c67.skills || []).map((skill) => [skill.competency_id, { competency_id: skill.competency_id, competency_name: skill.competency_name }])).values()];
  const groups = [{ competency_id: 'all', competency_name: 'Общий обзор' }, ...savedGroups];
  const tabs = document.getElementById('m8-report-tabs');
  const select = document.getElementById('m8-report-tab-select');
  const selectGroup = (id) => {
    tabs.querySelectorAll('button').forEach((button) => {
      const active = button.dataset.competencyId === String(id);
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', String(active));
    });
    select.value = String(id);
    m8SelectedCompetencyId = id;
    renderM8Chart(c67, id);
    renderM8Skills(c67, id);
  };
  tabs.innerHTML = groups.map((group, index) => `<button class="report-tab-button${index === 0 ? ' active' : ''}" type="button" role="tab" aria-selected="${index === 0}" data-competency-id="${escapeHtml(group.competency_id)}">${escapeHtml(group.competency_name || 'Группа навыков')}</button>`).join('');
  select.innerHTML = groups.map((group) => `<option value="${escapeHtml(group.competency_id)}">${escapeHtml(group.competency_name || 'Группа навыков')}</option>`).join('');
  tabs.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => selectGroup(button.dataset.competencyId)));
  select.onchange = () => selectGroup(select.value);
  if (groups[0]) selectGroup(groups[0].competency_id);
  const modes = document.getElementById('m8-report-chart-modes');
  modes?.querySelectorAll('[data-chart-mode]').forEach((button) => {
    const initialMode = m8ChartRenderContext?.mobileOverview ? 'bars' : m8ChartMode;
    button.setAttribute('aria-pressed', String(button.dataset.chartMode === initialMode));
    button.onclick = () => {
      m8ChartMode = button.dataset.chartMode;
      modes.querySelectorAll('[data-chart-mode]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
      renderM8Chart(c67, m8SelectedCompetencyId);
    };
  });
};

const loadM8Report = async (cycleId, reportId, isCurrent, ownerId, customerAccess = false) => {
  const stateNode = document.getElementById('m8-report-state');
  if (!reportId) {
  const status = await withReportDeadline(async (signal) => readApiResponse(
    await fetch(`/users/assessment/m8/cycles/${encodeURIComponent(cycleId)}/status`, { signal }),
    'Не удалось загрузить состояние отчёта.'));
  if (!isCurrent()) return;
  if (status.results_status !== 'ready') {
    stateNode.textContent = status.results_status === 'failed' ? 'Не удалось подготовить отчёт. Ответы сохранены.' : 'Оценка завершена. Готовим ваш отчёт';
    document.getElementById('m8-report-skills').replaceChildren();
    return;
  }
  if (status.report_status !== 'ready') {
    stateNode.textContent = status.report_status === 'failed'
      ? 'Не удалось подготовить отчёт. Ответы сохранены.' : 'Оценка завершена. Готовим ваш отчёт';
    document.getElementById('m8-report-skills').replaceChildren();
    return;
  }
  }
  const report = await withReportDeadline(async (signal) => readApiResponse(await fetch(customerAccess
    ? `/users/admin/m8-access/reports/${encodeURIComponent(reportId)}`
    : reportId ? `/users/assessment/m8/reports/${encodeURIComponent(reportId)}` : `/users/assessment/m8/cycles/${encodeURIComponent(cycleId)}/reports/latest`, { signal }),
  'Не удалось загрузить отчёт.'));
  if (!isCurrent()) return;
  if (
    (!customerAccess && Number(report.owner_user_id) !== Number(ownerId))
    || String(report.cycle_id) !== String(cycleId)
    || (reportId && String(report.id) !== String(reportId))
  ) throw new Error('Сессия или выбранный отчёт изменились.');
  const c67 = report.c67;
  renderM8Correction(report.correction);
  {
    const checkFreshness = async () => {
      if (!isCurrent() || document.visibilityState === 'hidden') return;
      try {
        const response = await fetch(customerAccess
          ? `/users/admin/m8-access/cycles/${encodeURIComponent(cycleId)}/reports/latest`
          : `/users/assessment/m8/cycles/${encodeURIComponent(cycleId)}/reports/latest`);
        const latest = await readApiResponse(response, 'Не удалось проверить актуальность отчёта.');
        if (!isCurrent() || String(latest.id) === String(report.id)) return;
        const update = document.getElementById('m8-report-update');
        update.innerHTML = '<h3>Отчёт обновлён</h3><p>Откройте актуальный отчёт, чтобы увидеть исправление.</p><button class="ghost-button compact-ghost" type="button">Открыть актуальный отчёт</button>';
        update.classList.remove('hidden');
        update.querySelector('button')?.addEventListener('click', () => openReport({
          m8CycleId: cycleId, m8ReportId: latest.id, returnTarget: state.reportReturnTarget, customerAccess,
        }), { once: true });
      } catch { /* The saved view remains stable when freshness is unavailable. */ }
    };
    document.addEventListener('visibilitychange', checkFreshness, { signal: m8FreshnessController.signal });
    window.addEventListener('focus', checkFreshness, { signal: m8FreshnessController.signal });
    void checkFreshness();
  }
  stateNode.textContent = 'Результат готов';
  const metadata = document.getElementById('m8-report-metadata');
  const finishedAt = report.collection_closed_at || c67.collection?.closed_at;
  metadata.innerHTML = `<div><dt>Программа</dt><dd>${escapeHtml(report.program_name || 'Программа оценки не указана')}</dd></div>` +
    `<div><dt>Дата завершения</dt><dd>${escapeHtml(formatParticipantDate(finishedAt))}</dd></div>` +
    (customerAccess ? `<div><dt>Участник</dt><dd>${escapeHtml(report.participant_name || 'Имя не указано')}</dd></div>` : '');
  const descriptive = c67.descriptive || {};
  const summary = document.getElementById('m8-report-summary');
  if (descriptive.status === 'ready' && descriptive.summary?.length) {
    summary.innerHTML = descriptive.summary.map((item) => `<p>${escapeHtml(item)}</p>`).join('');
  } else if (descriptive.status === 'failed') {
    summary.innerHTML = '<p>Пояснение временно недоступно</p><p>Фактический результат и ограничения доступны ниже.</p>';
  } else if (descriptive.status === 'historical') {
    summary.innerHTML = '<p>Для этой исторической версии показаны только сохранённые фактические данные.</p>';
  } else {
    summary.innerHTML = '<p>Пояснение готовится</p><p>Фактический результат уже доступен ниже.</p>';
  }
  const partial = c67.partial_result;
  const partialNode = document.getElementById('m8-report-partial');
  if (partial && (partial.is_incomplete || (partial.limitation_reasons || []).length)) {
    const progress = partial.progress || {};
    partialNode.classList.toggle('is-complete-scope', partial.plan_completed === true);
    partialNode.innerHTML = `<strong>${escapeHtml(partial.messages?.title || (partial.is_incomplete ? 'Оценка завершена не полностью' : 'Оценка завершена'))}</strong><p>Подтверждено ${escapeHtml(String(progress.completed ?? '—'))} из ${escapeHtml(String(progress.planned ?? '—'))} запланированных ситуаций. Показаны только подтверждённые результаты; непокрытые элементы не считаются неуспехом.</p>` +
      (partial.limitation_reasons || []).map((item) => `<p>${escapeHtml(item.message || 'Причина ограничения требует уточнения.')}</p>`).join('');
    partialNode.classList.remove('hidden');
  } else {
    partialNode.classList.remove('is-complete-scope');
    partialNode.classList.add('hidden');
  }
  setupM8CompetencyNavigation(c67);
  const coverage = document.getElementById('m8-report-coverage');
  const context = c67.coverage_context || {};
  const scopeSummary = context.contract_version
    ? `<p><strong>Возможность каталога в выбранном составе:</strong> ${escapeHtml(coverageContextLabel(context.catalog_possibility))}. ` +
      `<strong>Задания этой оценки:</strong> ${escapeHtml(coverageContextLabel(context.cycle_plan))}.</p>` +
      `<p>Эти значения не являются баллом и не гарантируют, что навык удалось наблюдать или что наблюдение по ответу можно было учесть в результате.</p>`
    : '';
  coverage.innerHTML = `<details><summary>Как получен результат</summary>${scopeSummary}` + Object.entries(c67.coverage || {}).map(([scope, cuts]) => `<section><h4>${escapeHtml(scope === 'full_m2' ? 'Навыки, предусмотренные методикой' : 'Задания этой оценки')}</h4>` +
    Object.entries(cuts).map(([name, cut]) => `<p><strong>${escapeHtml(coverageLabels[name] || 'Неизвестный разрез покрытия')}</strong>: ${escapeHtml(coverageLabel(cut))}</p>`).join('') + '</section>').join('') +
    `<p><strong>Проверка расчёта:</strong> ${c67.reliability?.status === 'verified' ? 'подтверждена в указанной области' : c67.reliability?.status === 'not_verified' ? 'ещё не подтверждена' : 'сведения о проверке отсутствуют'}.</p></details>`;
  document.getElementById('m8-report-limitations').innerHTML = (c67.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
  const explanations = document.getElementById('m8-report-recommendations');
  explanations.replaceChildren();
  document.getElementById('m8-report-recommendation-notices').replaceChildren();
  const download = document.getElementById('report-download-button');
  download.dataset.m8ReportId = report.id;
  download.dataset.m8ReportAccess = customerAccess ? 'customer' : 'owner';
  download.disabled = false;
  if (!customerAccess) void setupM8ComparisonOptions(cycleId, report.id, isCurrent);
};

export const resolveAssessmentSessionIdByCode = async () => {
  const ownerId = state.pendingUser?.id; const epoch = state.identityEpoch;
  if (!state.pendingUser?.id || !state.assessmentSessionCode) {
    return null;
  }

  const response = await fetch(
    '/users/' + state.pendingUser.id + '/assessment/by-code/' + encodeURIComponent(state.assessmentSessionCode),
  );
  const data = await readApiResponse(response, 'Не удалось восстановить assessment-сессию.');
  if (state.identityEpoch !== epoch || state.pendingUser?.id !== ownerId) return null;
  const resolvedSessionId = Number(data?.session_id);
  if (!resolvedSessionId) {
    return null;
  }

  state.assessmentSessionId = resolvedSessionId;
  if (data?.session_code) {
    state.assessmentSessionCode = data.session_code;
  }
  persistAssessmentContext();
  return resolvedSessionId;
};

export const handleReportBack = () => {
  if (state.reportReturnTarget === 'admin-reports') {
    void import('./admin/reports.js').then((module) => module.openAdminReports());
    return;
  }
  if (state.reportReturnTarget === 'reports') {
    void openReports();
    return;
  }

  void openHomePage();
};

export const loadSkillAssessments = async () => {
  const ownerId = state.pendingUser?.id; const epoch = state.identityEpoch;
  const isCurrent = () => state.identityEpoch === epoch && state.pendingUser?.id === ownerId;
  if (!state.pendingUser?.id) {
    state.reportInterpretation = null;
    return;
  }

  if (!state.assessmentSessionId && state.assessmentSessionCode) {
    await resolveAssessmentSessionIdByCode();
    if (!isCurrent()) return;
  }

  if (!state.assessmentSessionId) {
    state.reportInterpretation = null;
    return;
  }

  const profileSummaryPromise = fetch('/users/' + state.pendingUser.id + '/profile-summary')
    .then((response) => readApiResponse(response, 'Не удалось загрузить данные ассессмента.'))
    .catch((error) => {
      console.warn('Failed to load report metadata', error);
      return null;
    });

  let [skillsResponse, interpretationResponse, profileSummary] = await Promise.all([
    fetch('/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/skill-assessments'),
    fetch('/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/report-interpretation'),
    profileSummaryPromise,
  ]);
  if (!isCurrent()) return;
  if (profileSummary) {
    state.profileSummary = profileSummary;
  }

  if ((skillsResponse.status === 404 || interpretationResponse.status === 404) && state.assessmentSessionCode) {
    const previousSessionId = state.assessmentSessionId;
    const resolvedSessionId = await resolveAssessmentSessionIdByCode();
    if (!isCurrent()) return;
    if (resolvedSessionId && resolvedSessionId !== previousSessionId) {
      [skillsResponse, interpretationResponse, profileSummary] = await Promise.all([
        fetch('/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/skill-assessments'),
        fetch('/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/report-interpretation'),
        profileSummaryPromise,
      ]);
      if (!isCurrent()) return;
      if (profileSummary) {
        state.profileSummary = profileSummary;
      }
    }
  }

  const data = await readApiResponse(skillsResponse, 'Не удалось загрузить профиль компетенций.');
  const interpretation = await readApiResponse(
    interpretationResponse,
    'Не удалось загрузить интерпретацию результатов.',
  );
  if (!isCurrent()) return;
  state.skillAssessments = data;
  state.reportInterpretation = interpretation;
  persistAssessmentContext();
};

export const tryOpenReportAfterProcessing = () => {
  if (state.processingAnimationDone && state.processingDataLoaded && !state.processingAutoTransitionStarted) {
    state.processingAutoTransitionStarted = true;
    window.setTimeout(() => {
      navigateToScreen('report');
    }, 280);
  }
};

export const initReport = () => {
  reportCompetencyCompactQuery?.addEventListener('change', () => {
    if (!reportPanel?.classList.contains('hidden') && state.skillAssessments.length) {
      renderReport();
    }
  });
};
