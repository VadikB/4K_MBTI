import { state } from '../../state.js';
import {
  adminReportDetailSkillsRadarChart,
  adminReportDetailSkillsRadarLabels,
  adminReportDetailSkillsRadarFallback,
} from '../../dom.js';
import { levelThresholds } from '../../config.js';
import { escapeHtml } from '../../utils/format.js';
import { getCompetencyPalette, getCompetencySortIndex, getLevelPercent } from '../../utils/competency.js';

let adminSkillRadarChart = null;

const getRadarScale = (chart) => chart?.scales?.r || null;

const getRadarPoint = (scale, index, distance) => {
  if (typeof scale.getPointPosition === 'function') {
    return scale.getPointPosition(index, distance);
  }
  const labelCount = scale?._pointLabels?.length || 1;
  const angle = -Math.PI / 2 + ((Math.PI * 2) / labelCount) * index;
  return {
    x: scale.xCenter + Math.cos(angle) * distance,
    y: scale.yCenter + Math.sin(angle) * distance,
  };
};

const getRadarAxisAngle = (scale, index, radius) => {
  const point = getRadarPoint(scale, index, radius);
  return Math.atan2(point.y - scale.yCenter, point.x - scale.xCenter);
};

const buildRadarCompetencyGroups = (items, getCompetencyName) => {
  const groups = [];
  items.forEach((item, index) => {
    const competency = getCompetencyName(item) || 'Без категории';
    const previousGroup = groups[groups.length - 1];
    if (previousGroup && previousGroup.competency === competency) {
      previousGroup.end = index;
      return;
    }
    groups.push({ competency, start: index, end: index });
  });
  return groups;
};

const sortSkillsForRadar = (skills = []) =>
  [...skills].sort((first, second) => {
    const firstCompetency = first?.competency_name || '';
    const secondCompetency = second?.competency_name || '';
    const competencyDelta = getCompetencySortIndex(firstCompetency) - getCompetencySortIndex(secondCompetency);
    if (competencyDelta !== 0) {
      return competencyDelta;
    }
    return String(first?.skill_name || '').localeCompare(String(second?.skill_name || ''), 'ru');
  });

const drawRadarCompetencyRegionBackgrounds = (chart, options = {}) => {
  const scale = getRadarScale(chart);
  const groups = Array.isArray(options.groups) ? options.groups : [];
  const labelCount = chart?.data?.labels?.length || 0;
  if (!scale || labelCount < 2 || !groups.length) {
    return;
  }

  const radius = scale.drawingArea;
  const step = (Math.PI * 2) / labelCount;
  const context = chart.ctx;
  context.save();
  context.globalCompositeOperation = 'destination-over';

  groups.forEach((group) => {
    const start = Math.max(0, Math.min(labelCount - 1, group.start));
    const end = Math.max(start, Math.min(labelCount - 1, group.end));
    const palette = getCompetencyPalette(group.competency);
    let startAngle = getRadarAxisAngle(scale, start, radius) - step / 2;
    let endAngle = getRadarAxisAngle(scale, end, radius) + step / 2;
    if (endAngle <= startAngle) {
      endAngle += Math.PI * 2;
    }

    context.beginPath();
    context.moveTo(scale.xCenter, scale.yCenter);
    const segments = Math.max(4, Math.ceil((endAngle - startAngle) / (Math.PI / 18)));
    for (let index = 0; index <= segments; index += 1) {
      const angle = startAngle + ((endAngle - startAngle) * index) / segments;
      context.lineTo(scale.xCenter + Math.cos(angle) * radius, scale.yCenter + Math.sin(angle) * radius);
    }
    context.closePath();
    context.fillStyle = palette.fill;
    context.fill();
  });

  context.restore();
};

const radarCompetencyRegionsPlugin = {
  id: 'radarCompetencyRegions',
  beforeDatasetsDraw(chart, _args, options) {
    drawRadarCompetencyRegionBackgrounds(chart, options);
  },
};

