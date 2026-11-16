// Numbers are a server-owned projection of one saved Cycle/plan revision.
export const assessmentPositionText = (card) => {
  const total = card.planned_total;
  const knownTotal = Number.isInteger(total) && total > 0;
  if (card.journey_state === 'between_situations') {
    const completedPosition = card.last_completed_position_no;
    return Number.isInteger(completedPosition) && completedPosition > 0
      ? `Ситуация ${completedPosition} завершена` : '';
  }
  if (['active', 'paused', 'interrupted'].includes(card.status)) {
    const current = card.current_position_no;
    if (Number.isInteger(current) && current > 0 && knownTotal && current <= total) {
      return `${current} ситуация из ${total}`;
    }
  }
  return knownTotal ? `${total} ситуаций в плане` : '';
};

export const formatAssessmentDate = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Moscow',
  }).format(date).replace(/\s*г\.$/u, '');
};

// Presentation follows the server's journey; counts never determine its state.
export const assessmentMetadata = (card) => {
  const items = [];
  const add = (label, value) => { if (value) items.push({ label, value }); };
  add('Организация', card.organization_name);
  const journey = card.journey_state || card.status;
  if (card.closed_at || ['report_ready', 'processing', 'failed'].includes(journey)) {
    add('Дата завершения', formatAssessmentDate(card.closed_at));
  } else if (journey === 'ready') {
    const total = card.planned_total;
    if (Number.isInteger(total) && total > 0) {
      const noun = { one: 'ситуация', few: 'ситуации', many: 'ситуаций', other: 'ситуации' }[
        new Intl.PluralRules('ru-RU').select(total)];
      add('План оценки', `${total} ${noun}`);
    }
  } else if (['preparing', 'acquaintance', 'organization_preparing', 'participant_details_required',
    'preparation_failed', 'readiness_error', 'not_ready', 'unassigned'].includes(journey)) {
    add('Начало оценки', 'Оценка ещё не начата');
  } else {
    const text = assessmentPositionText(card);
    add(text.endsWith('в плане') ? 'План оценки' : 'Текущая ситуация', text);
  }
  return items;
};
