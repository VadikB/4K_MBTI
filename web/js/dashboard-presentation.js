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
