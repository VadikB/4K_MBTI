import { state, persistAssessmentContext, setCurrentScreen } from '../../state.js';
import {
  adminReportDetailPanel,
  adminReportDetailBackButton,
  adminReportDetailPdfButton,
  adminReportDetailExpertPdfButton,
  adminReportDetailDialoguesPdfButton,
  adminReportDetailDate,
  adminReportDetailScore,
  adminReportDetailAvatar,
  adminReportDetailName,
  adminReportDetailRole,
  adminReportDetailGroup,
  adminReportDetailPhone,
  adminReportDetailTelegram,
  adminReportDetailStatusBadge,
  adminReportDetailProfilePosition,
  adminReportDetailProfileDuties,
  adminReportDetailProfileDomain,
  adminReportDetailProfileProcesses,
  adminReportDetailProfileTasks,
  adminReportDetailProfileStakeholders,
  adminReportDetailProfileConstraints,
  adminReportDetailSkillsRadarChart,
  adminReportDetailSkillsRadarLabels,
  adminReportDetailSkillsRadarFallback,
  adminReportDetailMbtiType,
  adminReportDetailMbtiSummary,
  adminReportDetailMbtiAxes,
  adminReportDetailInsightTitle,
  adminReportDetailInsightText,
  adminReportDetailBasis,
  adminReportDetailStrengths,
  adminReportDetailGrowth,
  adminReportDetailQuotes,
  adminReportDetailCases,
  adminReportDetailExpertName,
  adminReportDetailExpertContacts,
  adminReportDetailExpertAssessedAt,
  adminReportDetailExpertComment,
  adminReportDetailExpertCommentEdit,
  adminReportDetailExpertCommentCancel,
  adminReportDetailExpertCommentSave,
  adminReportDetailExpertCommentStatus,
} from '../../dom.js';
import {
  escapeHtml,
  sanitizeDisplayRole,
  sanitizeDisplayMetaText,
  buildInitials,
  formatAdminReportDate,
  formatDateInputValue,
  formatDateTimeLocalValue,
  normalizeExpertAssessmentDateForApi,
  highlightAdminInsightFigures,
  parseJsonArrayField,
} from '../../utils/format.js';
import { readApiResponse } from '../../api.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import { renderAdminSkillRadar, renderAdminProfileSummaryList, getAdminStatusBadgeLabel } from './skill-radar.js';
export const loadAdminReportDetail = async (sessionId) => {
  const response = await fetch('/users/admin/reports/' + sessionId, {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить отчет по оценке.');
  state.adminReportDetail = data;
  state.adminReportDetailSessionId = sessionId;
  state.adminReportDetailExpertCommentEditing = false;
  state.adminReportDetailExpertCommentOriginal = data?.expert_comment || '';
  state.adminReportDetailExpertCommentDirty = false;
  state.adminReportDetailExpertMetaOriginal = {
    expert_name: data?.expert_name || '',
    expert_contacts: data?.expert_contacts || '',
    expert_assessed_at: formatDateInputValue(data?.expert_assessed_at),
  };
  persistAssessmentContext();
};

export const loadAdminReportDetailSkillAssessments = async (userId, sessionId) => {
  const response = await fetch('/users/' + userId + '/assessment/' + sessionId + '/skill-assessments', {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить оценки по навыкам.');
  state.adminReportDetailSkillAssessments = Array.isArray(data) ? data : [];
};

export const renderAdminReportDetail = () => {
  const detail = state.adminReportDetail;
  if (!detail) {
    adminReportDetailName.textContent = 'Отчет недоступен';
    adminReportDetailRole.textContent = 'Нет данных';
    adminReportDetailGroup.textContent = 'Нет данных';
    if (adminReportDetailPhone) {
      adminReportDetailPhone.textContent = 'Телефон не указан';
    }
    if (adminReportDetailTelegram) {
      adminReportDetailTelegram.textContent = 'Telegram не указан';
    }
    adminReportDetailDate.textContent = 'Без даты';
    adminReportDetailScore.textContent = '0%';
    if (adminReportDetailStatusBadge) {
      adminReportDetailStatusBadge.textContent = 'Черновик';
    }
    if (adminReportDetailMbtiType) {
      adminReportDetailMbtiType.textContent = 'Нет данных';
    }
    if (adminReportDetailMbtiSummary) {
      adminReportDetailMbtiSummary.textContent = 'Данные по отчету пока недоступны.';
    }
    adminReportDetailInsightTitle.textContent = 'AI insight недоступен';
    adminReportDetailInsightText.textContent =
      'После загрузки результатов здесь появится интерпретация профиля пользователя.';
    if (adminReportDetailProfilePosition) {
      adminReportDetailProfilePosition.textContent = 'Нет данных';
    }
    if (adminReportDetailProfileDuties) {
      adminReportDetailProfileDuties.textContent = 'Нет данных';
    }
    if (adminReportDetailProfileDomain) {
      adminReportDetailProfileDomain.textContent = 'Нет данных';
    }
    renderAdminProfileSummaryList(adminReportDetailProfileProcesses, []);
    renderAdminProfileSummaryList(adminReportDetailProfileTasks, []);
    renderAdminProfileSummaryList(adminReportDetailProfileStakeholders, []);
    renderAdminProfileSummaryList(adminReportDetailProfileConstraints, []);
    renderAdminSkillRadar([]);
    if (adminReportDetailMbtiAxes) {
      adminReportDetailMbtiAxes.innerHTML = '';
    }
    adminReportDetailBasis.innerHTML = '';
    adminReportDetailStrengths.innerHTML = '<li>Данные будут доступны после появления результатов оценки.</li>';
    adminReportDetailGrowth.innerHTML = '<li>Зоны роста будут определены после накопления результатов.</li>';
    adminReportDetailQuotes.innerHTML = '';
    if (adminReportDetailCases) {
      adminReportDetailCases.innerHTML = '';
    }
    if (adminReportDetailExpertName) {
      adminReportDetailExpertName.value = '';
      adminReportDetailExpertName.disabled = true;
    }
    if (adminReportDetailExpertContacts) {
      adminReportDetailExpertContacts.value = '';
      adminReportDetailExpertContacts.disabled = true;
    }
    if (adminReportDetailExpertAssessedAt) {
      adminReportDetailExpertAssessedAt.value = '';
      adminReportDetailExpertAssessedAt.disabled = true;
    }
    if (adminReportDetailExpertComment) {
      adminReportDetailExpertComment.value = '';
      adminReportDetailExpertComment.disabled = true;
      adminReportDetailExpertComment.placeholder = 'Комментарий эксперта появится после завершения ассессмента.';
    }
    if (adminReportDetailExpertCommentEdit) {
      adminReportDetailExpertCommentEdit.hidden = true;
      adminReportDetailExpertCommentEdit.disabled = true;
    }
    if (adminReportDetailExpertCommentCancel) {
      adminReportDetailExpertCommentCancel.hidden = true;
      adminReportDetailExpertCommentCancel.disabled = true;
    }
    if (adminReportDetailExpertCommentSave) {
      adminReportDetailExpertCommentSave.hidden = false;
      adminReportDetailExpertCommentSave.disabled = true;
      adminReportDetailExpertCommentSave.textContent = 'Сохранить комментарий';
    }
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = '';
    }
    return;
  }

  const reportDate = detail.report_date
    ? new Date(detail.report_date).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
      })
    : 'Без даты';
  const scorePercent = typeof detail.score_percent === 'number' ? detail.score_percent : 0;
  const mbtiAxes =
    Array.isArray(detail.mbti_axes) && detail.mbti_axes.length
      ? detail.mbti_axes
      : [
          { left: 'Экстраверсия', right: 'Интроверсия', value: 0 },
          { left: 'Интуиция', right: 'Сенсорика', value: 0 },
          { left: 'Мышление', right: 'Чувство', value: 0 },
          { left: 'Суждение', right: 'Восприятие', value: 0 },
        ];

  adminReportDetailDate.textContent = reportDate;
  adminReportDetailScore.textContent = scorePercent + '%';
  adminReportDetailAvatar.textContent = buildInitials(detail.full_name || 'Пользователь');
  adminReportDetailName.textContent = detail.full_name || 'Пользователь';
  adminReportDetailRole.textContent = sanitizeDisplayRole(detail.role_name || '') || 'Роль не указана';
  adminReportDetailGroup.textContent = sanitizeDisplayMetaText(detail.group_name || '') || 'Группа не указана';
  if (adminReportDetailPhone) {
    adminReportDetailPhone.textContent = detail.phone ? 'Телефон: ' + detail.phone : 'Телефон не указан';
  }
  if (adminReportDetailTelegram) {
    adminReportDetailTelegram.textContent = detail.telegram ? 'Telegram: ' + detail.telegram : 'Telegram не указан';
  }
  if (adminReportDetailStatusBadge) {
    adminReportDetailStatusBadge.textContent = getAdminStatusBadgeLabel(detail.status);
  }
  if (adminReportDetailMbtiType) {
    adminReportDetailMbtiType.textContent = detail.mbti_type || 'Нет данных';
  }
  if (adminReportDetailMbtiSummary) {
    adminReportDetailMbtiSummary.textContent = detail.mbti_summary || 'Данные MBTI пока недоступны для этой записи.';
  }
  adminReportDetailInsightTitle.textContent = detail.insight_title || 'AI insight недоступен';
  adminReportDetailInsightText.innerHTML = highlightAdminInsightFigures(
    detail.insight_text || 'Для этой записи пока не удалось построить интерпретацию результатов.',
  );
  if (adminReportDetailExpertComment) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertComment.value = detail.expert_comment || '';
    adminReportDetailExpertComment.disabled = !isEditingExpertComment;
    adminReportDetailExpertComment.placeholder = canEditExpertComment
      ? 'Добавьте вывод эксперта по результатам прохождения ассессмента.'
      : 'Комментарий эксперта доступен после полного завершения ассессмента.';
  }
  if (adminReportDetailExpertName) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertName.value = detail.expert_name || '';
    adminReportDetailExpertName.disabled = !isEditingExpertComment;
  }
  if (adminReportDetailExpertContacts) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertContacts.value = detail.expert_contacts || '';
    adminReportDetailExpertContacts.disabled = !isEditingExpertComment;
  }
  if (adminReportDetailExpertAssessedAt) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertAssessedAt.value = formatDateInputValue(detail.expert_assessed_at);
    adminReportDetailExpertAssessedAt.disabled = !isEditingExpertComment;
  }
  if (adminReportDetailExpertCommentEdit) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertCommentEdit.hidden = !canEditExpertComment || !hasExpertRecord || isEditingExpertComment;
    adminReportDetailExpertCommentEdit.disabled = !canEditExpertComment || !hasExpertRecord;
  }
  if (adminReportDetailExpertCommentCancel) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertCommentCancel.hidden = !isEditingExpertComment;
    adminReportDetailExpertCommentCancel.disabled = !isEditingExpertComment || !hasExpertRecord;
  }
  if (adminReportDetailExpertCommentSave) {
    const canEditExpertComment = Boolean(detail.can_edit_expert_comment);
    const hasExpertRecord = Boolean(
      (detail.expert_comment || '').trim() ||
      (detail.expert_name || '').trim() ||
      (detail.expert_contacts || '').trim() ||
      detail.expert_assessed_at,
    );
    const isEditingExpertComment =
      canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
    adminReportDetailExpertCommentSave.hidden = canEditExpertComment && hasExpertRecord && !isEditingExpertComment;
    adminReportDetailExpertCommentSave.disabled = !isEditingExpertComment;
    adminReportDetailExpertCommentSave.textContent = 'Сохранить комментарий';
  }
  if (adminReportDetailExpertCommentStatus) {
    adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
      ? 'Изменения не сохранены.'
      : '';
  }

  const profileSummary = detail.profile_summary || {};
  if (adminReportDetailProfilePosition) {
    adminReportDetailProfilePosition.textContent = profileSummary.position || 'Нет данных';
  }
  if (adminReportDetailProfileDuties) {
    adminReportDetailProfileDuties.textContent = profileSummary.duties || 'Нет данных';
  }
  if (adminReportDetailProfileDomain) {
    adminReportDetailProfileDomain.textContent = profileSummary.domain || 'Нет данных';
  }
  renderAdminProfileSummaryList(adminReportDetailProfileProcesses, profileSummary.processes);
  renderAdminProfileSummaryList(adminReportDetailProfileTasks, profileSummary.tasks);
  renderAdminProfileSummaryList(adminReportDetailProfileStakeholders, profileSummary.stakeholders);
  renderAdminProfileSummaryList(adminReportDetailProfileConstraints, profileSummary.constraints);

  renderAdminSkillRadar(state.adminReportDetailSkillAssessments);

  if (adminReportDetailMbtiAxes) {
    adminReportDetailMbtiAxes.innerHTML = '';
    mbtiAxes.forEach((axis) => {
      const item = document.createElement('div');
      item.className = 'admin-detail-mbti-axis';
      const value = Math.max(0, Math.min(100, Number(axis.value) || 0));
      item.innerHTML =
        '<div class="admin-detail-mbti-axis-head"><span>' +
        (axis.left || 'Нет данных') +
        '</span><span>' +
        (axis.right || 'Нет данных') +
        '</span></div>' +
        '<div class="admin-detail-mbti-axis-track"><span style="width:' +
        value +
        '%"></span></div>';
      adminReportDetailMbtiAxes.appendChild(item);
    });
  }

  adminReportDetailBasis.innerHTML = '';
  (detail.basis_items && detail.basis_items.length ? detail.basis_items : []).forEach((text) => {
    const item = document.createElement('li');
    item.innerHTML = highlightAdminInsightFigures(text);
    adminReportDetailBasis.appendChild(item);
  });

  adminReportDetailStrengths.innerHTML = '';
  (detail.strengths && detail.strengths.length
    ? detail.strengths
    : ['Сильные стороны будут определены после анализа результатов.']
  ).forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    adminReportDetailStrengths.appendChild(item);
  });

  adminReportDetailGrowth.innerHTML = '';
  (detail.growth_areas && detail.growth_areas.length
    ? detail.growth_areas
    : ['Зоны роста будут определены после анализа результатов.']
  ).forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    adminReportDetailGrowth.appendChild(item);
  });

  adminReportDetailQuotes.innerHTML = '';
  (detail.quotes && detail.quotes.length ? detail.quotes : []).forEach((text) => {
    const card = document.createElement('article');
    card.className = 'card card--inset admin-detail-quote-card';
    card.innerHTML = '<p>' + escapeHtml(text) + '</p>';
    adminReportDetailQuotes.appendChild(card);
  });

  if (adminReportDetailCases) {
    const caseItems = Array.isArray(detail.case_items) ? detail.case_items : [];
    adminReportDetailCases.innerHTML = '';
    if (!caseItems.length) {
      adminReportDetailCases.innerHTML =
        '<p class="report-empty-state">Для этой сессии пока не сохранены кейсы или история диалога.</p>';
    } else {
      const renderCaseTextBlock = (label, text) => {
        const normalized = String(text || '').trim();
        if (!normalized) {
          return '';
        }
        return (
          '<div class="admin-detail-case-text-block">' +
          '<strong>' +
          escapeHtml(label) +
          '</strong>' +
          '<p>' +
          escapeHtml(normalized) +
          '</p>' +
          '</div>'
        );
      };

      caseItems.forEach((item) => {
        const statusMap = {
          selected: 'Выбран',
          shown: 'Показан',
          answered: 'Отвечен',
          assessed: 'Оценен',
          completed: 'Завершен',
        };
        const startedAt = item.started_at
          ? new Date(item.started_at).toLocaleString('ru-RU', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })
          : 'Нет данных';
        const finishedAt = item.finished_at
          ? new Date(item.finished_at).toLocaleString('ru-RU', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })
          : 'Нет данных';
        const textBlocks = [
          renderCaseTextBlock('Контекст', item.personalized_context),
          renderCaseTextBlock('Задача', item.personalized_task),
        ]
          .filter(Boolean)
          .join('');
        const promptBlock = item.prompt_text
          ? '<details class="admin-detail-case-prompt-details">' +
            '<summary>Показать полный промпт</summary>' +
            '<pre>' +
            escapeHtml(item.prompt_text) +
            '</pre>' +
            '</details>'
          : '';
        const details = document.createElement('details');
        details.className = 'card admin-detail-case-item';
        details.innerHTML =
          '<summary class="admin-detail-case-summary">' +
          '<div class="admin-detail-case-summary-main">' +
          '<span class="admin-detail-case-order">Кейс ' +
          escapeHtml(item.case_number) +
          '</span>' +
          '<strong>' +
          escapeHtml(item.case_title || 'Кейс без названия') +
          '</strong>' +
          '<span class="admin-detail-case-code">' +
          escapeHtml(item.case_id_code || 'Без ID') +
          '</span>' +
          '</div>' +
          '<div class="admin-detail-case-summary-meta">' +
          '<span>' +
          escapeHtml(statusMap[item.status] || item.status || 'Неизвестно') +
          '</span>' +
          '<span>' +
          escapeHtml((item.dialogue || []).length) +
          ' сообщений</span>' +
          '<span>' +
          escapeHtml((item.skill_results || []).length) +
          ' навыков</span>' +
          '</div>' +
          '</summary>' +
          '<div class="admin-detail-case-body">' +
          '<div class="admin-detail-case-columns">' +
          '<section class="card admin-detail-case-panel">' +
          '<details class="admin-detail-case-section" open>' +
          '<summary class="admin-detail-case-section-summary">Текст кейса</summary>' +
          '<div class="admin-detail-case-section-body">' +
          '<div class="admin-detail-case-meta"><span>Начало: ' +
          escapeHtml(startedAt) +
          '</span><span>Завершение: ' +
          escapeHtml(finishedAt) +
          '</span></div>' +
          '<div class="admin-detail-case-text-stack">' +
          (textBlocks || '<p class="report-empty-state">Текст кейса в этой сессии не сохранен.</p>') +
          '</div>' +
          promptBlock +
          '</div>' +
          '</details>' +
          '</section>' +
          '<section class="card admin-detail-case-panel">' +
          '<details class="admin-detail-case-section" open>' +
          '<summary class="admin-detail-case-section-summary">Диалог по кейсу</summary>' +
          '<div class="admin-detail-case-section-body">' +
          '<div class="admin-detail-case-dialogue">' +
          '<div class="admin-detail-case-dialogue-toolbar">' +
          '<span class="admin-detail-case-dialogue-caption">Диалог пользователя с агентом</span>' +
          '<button type="button" class="ghost-button compact-ghost admin-detail-case-dialogue-pdf-button" data-session-id="' +
          escapeHtml(detail.session_id) +
          '" data-session-case-id="' +
          escapeHtml(item.session_case_id) +
          '"><img class="button-icon" src="/web/assets/icons/download-icon.svg" alt="" aria-hidden="true">Скачать диалог PDF</button>' +
          '</div>' +
          ((item.dialogue || []).length
            ? item.dialogue
                .map(
                  (message) =>
                    '<article class="admin-detail-case-message ' +
                    (message.role === 'user' ? 'is-user' : 'is-assistant') +
                    '">' +
                    '<span class="admin-detail-case-message-role">' +
                    escapeHtml(message.role === 'user' ? 'Пользователь' : 'Ассистент') +
                    '</span>' +
                    '<p>' +
                    escapeHtml(message.message_text || '') +
                    '</p>' +
                    '</article>',
                )
                .join('')
            : '<p class="report-empty-state">Диалог по кейсу не найден.</p>') +
          '</div>' +
          '</div>' +
          '</details>' +
          '</section>' +
          '</div>' +
          '<section class="card admin-detail-case-panel">' +
          '<h4>Результат по кейсу</h4>' +
          '<div class="admin-detail-case-skills">' +
          ((item.skill_results || []).length
            ? item.skill_results
                .map(
                  (skill) =>
                    '<article class="card admin-detail-case-skill-card">' +
                    '<div class="admin-detail-case-skill-head">' +
                    '<strong>' +
                    escapeHtml(skill.skill_name || 'Навык') +
                    '</strong>' +
                    '<span>' +
                    escapeHtml(skill.assessed_level_name || skill.assessed_level_code || 'Без уровня') +
                    '</span>' +
                    '</div>' +
                    '<div class="admin-detail-case-skill-meta">' +
                    '<span>' +
                    escapeHtml(skill.competency_name || 'Без категории') +
                    '</span>' +
                    '<span>Artifact: ' +
                    escapeHtml(
                      typeof skill.artifact_compliance_percent === 'number'
                        ? skill.artifact_compliance_percent + '%'
                        : '—',
                    ) +
                    '</span>' +
                    '<span>Blocks: ' +
                    escapeHtml(
                      typeof skill.block_coverage_percent === 'number' ? skill.block_coverage_percent + '%' : '—',
                    ) +
                    '</span>' +
                    '</div>' +
                    '<div class="admin-detail-case-tags">' +
                    ((skill.red_flags || [])
                      .map((flag) => '<span class="admin-detail-case-tag danger">' + escapeHtml(flag) + '</span>')
                      .join('') || '<span class="admin-detail-case-tag muted">Без red flags</span>') +
                    (skill.found_evidence || [])
                      .map((itemText) => '<span class="admin-detail-case-tag">' + escapeHtml(itemText) + '</span>')
                      .join('') +
                    '</div>' +
                    (skill.evidence_excerpt
                      ? '<p class="admin-detail-case-evidence">' + escapeHtml(skill.evidence_excerpt) + '</p>'
                      : '') +
                    '</article>',
                )
                .join('')
            : '<p class="report-empty-state">Локальная аналитика по кейсу не найдена.</p>') +
          '</div>' +
          '</section>' +
          '</div>';
        const caseDialoguePdfButton = details.querySelector('.admin-detail-case-dialogue-pdf-button');
        if (caseDialoguePdfButton) {
          caseDialoguePdfButton.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            window.location.href =
              '/users/admin/reports/' + detail.session_id + '/cases/' + item.session_case_id + '/dialogue.pdf';
          });
        }
        adminReportDetailCases.appendChild(details);
      });
    }
  }

  if (adminReportDetailPdfButton) {
    adminReportDetailPdfButton.disabled = !(detail.user_id && detail.session_id);
  }
  if (adminReportDetailExpertPdfButton) {
    adminReportDetailExpertPdfButton.disabled = !detail.session_id;
  }
  if (adminReportDetailDialoguesPdfButton) {
    adminReportDetailDialoguesPdfButton.disabled = !detail.session_id;
  }
};

