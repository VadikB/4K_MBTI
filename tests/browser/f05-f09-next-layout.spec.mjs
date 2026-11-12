import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

// Component geometry in a real browser. The owned HTTP/PG route is checked separately.
const css = ['tokens.css', 'base.css', 'components.css', 'screens/interview.css']
  .map((name) => fs.readFileSync(path.resolve('web/styles', name), 'utf8')).join('\n');
const evidence = path.resolve('docs/evc/tasks/p4k-f05-f09-one/evidence');

test('F09 Next card is readable at desktop, mobile and enlarged text', async ({ page }) => {
  fs.mkdirSync(evidence, { recursive: true });
  for (const [name, width, zoom] of [
    ['desktop-1440', 1440, 1], ['mobile-390', 390, 1],
    ['mobile-320', 320, 1], ['mobile-320-text-200', 320, 2],
  ]) {
    await page.setViewportSize({ width, height: 900 });
    await page.setContent(`<html lang="ru"><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
      <body><main class="interview-panel"><div class="interview-messages">
      <section class="interview-return-card"><h3>Ситуация 1 завершена</h3>
      <p>Ответы сохранены. Сейчас пауза: время на выполнение не расходуется.</p>
      <button type="button" class="primary-button">Проверить состояние</button>
      <p role="status">Подготовка продолжается. Очень длинное синтетическое пояснение: запрос
      к серверу завершился без ответа, операция продолжает выполняться и требует проверки состояния.</p>
      </section><textarea disabled aria-label="Ответ" placeholder="Ситуация завершена. Следующий ответ станет доступен после перехода."></textarea>
      </div></main></body></html>`);
    await page.addStyleTag({ content: css });
    if (zoom === 2) await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
    const button = page.getByRole('button', { name: /Проверить состояние/ });
    await expect(button).toBeVisible();
    await button.focus();
    await expect(button).toBeFocused();
    await expect(page.getByRole('status')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Ответ' })).toBeDisabled();
    const geometry = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      button: document.querySelector('.interview-return-card button').getBoundingClientRect().toJSON(),
      card: document.querySelector('.interview-return-card').getBoundingClientRect().toJSON(),
    }));
    expect(geometry.overflow, `${name} horizontal overflow`).toBeLessThanOrEqual(1);
    expect(geometry.button.width, `${name} button width`).toBeGreaterThan(180);
    expect(geometry.button.right, `${name} button within card`).toBeLessThanOrEqual(geometry.card.right + 1);
    await page.screenshot({ path: path.join(evidence, `f09-${name}.png`), fullPage: true });
  }
});
