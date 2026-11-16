export const getReportScoreValue = (skill) => {
  const value = skill?.score?.value;
  if (value == null || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= 0 && numeric <= 3 ? numeric : null;
};

export const splitRadarRuns = (values) => {
  if (!values.length) return [];
  const available = values.map((value) => value != null);
  if (available.every(Boolean)) return [{ indexes: values.map((_, index) => index), closed: true }];
  if (available.every((value) => !value)) return [];

  const firstGap = available.findIndex((value) => !value);
  const runs = [];
  let current = [];
  for (let step = 1; step <= values.length; step += 1) {
    const index = (firstGap + step) % values.length;
    if (available[index]) {
      current.push(index);
    } else if (current.length) {
      runs.push({ indexes: current, closed: false });
      current = [];
    }
  }
  if (current.length) runs.push({ indexes: current, closed: false });
  return runs;
};

export const summarizeReportScores = (skills) => {
  const values = skills.map(getReportScoreValue);
  return {
    values,
    hasScores: values.some((value) => value != null),
    allZero: values.length > 0 && values.every((value) => value === 0),
    missingCount: values.filter((value) => value == null).length,
  };
};

// Pure projection of one saved Report. It is also suitable for a PDF or comparison
// renderer: neither geometry nor labels need a browser or a current catalog.
export const projectReportRadar = (skills) => {
  const axes = skills.map((skill) => {
    const value = getReportScoreValue(skill);
    return {
      skillId: skill.skill_id,
      competencyId: skill.competency_id,
      name: skill.skill_name || 'Навык',
      value,
      displayValue: value == null ? null : String(skill.score.value),
      partial: skill.outcome === 'partial_score',
      status: skill.presentation?.label || null,
      limitations: [
        ...(skill.presentation?.reasons || []).map((reason) => reason.message).filter(Boolean),
        ...(Array.isArray(skill.limitations) ? skill.limitations : []),
      ],
    };
  });
  return { axes, runs: splitRadarRuns(axes.map((axis) => axis.value)) };
};

export const radarPoint = (index, value, count, centerX, centerY, radius) => {
  const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
  return {
    x: centerX + Math.cos(angle) * radius * value / 3,
    y: centerY + Math.sin(angle) * radius * value / 3,
  };
};
