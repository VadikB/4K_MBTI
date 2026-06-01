import { state, persistAssessmentContext, clearAssessmentStorage, setCurrentScreen } from '../state.js';
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
} from '../utils/format.js';
import { getLevelPercent } from '../utils/competency.js';
import { readApiResponse } from '../api.js';
import { hideAllPanels, syncUrlState, navigateToScreen } from '../router.js';
import { formatAdminChartLabel } from './admin/charts.js';
import { openHomePage } from './ai-welcome.js';
import { openReports } from './reports.js';

const reportMbtiCard = document.getElementById('report-mbti-card');
const reportMbtiTitle = document.getElementById('report-mbti-title');
const reportMbtiScore = document.getElementById('report-mbti-score');
const reportMbtiSignals = document.getElementById('report-mbti-signals');
const reportMbtiSummary = document.getElementById('report-mbti-summary');
const reportMbtiMissingBlock = document.getElementById('report-mbti-missing-block');
const reportMbtiMissing = document.getElementById('report-mbti-missing');

let reportCompetencyBarChart = null;
let reportInfoModalCloseTimer = null;

const getMbtiOverallBlock = () => {
  const payload = state.assessmentMbtiSummary;
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  return payload['общий_итог'] || payload.overall_result || payload.overall || null;
};

const getMbtiSummaryText = () => {
  const overallBlock = getMbtiOverallBlock();
  if (!overallBlock || typeof overallBlock !== 'object') {
    return '';
  }
  const signals = Array.isArray(overallBlock['вероятные_сигналы_темперамента'])
    ? overallBlock['вероятные_сигналы_темперамента'].map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  const score = overallBlock['оценка'] ?? overallBlock.score ?? null;
  const conclusion = String(
    overallBlock['краткий_вывод'] || overallBlock.summary || overallBlock.conclusion || '',
  ).trim();

  const parts = [];
  if (signals.length) {
    parts.push('MBTI-профиль: ' + signals.join(', ') + '.');
  }
  if (score !== null && score !== undefined && score !== '') {
    parts.push('Уверенность: ' + score + '/100.');
  }
  if (conclusion) {
    parts.push(conclusion);
  }
  return parts.join(' ');
};

const getMbtiSignals = () => {
  const overallBlock = getMbtiOverallBlock();
  if (!overallBlock || typeof overallBlock !== 'object') {
    return [];
  }
  return Array.isArray(overallBlock['вероятные_сигналы_темперамента'])
    ? overallBlock['вероятные_сигналы_темперамента'].map((item) => String(item || '').trim()).filter(Boolean)
    : [];
};

const getMbtiMissingInfo = () => {
  const overallBlock = getMbtiOverallBlock();
  if (!overallBlock || typeof overallBlock !== 'object') {
    return [];
  }
  return Array.isArray(overallBlock['недостающая_информация'])
    ? overallBlock['недостающая_информация'].map((item) => String(item || '').trim()).filter(Boolean)
    : [];
};