export const saveAdminReportExpertComment = async () => {
  const detail = state.adminReportDetail;
  if (!detail?.session_id || !adminReportDetailExpertComment) {
    return;
  }
  if (!detail.can_edit_expert_comment) {
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = 'Комментарий доступен только для завершенного ассессмента.';
    }
    return;
  }
  const previousText = adminReportDetailExpertCommentSave ? adminReportDetailExpertCommentSave.textContent : '';
  if (adminReportDetailExpertCommentSave) {
    adminReportDetailExpertCommentSave.disabled = true;
    adminReportDetailExpertCommentSave.textContent = 'Сохраняем...';
  }
  if (adminReportDetailExpertCommentStatus) {
    adminReportDetailExpertCommentStatus.textContent = '';
  }
  try {
    const response = await fetch('/users/admin/reports/' + detail.session_id + '/expert-comment', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        expert_comment: adminReportDetailExpertComment.value.trim() || null,
        expert_name: adminReportDetailExpertName?.value.trim() || null,
        expert_contacts: adminReportDetailExpertContacts?.value.trim() || null,
        expert_assessed_at: normalizeExpertAssessmentDateForApi(adminReportDetailExpertAssessedAt?.value),
      }),
    });
    const data = await readApiResponse(response, 'Не удалось сохранить комментарий эксперта.');
    state.adminReportDetail = data;
    state.adminReportDetailExpertCommentEditing = false;
    state.adminReportDetailExpertCommentOriginal = data?.expert_comment || '';
    state.adminReportDetailExpertCommentDirty = false;
    state.adminReportDetailExpertMetaOriginal = {
      expert_name: data?.expert_name || '',
      expert_contacts: data?.expert_contacts || '',
      expert_assessed_at: formatDateInputValue(data?.expert_assessed_at),
    };
    renderAdminReportDetail();
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = 'Комментарий сохранен.';
    }
  } catch (error) {
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = error.message;
    }
  } finally {
    if (adminReportDetailExpertCommentSave) {
      const detailState = state.adminReportDetail;
      const canEditExpertComment = Boolean(detailState?.can_edit_expert_comment);
      const hasExpertRecord = Boolean(
        (detailState?.expert_comment || '').trim() ||
        (detailState?.expert_name || '').trim() ||
        (detailState?.expert_contacts || '').trim() ||
        detailState?.expert_assessed_at,
      );
      const isEditingExpertComment =
        canEditExpertComment && (!hasExpertRecord || state.adminReportDetailExpertCommentEditing);
      adminReportDetailExpertCommentSave.hidden = canEditExpertComment && hasExpertRecord && !isEditingExpertComment;
      adminReportDetailExpertCommentSave.disabled = !isEditingExpertComment;
      adminReportDetailExpertCommentSave.textContent = previousText || 'Сохранить комментарий';
    }
  }
};

