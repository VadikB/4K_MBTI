import { competencyPalette, fallbackCompetencyPalette, competencyOrder, levelPercentMap } from '../config.js';

export const getCompetencyPalette = (competencyName) =>
  competencyPalette[competencyName] || fallbackCompetencyPalette;

export const getCompetencySortIndex = (competencyName) => {
  const index = competencyOrder.indexOf(competencyName);
  return index === -1 ? competencyOrder.length : index;
};

export const getLevelPercent = (levelCode) => levelPercentMap[levelCode] ?? 0;