const radarThresholdRingsPlugin = {
  id: 'radarThresholdRings',
  beforeDatasetsDraw(chart, _args, options = {}) {
    const scale = getRadarScale(chart);
    const thresholds = Array.isArray(options.thresholds) ? options.thresholds : [];
    const labelCount = chart?.data?.labels?.length || 0;
    if (!scale || labelCount < 3 || !thresholds.length) {
      return;
    }

    const context = chart.ctx;
    context.save();
    context.lineWidth = 1.4;
    context.setLineDash([5, 5]);
    thresholds.forEach((threshold) => {
      const value = Number(threshold.value) || 0;
      if (value <= 0) {
        return;
      }
      const distance = scale.getDistanceFromCenterForValue(value);
      context.beginPath();
      for (let index = 0; index < labelCount; index += 1) {
        const point = getRadarPoint(scale, index, distance);
        if (index === 0) {
          context.moveTo(point.x, point.y);
        } else {
          context.lineTo(point.x, point.y);
        }
      }
      context.closePath();
      context.strokeStyle = threshold.code === 'L3' ? 'rgba(15, 23, 42, 0.38)' : 'rgba(15, 23, 42, 0.25)';
      context.stroke();

      const labelAngle = -Math.PI / 4;
      const labelX = scale.xCenter + Math.cos(labelAngle) * distance + 6;
      const labelY = scale.yCenter + Math.sin(labelAngle) * distance;
      context.setLineDash([]);
      context.font = '800 11px Inter, Segoe UI, Arial, sans-serif';
      context.textAlign = 'left';
      context.textBaseline = 'middle';
      const text = threshold.code;
      const width = context.measureText(text).width + 10;
      context.fillStyle = 'rgba(255, 255, 255, 0.86)';
      context.fillRect(labelX - 4, labelY - 9, width, 18);
      context.fillStyle = '#334155';
      context.fillText(text, labelX + 1, labelY);
      context.setLineDash([5, 5]);
    });
    context.restore();
  },
};

const isSkillNotDetected = (skill) => getLevelPercent(skill?.assessed_level_code) <= 0;

const getRadarPointLabelBounds = (scale, index) => {
  const item = scale?._pointLabelItems?.[index];
  if (!item) {
    return null;
  }
  const left = Number.isFinite(item.left) ? item.left : item.x - 36;
  const right = Number.isFinite(item.right) ? item.right : item.x + 36;
  const top = Number.isFinite(item.top) ? item.top : item.y - 10;
  const bottom = Number.isFinite(item.bottom) ? item.bottom : item.y + 10;
  return { left, right, top, bottom };
};

const hideAdminSkillRadarLabelTooltip = (chart) => {
  if (chart?.$notDetectedLabelTooltip) {
    chart.$notDetectedLabelTooltip.classList.add('hidden');
  }
  if (chart?.canvas) {
    chart.canvas.style.cursor = '';
  }
  if (chart) {
    chart.$notDetectedLabelIndex = undefined;
  }
};

const getAdminSkillRadarLabelTooltip = (chart) => {
  if (chart.$notDetectedLabelTooltip) {
    return chart.$notDetectedLabelTooltip;
  }
  const parent = chart.canvas?.parentElement;
  if (!parent) {
    return null;
  }
  const tooltip = document.createElement('div');
  tooltip.className = 'admin-skill-radar-label-tooltip hidden';
  tooltip.setAttribute('role', 'tooltip');
  parent.appendChild(tooltip);
  chart.$notDetectedLabelTooltip = tooltip;
  return tooltip;
};

