// Local synthetic connection gallery, actual HTML/dist; no TEST or data contour.
import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';
import { spawnSync } from 'node:child_process';
let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18945 }); });
test.afterAll(async () => { await preview?.close(); });

for (const role of ['admin', 'superadmin']) for (const status of ['absent', 'unknown', 'confirmed']) {
  test(`ADM-PROGRAM AC06 ${role} ${status}: forms and readiness 1440/390/320 and text200`, async ({ page }, info) => {
    const rows = [];
    for (const width of [1440, 390, 320]) for (const textScale of [1, 2]) for (const view of (role === 'superadmin' ? ['people'] : ['organization-data', 'questionnaire', 'people'])) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(`${preview.base}/demo/${role}/${status}/`);
      if (role === 'superadmin') {
        await expect.poll(async () => await page.locator('#admin-open-organizations-button').isVisible() ||
          await page.locator('#admin-organizations-panel').isVisible()).toBe(true);
        if (await page.locator('#admin-open-organizations-button').isVisible()) await page.locator('#admin-open-organizations-button').click();
        await page.locator('#platform-org-rows [data-org-id="3"]:not([data-org-admins])').click();
      }
      const card = page.locator('[data-organization-id="3"]');
      await expect(card).toBeVisible();
      await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
      await card.locator(`.admin-organization-step[data-view="${view}"]`).click();
      const participantHelp = view === 'people' && role === 'admin';
      const form = view === 'people'
        ? card.locator(participantHelp ? '.admin-member-action-help' : '.admin-assignment-readiness')
        : card.locator('form[data-action="' + (view === 'questionnaire' ? 'preview-questionnaire' : 'preview-early-data') + '"]');
      const sourceSelector = participantHelp ? 'summary' : view === 'people' ? 'input[name="invitation_email"]'
        : view === 'questionnaire' ? 'input[type="file"]' : '[name="purpose"]';
      const buttonSelector = participantHelp ? 'summary' : view === 'people'
        ? 'form[data-action="assign-member-assessment"] button[type="submit"]' : 'button[type="submit"]';
      const formScope = view === 'people' && !participantHelp ? card : form;
      const author = formScope.locator(sourceSelector);
      const button = formScope.locator(buttonSelector);
      await expect(form).toBeVisible();
      if (participantHelp) {
        await author.click();
        await expect(form).toHaveAttribute('open', '');
        await expect(card.locator('form[data-action="assign-member-assessment"]')).toHaveCount(0);
      } else if (view === 'people') await author.check();
      else if (view === 'organization-data') await author.fill('synthetic-contact@example.test');
      if (view === 'questionnaire') await author.setInputFiles({
        name: 'synthetic-questionnaire-long-file-name.csv', mimeType: 'text/csv',
        buffer: Buffer.from('question_id,field,value\nC01,name,Синтетическая организация\n'),
      });
      if (textScale === 2) {
        await page.evaluate(() => {
          // Snapshot all computed sizes before assigning any, avoiding compounding.
          const nodes = [...document.querySelectorAll('#admin-organizations-panel, #admin-organizations-panel *')];
          const styles = nodes.map((node) => ({ node, font: parseFloat(getComputedStyle(node).fontSize),
            line: parseFloat(getComputedStyle(node).lineHeight) }));
          for (const { node, font, line } of styles) {
            if (Number.isFinite(font)) node.style.fontSize = `${font * 2}px`;
            if (Number.isFinite(line)) node.style.lineHeight = `${line * 2}px`;
          }
        });
      }
      await author.focus();
      await expect(author).toBeFocused();
      if (!participantHelp) {
        if (status === 'confirmed' && view !== 'people') await expect(button).toBeEnabled();
        else await expect(button).toBeDisabled();
      }
      await button.scrollIntoViewIfNeeded();
      const metrics = await form.evaluate((node, { sourceSelector, buttonSelector }) => {
        const scope = node.classList.contains('admin-assignment-readiness') ? node.closest('[data-organization-id]') : node;
        const source = scope.querySelector(sourceSelector);
        const submit = scope.querySelector(buttonSelector);
        return { viewport: innerWidth,
        document: document.documentElement.scrollWidth, form: node.getBoundingClientRect().toJSON(),
        authorFontPx: getComputedStyle(source).fontSize,
        documentOutliers: [...document.querySelectorAll('body *')].filter((element) => {
          const rect = element.getBoundingClientRect(); return rect.width && (rect.x < -1 || rect.right > innerWidth + 1);
        }).map((element) => ({ tag: element.tagName, class: element.className,
          name: element.getAttribute('name'), rect: element.getBoundingClientRect().toJSON() })),
        button: submit.getBoundingClientRect().toJSON(),
        horizontalOutliers: [...node.querySelectorAll('*')].filter((element) => {
          const rect = element.getBoundingClientRect(); return rect.width && (rect.x < 0 || rect.right > innerWidth + 1);
        }).map((element) => ({ tag: element.tagName, name: element.getAttribute('name'), text: element.textContent.slice(0, 80) })) };
      }, { sourceSelector, buttonSelector });
      rows.push({ role, status, width, view, textScale, ...metrics });
      await info.attach(`${view}-${width}-text${textScale * 100}-metrics`, { body: JSON.stringify(rows.at(-1), null, 2), contentType: 'application/json' });
      await page.screenshot({ path: info.outputPath(`${role}-${status}-${view}-${width}-text${textScale * 100}.png`), fullPage: true });
      expect(metrics.document).toBeLessThanOrEqual(width + 1);
      expect(metrics.horizontalOutliers).toEqual([]);
      expect(metrics.button.width).toBeGreaterThan(40);
      expect(metrics.button.y).toBeGreaterThanOrEqual(0);
      expect(metrics.button.bottom).toBeLessThanOrEqual(1001);
    }
    await info.attach('visual-matrix', { body: JSON.stringify({ scope: 'local_synthetic_http',
      source_sha: spawnSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).stdout.trim(),
      identity: preview.identity, physical_devices: 'NOT_RUN', native_text_zoom: 'NOT_RUN', rows }, null, 2), contentType: 'application/json' });
  });
}