export const enableAdminReportExpertCommentEditing = () => {
  const detail = state.adminReportDetail;
  if (!detail?.can_edit_expert_comment) {
    return;
  }
  state.adminReportDetailExpertCommentEditing = true;
  state.adminReportDetailExpertCommentDirty = false;
  renderAdminReportDetail();
  if (adminReportDetailExpertComment) {
    adminReportDetailExpertComment.focus();
    const length = adminReportDetailExpertComment.value.length;
    adminReportDetailExpertComment.setSelectionRange(length, length);
  }
  if (adminReportDetailExpertCommentStatus) {
    adminReportDetailExpertCommentStatus.textContent = '';
  }
};

export const cancelAdminReportExpertCommentEditing = () => {
  const detail = state.adminReportDetail;
  if (!detail?.can_edit_expert_comment) {
    return;
  }
  state.adminReportDetailExpertCommentEditing = false;
  state.adminReportDetailExpertCommentDirty = false;
  if (adminReportDetailExpertName) {
    adminReportDetailExpertName.value = state.adminReportDetailExpertMetaOriginal.expert_name || '';
  }
  if (adminReportDetailExpertContacts) {
    adminReportDetailExpertContacts.value = state.adminReportDetailExpertMetaOriginal.expert_contacts || '';
  }
  if (adminReportDetailExpertAssessedAt) {
    adminReportDetailExpertAssessedAt.value = state.adminReportDetailExpertMetaOriginal.expert_assessed_at || '';
  }
  if (adminReportDetailExpertComment) {
    adminReportDetailExpertComment.value = state.adminReportDetailExpertCommentOriginal || '';
  }
  renderAdminReportDetail();
  if (adminReportDetailExpertCommentStatus) {
    adminReportDetailExpertCommentStatus.textContent = '';
  }
};