const adminSkillRadarNotDetectedLabelsPlugin = {
  id: 'adminSkillRadarNotDetectedLabels',
  afterDraw(chart, _args, options = {}) {
    const skills = Array.isArray(options.skills) ? options.skills : [];
    if (!skills.length) {
      return;
    }

    const scale = getRadarScale(chart);
    if (!scale?._pointLabelItems?.length) {
      return;
    }

    const context = chart.ctx;
    context.save();
    context.strokeStyle = 'rgba(100, 116, 139, 0.72)';
    context.lineWidth = 1;
    context.setLineDash([3, 3]);

    skills.forEach((skill, index) => {
      if (!isSkillNotDetected(skill)) {
        return;
      }
      const bounds = getRadarPointLabelBounds(scale, index);
      if (!bounds) {
        return;
      }
      const y = bounds.bottom + 3;
      context.beginPath();
      context.moveTo(bounds.left, y);
      context.lineTo(bounds.right, y);
      context.stroke();
    });

    context.restore();
  },
  afterEvent(chart, args, options = {}) {
    const skills = Array.isArray(options.skills) ? options.skills : [];
    const event = args.event;
    const scale = getRadarScale(chart);
    if (!skills.length || !event || !scale?._pointLabelItems?.length) {
      hideAdminSkillRadarLabelTooltip(chart);
      return;
    }

    const hoveredIndex = skills.findIndex((skill, index) => {
      if (!isSkillNotDetected(skill)) {
        return false;
      }
      const bounds = getRadarPointLabelBounds(scale, index);
      if (!bounds) {
        return false;
      }
      return (
        event.x >= bounds.left - 4 &&
        event.x <= bounds.right + 4 &&
        event.y >= bounds.top - 4 &&
        event.y <= bounds.bottom + 8
      );
    });

    if (hoveredIndex === -1) {
      hideAdminSkillRadarLabelTooltip(chart);
      return;
    }

    const bounds = getRadarPointLabelBounds(scale, hoveredIndex);
    const tooltip = getAdminSkillRadarLabelTooltip(chart);
    if (!bounds || !tooltip) {
      hideAdminSkillRadarLabelTooltip(chart);
      return;
    }

    const skill = skills[hoveredIndex];
    const tooltipWidth = 280;
    const canvasWidth = chart.width || chart.canvas?.clientWidth || 0;
    const centerX = (bounds.left + bounds.right) / 2;
    const left = Math.max(8 + tooltipWidth / 2, Math.min(canvasWidth - 8 - tooltipWidth / 2, centerX));
    const top = bounds.bottom + 12;

    chart.canvas.style.cursor = 'help';
    tooltip.innerHTML =
      '<strong>' +
      escapeHtml(skill?.skill_name || 'Навык') +
      '</strong>' +
      '<span>Компетенция не проявилась в ассессменте</span>' +
      '<em>' +
      escapeHtml(skill?.competency_name || '') +
      '</em>';
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.classList.remove('hidden');
    chart.$notDetectedLabelIndex = hoveredIndex;
  },
  beforeDestroy(chart) {
    chart.$notDetectedLabelTooltip?.remove();
    chart.$notDetectedLabelTooltip = null;
  },
};

export const destroyAdminSkillRadarChart = () => {
  if (adminSkillRadarChart) {
    adminSkillRadarChart.destroy();
    adminSkillRadarChart = null;
  }
};

const formatRadarLabel = (text) => {
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
    if ((currentLine + ' ' + word).length <= 16 || lines.length >= 2) {
      currentLine += ' ' + word;
      return;
    }
    lines.push(currentLine);
    currentLine = word;
  });

  if (currentLine) {
    lines.push(currentLine);
  }

  return lines.length > 1 ? lines : [rawText];
};

export const renderAdminProfileSummaryList = (node, items) => {
  if (!node) {
    return;
  }
  const values = Array.isArray(items) ? items.filter((item) => String(item || '').trim()) : [];
  if (!values.length) {
    node.innerHTML = '<li>Нет данных</li>';
    return;
  }
  node.innerHTML = values.map((item) => '<li>' + escapeHtml(String(item)) + '</li>').join('');
};

const buildAdminSkillRadarFallbackMarkup = (skills) =>
  '<div class="admin-detail-skill-radar-list">' +
  skills
    .map(
      (skill) =>
        '<div class="admin-detail-skill-radar-item">' +
        '<span>' +
        (skill.skill_name || 'Навык') +
        '</span>' +
        '<strong>' +
        getLevelPercent(skill.assessed_level_code) +
        '%</strong>' +
        '</div>',
    )
    .join('') +
  '</div>';

