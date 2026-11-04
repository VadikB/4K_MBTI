"use strict";

const HIGH_RISK = [
  /^\.github\/workflows\//,
  /^database\//,
  /^Api\/(auth|database|assessment|agent)/,
  /^scripts\/deploy_/,
  /migration/i,
];
const LOW_RISK = [/\.md$/i, /^docs\//];

function classifyPaths(paths) {
  if (paths.some((path) => HIGH_RISK.some((pattern) => pattern.test(path)))) {
    return "high";
  }
  if (paths.length > 0 && paths.every((path) => LOW_RISK.some((pattern) => pattern.test(path)))) {
    return "low";
  }
  return "medium";
}

function findOverlaps(currentPaths, pullRequests) {
  const current = new Set(currentPaths);
  return pullRequests
    .map((pullRequest) => ({
      number: pullRequest.number,
      title: pullRequest.title,
      paths: [...new Set(pullRequest.paths.filter((path) => current.has(path)))].sort(),
    }))
    .filter((pullRequest) => pullRequest.paths.length > 0)
    .sort((left, right) => left.number - right.number);
}

function formatSummary({ risk, overlaps }) {
  const lines = ["## Координация PR", "", `Класс риска путей: **${risk}**.`, ""];
  if (overlaps.length === 0) {
    lines.push("Пересечений файлов с другими открытыми PR не найдено.");
    return lines.join("\n");
  }
  lines.push("Найдены пересечения; до merge зафиксируйте `depends_on` или порядок разрешения:", "");
  for (const overlap of overlaps) {
    lines.push(`- #${overlap.number} ${overlap.title}: ${overlap.paths.map((path) => `\`${path}\``).join(", ")}`);
  }
  return lines.join("\n");
}

module.exports = { classifyPaths, findOverlaps, formatSummary };