export const updateAdminExpertCommentDirtyState = () => {
  const currentComment = adminReportDetailExpertComment?.value.trim() || '';
  const originalComment = String(state.adminReportDetailExpertCommentOriginal || '').trim();
  const currentMeta = {
    expert_name: adminReportDetailExpertName?.value.trim() || '',
    expert_contacts: adminReportDetailExpertContacts?.value.trim() || '',
    expert_assessed_at: adminReportDetailExpertAssessedAt?.value || '',
  };
  const originalMeta = state.adminReportDetailExpertMetaOriginal || {};
  state.adminReportDetailExpertCommentDirty =
    currentComment !== originalComment ||
    currentMeta.expert_name !== String(originalMeta.expert_name || '').trim() ||
    currentMeta.expert_contacts !== String(originalMeta.expert_contacts || '').trim() ||
    currentMeta.expert_assessed_at !== String(originalMeta.expert_assessed_at || '');
};

if (adminReportDetailExpertName) {
  adminReportDetailExpertName.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    updateAdminExpertCommentDirtyState();
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
        ? 'Изменения не сохранены.'
        : '';
    }
  });
}

if (adminReportDetailExpertContacts) {
  adminReportDetailExpertContacts.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    updateAdminExpertCommentDirtyState();
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
        ? 'Изменения не сохранены.'
        : '';
    }
  });
}