export const renderAdminSkillRadar = (skills = []) => {
  if (!adminReportDetailSkillsRadarChart || !adminReportDetailSkillsRadarFallback) {
    return;
  }

  destroyAdminSkillRadarChart();

  adminReportDetailSkillsRadarChart.classList.add('hidden');
  if (adminReportDetailSkillsRadarLabels) {
    adminReportDetailSkillsRadarLabels.classList.add('hidden');
  }
  adminReportDetailSkillsRadarFallback.classList.add('hidden');
  adminReportDetailSkillsRadarFallback.innerHTML = '';

  if (state.adminReportDetailSkillAssessmentsLoading) {
    adminReportDetailSkillsRadarFallback.textContent = 'Загружаем распределение по навыкам...';
    adminReportDetailSkillsRadarFallback.classList.remove('hidden');
    return;
  }

  if (!skills.length) {
    adminReportDetailSkillsRadarFallback.textContent = 'Для этой записи пока нет оценок по отдельным навыкам.';
    adminReportDetailSkillsRadarFallback.classList.remove('hidden');
    return;
  }

  const radarSkills = sortSkillsForRadar(skills);
  const skillCompetencyGroups = buildRadarCompetencyGroups(radarSkills, (skill) => skill.competency_name);

  if (typeof window.Chart !== 'function') {
    adminReportDetailSkillsRadarFallback.innerHTML = buildAdminSkillRadarFallbackMarkup(radarSkills);
    adminReportDetailSkillsRadarFallback.classList.remove('hidden');
    return;
  }

  const context = adminReportDetailSkillsRadarChart.getContext('2d');
  if (!context) {
    adminReportDetailSkillsRadarFallback.innerHTML = buildAdminSkillRadarFallbackMarkup(radarSkills);
    adminReportDetailSkillsRadarFallback.classList.remove('hidden');
    return;
  }

  adminReportDetailSkillsRadarChart.classList.remove('hidden');
  if (adminReportDetailSkillsRadarLabels) {
    adminReportDetailSkillsRadarLabels.classList.remove('hidden');
  }

  adminSkillRadarChart = new window.Chart(context, {
    type: 'radar',
    data: {
      labels: radarSkills.map((skill) => formatRadarLabel(skill.skill_name)),
      datasets: [
        {
          label: 'Оценка навыка',
          data: radarSkills.map((skill) => getLevelPercent(skill.assessed_level_code)),
          fill: true,
          borderColor: '#334155',
          backgroundColor: 'rgba(51, 65, 85, 0.12)',
          borderWidth: 2,
          pointRadius: radarSkills.map((skill) => (isSkillNotDetected(skill) ? 0 : 4)),
          pointHoverRadius: radarSkills.map((skill) => (isSkillNotDetected(skill) ? 0 : 5)),
          pointBackgroundColor: radarSkills.map((skill) => getCompetencyPalette(skill.competency_name).stroke),
          pointBorderColor: radarSkills.map((skill) => getCompetencyPalette(skill.competency_name).stroke),
          pointBorderWidth: 1,
        },
      ],
    },
    plugins: [radarCompetencyRegionsPlugin, radarThresholdRingsPlugin, adminSkillRadarNotDetectedLabelsPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {
        padding: {
          top: 14,
          right: 44,
          bottom: 16,
          left: 44,
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        radarCompetencyRegions: {
          groups: skillCompetencyGroups,
        },
        radarThresholdRings: {
          thresholds: levelThresholds,
        },
        adminSkillRadarNotDetectedLabels: {
          skills: radarSkills,
        },
        tooltip: {
          displayColors: false,
          backgroundColor: '#fff',
          borderColor: 'rgba(15, 23, 42, 0.12)',
          borderWidth: 1,
          titleColor: '#14151f',
          bodyColor: '#14151f',
          footerColor: '#64748b',
          caretPadding: 8,
          cornerRadius: 8,
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
            title(items) {
              const skill = radarSkills[items[0]?.dataIndex ?? 0];
              return skill?.skill_name || 'Навык';
            },
            label(context) {
              const skill = radarSkills[context.dataIndex];
              if (isSkillNotDetected(skill)) {
                return 'Компетенция не проявилась в ассессменте';
              }
              return (skill?.assessed_level_name || 'Нет уровня') + ' - ' + context.formattedValue + '%';
            },
            afterLabel(context) {
              const skill = radarSkills[context.dataIndex];
              return skill?.competency_name || '';
            },
          },
        },
      },
      scales: {
        r: {
          beginAtZero: true,
          min: 0,
          max: 100,
          ticks: {
            stepSize: 25,
            display: false,
          },
          grid: {
            color: 'rgba(100, 116, 139, 0.16)',
          },
          angleLines: {
            color: 'rgba(100, 116, 139, 0.16)',
          },
          pointLabels: {
            color(context) {
              const skill = radarSkills[context?.index ?? 0];
              if (isSkillNotDetected(skill)) {
                return '#94a3b8';
              }
              return getCompetencyPalette(skill?.competency_name).stroke;
            },
            font: {
              family: 'Inter',
              size: 14,
              weight: '700',
            },
            padding: 10,
          },
        },
      },
      elements: {
        line: {
          tension: 0,
        },
      },
    },
  });
};

export const getAdminStatusBadgeLabel = (status) => {
  const normalized = String(status || '')
    .trim()
    .toLowerCase();
  if (normalized === 'завершено') {
    return 'Завершено';
  }
  if (normalized === 'в процессе') {
    return 'В процессе';
  }
  return 'Черновик';
};
