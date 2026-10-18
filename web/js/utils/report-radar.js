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