if (adminReportDetailExpertAssessedAt) {
  adminReportDetailExpertAssessedAt.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    updateAdminExpertCommentDirtyState();
    if (adminReportDetailExpertCommentStatus) {
      adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
        ? 'Изменения не сохранены.'
        : '';
    }
  });
}

export const openAdminReportDetail = async (sessionId) => {
  setCurrentScreen('admin-report-detail');
  state.adminReportDetailSessionId = sessionId;
  state.adminReportDetailSkillAssessments = [];
  state.adminReportDetailSkillAssessmentsLoading = true;
  persistAssessmentContext();
  syncUrlState('admin-report-detail');
  hideAllPanels();
  adminReportDetailPanel.classList.remove('hidden');
  adminReportDetailName.textContent = 'Загружаем отчет...';
  adminReportDetailRole.textContent = 'Подождите, пожалуйста';
  adminReportDetailGroup.textContent = '';
  if (adminReportDetailPhone) {
    adminReportDetailPhone.textContent = '';
  }
  if (adminReportDetailTelegram) {
    adminReportDetailTelegram.textContent = '';
  }
  adminReportDetailDate.textContent = 'Без даты';
  adminReportDetailScore.textContent = '0%';
  if (adminReportDetailStatusBadge) {
    adminReportDetailStatusBadge.textContent = 'Подготовка';
  }
  renderAdminSkillRadar([]);
  adminReportDetailInsightTitle.textContent = 'Загружаем AI insight...';
  adminReportDetailInsightText.textContent = 'Подготавливаем интерпретацию результатов пользователя.';
  if (adminReportDetailMbtiAxes) {
    adminReportDetailMbtiAxes.innerHTML = '';
  }
  adminReportDetailBasis.innerHTML = '';
  adminReportDetailStrengths.innerHTML = '';
  adminReportDetailGrowth.innerHTML = '';
  adminReportDetailQuotes.innerHTML = '';
  if (adminReportDetailCases) {
    adminReportDetailCases.innerHTML = '';
  }
  try {
    await loadAdminReportDetail(sessionId);
    renderAdminReportDetail();
    if (state.adminReportDetail?.user_id && state.adminReportDetail?.session_id) {
      try {
        await loadAdminReportDetailSkillAssessments(
          state.adminReportDetail.user_id,
          state.adminReportDetail.session_id,
        );
      } catch (skillError) {
        console.error('Failed to load admin skill assessments', skillError);
        state.adminReportDetailSkillAssessments = [];
      } finally {
        state.adminReportDetailSkillAssessmentsLoading = false;
      }
      renderAdminSkillRadar(state.adminReportDetailSkillAssessments);
    } else {
      state.adminReportDetailSkillAssessmentsLoading = false;
      renderAdminSkillRadar([]);
    }
  } catch (error) {
    state.adminReportDetail = null;
    state.adminReportDetailSkillAssessments = [];
    state.adminReportDetailSkillAssessmentsLoading = false;
    adminReportDetailName.textContent = 'Не удалось загрузить отчет';
    adminReportDetailRole.textContent = error.message;
    adminReportDetailGroup.textContent = 'Попробуйте открыть запись позже';
    if (adminReportDetailPhone) {
      adminReportDetailPhone.textContent = '';
    }
    if (adminReportDetailTelegram) {
      adminReportDetailTelegram.textContent = '';
    }
    renderAdminSkillRadar([]);
    adminReportDetailInsightTitle.textContent = 'Не удалось загрузить AI insight';
    adminReportDetailInsightText.textContent = error.message;
    if (adminReportDetailMbtiSummary) {
      adminReportDetailMbtiSummary.textContent = 'Не удалось загрузить данные MBTI.';
    }
    adminReportDetailBasis.innerHTML = '';
    adminReportDetailStrengths.innerHTML = '<li>Данные временно недоступны.</li>';
    adminReportDetailGrowth.innerHTML = '<li>Данные временно недоступны.</li>';
    adminReportDetailQuotes.innerHTML = '';
  }
};
