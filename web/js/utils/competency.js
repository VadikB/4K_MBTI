import { levelPercentMap } from '../config.js';

export const getLevelPercent = (levelCode) => levelPercentMap[levelCode] ?? 0;
