"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { classifyPaths, findOverlaps, formatSummary } = require("../../.github/scripts/pr_coordination.cjs");

test("classifies the highest path risk", () => {
  assert.equal(classifyPaths(["docs/evc/task.md"]), "low");
  assert.equal(classifyPaths(["web/js/main.js", "docs/note.md"]), "medium");
  assert.equal(classifyPaths(["web/js/main.js", ".github/workflows/ci.yml"]), "high");
});

test("finds and sorts overlaps with open pull requests", () => {
  const overlaps = findOverlaps(["Api/routes.py", "README.md"], [
    { number: 8, title: "Docs", paths: ["README.md", "README.md"] },
    { number: 4, title: "Other", paths: ["web/js/main.js"] },
  ]);
  assert.deepEqual(overlaps, [{ number: 8, title: "Docs", paths: ["README.md"] }]);
  assert.match(formatSummary({ risk: "high", overlaps }), /#8 Docs/);
});