const renderReportMbti = () => {
  if (!reportMbtiCard || !reportMbtiTitle || !reportMbtiSignals || !reportMbtiSummary) {
    return;
  }

  const overallBlock = getMbtiOverallBlock();
  if (!overallBlock || typeof overallBlock !== 'object') {
    reportMbtiCard.classList.add('hidden');
    return;
  }

  const signals = getMbtiSignals();
  const score = overallBlock['оценка'] ?? overallBlock.score ?? null;
  const conclusion = String(
    overallBlock['краткий_вывод'] || overallBlock.summary || overallBlock.conclusion || '',
  ).trim();
  const missingInfo = getMbtiMissingInfo();

  reportMbtiCard.classList.remove('hidden');
  reportMbtiTitle.textContent = signals.length ? signals.join(' · ') : 'Профиль по ответам на кейсы';

  reportMbtiSignals.innerHTML = '';
  signals.forEach((signal) => {
    const badge = document.createElement('span');
    badge.className = 'report-mbti-signal';
    badge.textContent = signal;
    reportMbtiSignals.appendChild(badge);
  });

  reportMbtiSummary.textContent = conclusion || getMbtiSummaryText() || 'MBTI-вывод пока не сформирован.';

  if (reportMbtiScore) {
    if (score !== null && score !== undefined && score !== '') {
      reportMbtiScore.classList.remove('hidden');
      const strong = reportMbtiScore.querySelector('strong');
      if (strong) {
        strong.textContent = String(score) + '/100';
      }
    } else {
      reportMbtiScore.classList.add('hidden');
    }
  }

  if (reportMbtiMissingBlock && reportMbtiMissing) {
    reportMbtiMissing.innerHTML = '';
    if (missingInfo.length) {
      reportMbtiMissingBlock.classList.remove('hidden');
      missingInfo.forEach((item) => {
        const li = document.createElement('li');
        li.textContent = item;
        reportMbtiMissing.appendChild(li);
      });
    } else {
      reportMbtiMissingBlock.classList.add('hidden');
    }
  }
};

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
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
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
  const start = new Date(startedAt);
  const finish = new Date(finishedAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(finish.getTime()) || finish < start) {
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
    [summary.finished_at ? 'Завершена' : 'Начата', formatReportDateTime(summary.finished_at || summary.started_at)],
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
      cardGradient.addColorStop(0, '#f1efff');
      cardGradient.addColorStop(1, '#dfdcfb');

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
        fillGradient.addColorStop(0, '#5d4be8');
        fillGradient.addColorStop(0.54, '#6757f0');
        fillGradient.addColorStop(1, '#8d84ff');
        context.fillStyle = fillGradient;
        drawCanvasRoundedRect(context, centerX - fillWidth / 2, fillTop, fillWidth, fillHeight, fillWidth / 2);
        context.fill();
      }

      context.fillStyle = '#6d61f3';
      context.font = '800 26px Inter, sans-serif';
      context.fillText(value + '%', centerX, valueY);

      context.fillStyle = '#2b2d42';
      context.font = '800 11px Inter, sans-serif';
      drawWrappedCanvasText(context, item.competency || 'Компетенция', centerX, labelY, cardWidth - 18, 14);
    });
    context.restore();
  },
};

const getReportCompetencyGradient = () => 'rgba(93, 75, 232, 0)';

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
          borderColor: 'rgba(70, 72, 212, 0.32)',
          hoverBorderColor: 'rgba(70, 72, 212, 0.32)',
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
          backgroundColor: '#191c1e',
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

  const mbtiSummaryText = getMbtiSummaryText();

  reportOverallScore.textContent = totalScore + '%';
  reportSummaryText.textContent = mbtiSummaryText
    ? 'Глубокий анализ оценок по четырем направлениям и детализация результатов по каждому навыку пользователя. Ниже доступен отдельный MBTI-разбор по ответам на кейсы.'
    : 'Глубокий анализ оценок по четырем направлениям и детализация результатов по каждому навыку пользователя.';
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
  renderReportMbti();

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

export const openReport = (options = {}) => {
  const { returnTarget = 'home' } = options;
  state.reportReturnTarget = returnTarget === 'reports' ? 'reports' : 'home';
  setCurrentScreen('report');
  syncUrlState('report');
  hideAllPanels();
  reportPanel.classList.remove('hidden');
  renderReport();
  clearAssessmentStorage();
};

export const resolveAssessmentSessionIdByCode = async () => {
  if (!state.pendingUser?.id || !state.assessmentSessionCode) {
    return null;
  }

  const response = await fetch(
    '/users/' + state.pendingUser.id + '/assessment/by-code/' + encodeURIComponent(state.assessmentSessionCode),
  );
  const data = await readApiResponse(response, 'Не удалось восстановить assessment-сессию.');
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
  if (state.reportReturnTarget === 'reports') {
    void openReports();
    return;
  }

  void openHomePage();
};

export const loadSkillAssessments = async () => {
  if (!state.pendingUser?.id) {
    state.reportInterpretation = null;
    return;
  }

  if (!state.assessmentSessionId && state.assessmentSessionCode) {
    await resolveAssessmentSessionIdByCode();
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
  if (profileSummary) {
    state.profileSummary = profileSummary;
  }

  if ((skillsResponse.status === 404 || interpretationResponse.status === 404) && state.assessmentSessionCode) {
    const previousSessionId = state.assessmentSessionId;
    const resolvedSessionId = await resolveAssessmentSessionIdByCode();
    if (resolvedSessionId && resolvedSessionId !== previousSessionId) {
      [skillsResponse, interpretationResponse, profileSummary] = await Promise.all([
        fetch('/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/skill-assessments'),
        fetch('/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/report-interpretation'),
        profileSummaryPromise,
      ]);
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
  state.skillAssessments = data;
  state.reportInterpretation = interpretation;
  state.assessmentMbtiSummary =
    interpretation && typeof interpretation.mbti_summary === 'object' ? interpretation.mbti_summary : null;
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
