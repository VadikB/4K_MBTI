# AC18 FIX-03 / P3-B — progress, time and return

Base `023bf85ec796d212d29b33218d906a1ed2023941`; implementation commits
`ab03144cf465b5213a722a26f9cf6538af64235e` and
`c06f7a74822c338767eb6f3e81fa5fe15e654c69` (plus task-state/docs commit).
Separate worktree/branch `codex/ac18-p3-b-time-return`. Release version remains
`2.0.86` in local candidate; bump is a separate authorized release step.

Problem: saved plan, return card and top indicator could show different totals;
unknown timing became `0`; a lost Continue response could lead to an independent
retry. New behavior: both API projections take the total from frozen plan.route;
UI distinguishes unknown timing from zero; return uses server pause and progress,
preserves an idempotency key across rerender/reload, performs readback, and clears
the key once active runtime is confirmed. Existing FIX-RETURN-01 remains intact.

Trace: M7 R1 v2 `sales-pilot-return-r1@2.0` checksum
`1121db8c84b6997ee427264a589b5db088588e134734d8ae0dbc0d2220a36f14`
→ `docs/architecture/m7-return-time-integration.md`, ADR-002/Change 01
→ `Api/m7_return_integration.py`, `Api/m10_product_flow.py`,
`web/js/screens/interview.js` → frontend, isolated PG, HTTP and browser checks.
Source file hashes: policy JSON `7ee12e5ebbd063ad27c24d415fbe388f9404ac33579621637cae1a94a9342e3a`;
M7 integration doc `4f77683101688bbfe2f5a3cd9aa2f042e951a45ec448a10afa96c541875c15fd`;
task package `TASK_3B_ARCHITECT.md` `64ec2a5616a4be9ed397e638993c6c73771d80bffd8a2d37ac1c7ce212a58f94`.

Verification: `CHECKS.csv` records commands, source SHA and evidence per criterion.
Frontend 157 PASS, backend minimum 977 PASS, M7 owned isolated PostgreSQL 31 PASS,
HTTP P03 2 PASS, browser P03/P3-B 4 PASS, visual six states × four widths 24 PASS,
ESLint/build/compile/diff PASS. A separate 200% text emulation measured overflow
543 px at 390 px viewport: FAIL in shared 3А mobile topbar/textarea. Physical
iOS/Android, owner visual decision, historical TEST OPS01 and CI: NOT_RUN.

No API/schema/methodology/policy change; no production/test data or paid LLM.
Rollback: revert the product commits and rebuild `web/dist`; no data migration.
P3-A owns shared mobile chat/keyboard layer; P3-I checks combined deployed SHA.
Push, PR, version bump, merge and deploy have not been authorized or executed.
