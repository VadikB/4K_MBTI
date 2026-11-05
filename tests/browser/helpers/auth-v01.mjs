// AUTH-V01: local, synthetic browser acceptance. baseRoutes rejects unknown /users/**.
export function registerAuthV01Tests({ test, expect, baseRoutes, base, fulfillJson, appRelease }) {
  const email = 'person@example.test';
  const longEmail = 'synthetic.participant.with.long.name.for.auth.check@example.test';
  const white = 'rgb(255, 255, 255)';
  const tokenUrl = (action = 'email_verification') => `${base}/?auth_action=${action}&token=auth-v01-local-only`;
  const fontReady = (page) => page.evaluate(() => document.fonts.ready.then(() => undefined));

  async function shell(page, panel = '#auth-panel') {
    await expect(page.locator(panel)).toBeVisible();
    await expect(page.locator('.auth-header')).toBeVisible();
    await expect(page.locator('.auth-header-brand:visible')).toHaveCount(1);
    await expect(page.locator('.auth-header-brand')).toHaveText('4К Ассистент');
    await expect(page.locator('.auth-panel .brand:visible, .auth-external-brand:visible')).toHaveCount(0);
    for (const selector of ['body', '.shell', '.auth-header', '.app-footer']) {
      await expect(page.locator(selector)).toHaveCSS('background-color', white);
    }
    await expect(page.locator('.app-footer')).toBeVisible();
    await expect(page.locator('.app-footer-release')).toBeHidden();
    await expect(page.locator('[data-app-release-badge]:visible')).toHaveCount(1);
    await expect(page.locator('.auth-release-badge')).toHaveText(`Релиз ${appRelease}`);
  }

  async function noOverflow(page, testInfo, label = 'layout') {
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      outliers: [...document.querySelectorAll('.auth-header *, #auth-panel *, .app-footer *')]
        .filter((element) => element.getBoundingClientRect().width > 0)
        .map((element) => ({ selector: element.id ? `#${element.id}` : element.className,
          x: element.getBoundingClientRect().x, right: element.getBoundingClientRect().right,
          scrollWidth: element.scrollWidth, clientWidth: element.clientWidth }))
        .filter((box) => box.x < 0 || box.right > document.documentElement.clientWidth || box.scrollWidth > box.clientWidth + 1),
    }));
    if (testInfo && dimensions.document > dimensions.viewport) {
      await testInfo.attach(`auth-v01-overflow-${label}.json`, { body: Buffer.from(JSON.stringify(dimensions, null, 2)), contentType: 'application/json' });
    }
    expect(dimensions.document, label).toBeLessThanOrEqual(dimensions.viewport);
    expect(dimensions.body, label).toBeLessThanOrEqual(dimensions.viewport);
    const boxes = await page.evaluate(() => {
      const box = (selector) => {
        const rect = document.querySelector(selector).getBoundingClientRect();
        return { x: rect.x, right: rect.right, top: rect.top, bottom: rect.bottom };
      };
      return { header: box('.auth-header'), card: box('#auth-panel'), footer: box('.app-footer') };
    });
    for (const box of Object.values(boxes)) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.right).toBeLessThanOrEqual(dimensions.viewport + 1);
    }
    expect(boxes.header.bottom).toBeLessThanOrEqual(boxes.card.top + 1);
    expect(boxes.card.bottom).toBeLessThanOrEqual(boxes.footer.top + 1);
    return dimensions;
  }

  async function reachable(locator) {
    await locator.scrollIntoViewIfNeeded();
    await expect(locator).toBeInViewport();
    const unobscured = await locator.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const target = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
      return element === target || element.contains(target);
    });
    expect(unobscured).toBe(true);
  }

  async function passwordStep(page, address = email) {
    await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, {
      email: address, auth_mode: 'password', message: 'Введите пароль.',
    }));
    await page.locator('#email-input').fill(address);
    await page.locator('#request-magic-link-button').click();
    await expect(page.locator('#auth-title')).toHaveText('С возвращением');
    await expect(page.locator('#auth-token-form')).toBeVisible();
  }

  async function geometry(page) {
    return page.evaluate(() => {
      const read = (selector) => {
        const element = document.querySelector(selector);
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height,
          fontFamily: style.fontFamily, fontSize: style.fontSize, fontWeight: style.fontWeight,
          lineHeight: style.lineHeight, borderRadius: style.borderRadius, padding: style.padding,
          background: style.backgroundColor, shadow: style.boxShadow };
      };
      return { viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio },
        fonts: [...document.fonts].filter((font) => font.family === 'Onest').map((font) => ({
          family: font.family, status: font.status, weight: font.weight,
        })), header: read('.auth-header'), brand: read('.auth-header-brand'), badge: read('.auth-release-badge'),
        card: read('#auth-panel'), title: read('#auth-title'),
        input: read(document.querySelector('#auth-email-form').classList.contains('hidden') ? '#magic-token-input' : '#email-input'),
        button: read(document.querySelector('#auth-email-form').classList.contains('hidden') ? '#verify-magic-link-button' : '#request-magic-link-button'),
        footer: read('.app-footer') };
    });
  }

  test('AUTH-V01 TC-02/03 initial HTML has a white independent auth header and frontend badge without JavaScript', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 1 });
    try {
      const page = await context.newPage();
      await page.goto(base);
      await shell(page, '#session-restore-panel');
      await expect(page.locator('#email-input')).toBeHidden();
      await expect(page.locator('.auth-header-brand')).toHaveCSS('font-family', /Onest/);
      expect(await page.locator('.app-footer').innerText()).not.toMatch(/Версия|Релиз/);
    } finally { await context.close(); }
  });

  test('AUTH-V01 TC-02/03/06 AUTH01 and AUTH03 retain original 1440x1024 geometry and Onest metrics', async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 1 });
    try {
      const page = await context.newPage();
      await baseRoutes(page);
      await page.goto(base);
      await fontReady(page);
      const measurements = {};
      for (const state of ['AUTH01', 'AUTH03']) {
        if (state === 'AUTH03') await passwordStep(page);
        await shell(page);
        const metrics = await geometry(page);
        measurements[state] = metrics;
        await testInfo.attach(`auth-v01-${state}-geometry.json`, { body: Buffer.from(JSON.stringify(metrics, null, 2)), contentType: 'application/json' });
        expect(metrics.viewport).toEqual({ width: 1440, height: 1024, dpr: 1 });
        expect(metrics.fonts.some((font) => font.status === 'loaded')).toBe(true);
        expect(metrics.brand).toMatchObject({ x: 62, y: 44, height: 24, fontSize: '20px', lineHeight: '24px', fontWeight: '700' });
        expect(metrics.brand.fontFamily).toMatch(/Onest/);
        expect(metrics.badge.x - metrics.brand.x - metrics.brand.width).toBeCloseTo(16, 1);
        expect(metrics.badge).toMatchObject({ height: 24, borderRadius: '8px', padding: '0px 12px' });
        expect(metrics.card.width).toBe(474);
        expect(metrics.card.height).toBe(474);
        expect(metrics.card.x).toBe(483);
        expect(Math.abs(metrics.card.y - 275.5)).toBeLessThanOrEqual(1);
        expect(metrics.card).toMatchObject({ borderRadius: '8px', padding: '36px 64px', background: 'rgb(179, 235, 239)', shadow: 'none' });
        expect(metrics.title).toMatchObject({ fontSize: '24px', lineHeight: '32px', fontWeight: '700' });
        expect(metrics.input).toMatchObject({ width: 346, height: 56, fontSize: '16px', borderRadius: '8px', background: 'rgb(246, 249, 249)' });
        expect(metrics.button).toMatchObject({ width: 346, height: 56, fontSize: '16px', lineHeight: '24px', borderRadius: '8px', background: 'rgb(34, 44, 48)', shadow: 'none' });
        await noOverflow(page);
        if (state === 'AUTH01') {
          await expect(page.locator('#email-input')).toHaveAccessibleName('Рабочий email');
          await expect(page.locator('#auth-email-form .field > span')).toHaveClass(/sr-only/);
          const labelBox = await page.locator('#auth-email-form .field > span').boundingBox();
          expect(labelBox.width).toBeLessThanOrEqual(1);
          expect(labelBox.height).toBeLessThanOrEqual(1);
        }
      }
      await testInfo.attach('auth-v01-desktop-geometry.json', { body: Buffer.from(JSON.stringify(measurements, null, 2)), contentType: 'application/json' });
    } finally { await context.close(); }
  });

  test('AUTH-V01 TC-04 header keeps exactly the frontend release through backend mismatch, outage and reload', async ({ page }) => {
    await baseRoutes(page);
    const backendVersion = appRelease === '0.0.0' ? '0.0.1' : '0.0.0';
    let outage = false;
    let versionRequests = 0;
    await page.route('**/users/version', (route) => {
      versionRequests += 1;
      return fulfillJson(route, outage ? { detail: 'synthetic unavailable' } : { version: backendVersion }, outage ? 503 : 200);
    });
    await page.goto(base);
    await expect.poll(() => versionRequests).toBe(1);
    await shell(page);
    await expect(page.locator('[data-app-release-number]:visible')).toHaveCount(1);
    outage = true;
    await page.reload();
    await expect.poll(() => versionRequests).toBe(2);
    await shell(page);
    await expect(page.locator('[data-app-release-number]:visible')).toHaveText(appRelease);
    await expect(page.locator('.auth-header')).not.toContainText(backendVersion);
  });

  test('AUTH-V01 TC-04 unknown release renderer safely hides the badge and preserves the brand', async ({ page }) => {
    await baseRoutes(page);
    await page.goto(base);
    await shell(page);
    // Exercise the real rendering boundary independently of the valid build config.
    await page.evaluate(async () => {
      const { renderReleaseVersion, resolveReleaseVersion } = await import('/web/js/release-version.js');
      renderReleaseVersion(document, resolveReleaseVersion('0.0.0', undefined));
    });
    await expect(page.locator('.auth-release-badge')).toBeHidden();
    await expect(page.locator('.auth-header-brand')).toBeVisible();
    await expect(page.locator('.auth-header-brand')).toHaveText('4К Ассистент');
  });

  for (const year of [2026, 2027]) {
    test(`AUTH-V01 TC-05 footer uses the fixture year ${year}, exact legal names and no release row`, async ({ page }) => {
      await page.clock.setFixedTime(new Date(`${year}-01-01T12:00:00+03:00`));
      await baseRoutes(page);
      await page.goto(base);
      await shell(page);
      const footer = page.locator('.app-footer');
      await expect(footer.locator('.app-footer-documents > span')).toHaveText([
        'Политика конфиденциальности', 'Согласие на обработку персональных данных',
      ]);
      await expect(footer.locator('.app-footer-copyright')).toHaveText(`© ${year} LIDUM`);
      await expect(footer.locator('a')).toHaveCount(0);
      await expect(footer).toHaveCSS('font-family', /Onest/);
      await expect(footer.locator('.app-footer-documents')).toHaveCSS('line-height', '16px');
      await expect(footer.locator('.app-footer-release')).toBeHidden();
    });
  }

  test('AUTH-V01 TC-08 AUTH01, AUTH03 and long messages fit widths 320–1440 without overlap', async ({ page }, testInfo) => {
    await baseRoutes(page);
    const measurements = [];
    const sizes = [[320, 568], [360, 760], [390, 844], [430, 932], [768, 1024], [1024, 768], [1440, 1024]];
    for (const [width, height] of sizes) {
      await page.setViewportSize({ width, height });
      await page.goto(base);
      await fontReady(page);
      for (const state of ['AUTH01', 'AUTH03', 'long error']) {
        if (state === 'AUTH03') await passwordStep(page, longEmail);
        if (state === 'long error') {
          await page.route('**/users/auth/email/password-login', (route) => fulfillJson(route, {
            detail: `Синтетическая подробная ошибка для ${longEmail}. Проверьте введённые данные и повторите попытку входа.`,
          }, 401));
          await page.locator('#magic-token-input').fill('Aa7!bC9@dE');
          await page.locator('#verify-magic-link-button').click();
          await expect(page.locator('#auth-error')).toBeVisible();
        }
        await shell(page);
        const input = page.locator(state === 'AUTH01' ? '#email-input' : '#magic-token-input');
        const button = page.locator(state === 'AUTH01' ? '#request-magic-link-button' : '#verify-magic-link-button');
        await expect(input).toHaveCSS('height', '56px');
        await expect(input).toHaveCSS('font-size', '16px');
        await expect(button).toHaveCSS('height', '56px');
        await reachable(button);
        if (state !== 'AUTH01') await reachable(page.locator('#auth-change-credential-email-button'));
        measurements.push({ width, height, state, ...await noOverflow(page, testInfo, `${width}-${state}`), card: await page.locator('#auth-panel').boundingBox() });
      }
    }
    await testInfo.attach('auth-v01-responsive-geometry.json', { body: Buffer.from(JSON.stringify(measurements, null, 2)), contentType: 'application/json' });
  });

  for (const width of [320, 390]) {
    test(`AUTH-V01 TC-09 ${width}x480 with 200% text keeps keyboard actions and tooltip reachable`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 480 });
      await baseRoutes(page);
      await page.route('**/users/auth/email/confirm', (route) => fulfillJson(route, {
        email: longEmail, auth_mode: 'password_registration', message: 'Создайте пароль.',
      }));
      await page.goto(tokenUrl());
      await expect(page.locator('#auth-title')).toHaveText('Создайте пароль');
      await fontReady(page);
      // Text-only 200% emulation: double computed text metrics, preserving the viewport.
      await page.evaluate(() => {
        const nodes = [...document.querySelectorAll('.auth-header, .auth-header *, #auth-panel, #auth-panel *, .app-footer, .app-footer *')];
        const metrics = nodes.map((node) => ({ node, font: parseFloat(getComputedStyle(node).fontSize), line: parseFloat(getComputedStyle(node).lineHeight) }));
        metrics.forEach(({ node, font, line }) => {
          if (font > 0) node.style.fontSize = `${font * 2}px`;
          if (Number.isFinite(line)) node.style.lineHeight = `${line * 2}px`;
        });
      });
      await noOverflow(page, testInfo, `${width}-text200`);
      const input = page.locator('#magic-token-input');
      await input.fill('Aa7!bC9@dE');
      await input.focus();
      await page.keyboard.press('Tab');
      await expect(page.locator('#auth-password-toggle-button')).toBeFocused();
      await page.keyboard.press('Tab');
      const trigger = page.locator('#auth-password-requirements-trigger');
      await expect(trigger).toBeFocused();
      const tooltip = page.locator('#auth-password-requirements-popover');
      // Focus opens it; Escape and Enter exercise explicit keyboard close/reopen.
      await expect(tooltip).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(tooltip).toBeHidden();
      await page.keyboard.press('Enter');
      await expect(tooltip).toBeVisible();
      await expect(trigger).toHaveAttribute('aria-expanded', 'true');
      await noOverflow(page);
      const box = await tooltip.boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width);
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height).toBeLessThanOrEqual(480);
      await page.keyboard.press('Escape');
      await expect(tooltip).toBeHidden();
      await page.keyboard.press('Tab');
      await expect(page.locator('#auth-password-generate-button')).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(page.locator('#verify-magic-link-button')).toBeFocused();
      await reachable(page.locator('#verify-magic-link-button'));
      await page.keyboard.press('Tab');
      await expect(page.locator('#auth-change-credential-email-button')).toBeFocused();
      await reachable(page.locator('#auth-change-credential-email-button'));
      await noOverflow(page);
    });
  }

  test('AUTH-V01 TC-13 restore, link checking, registration, waiting, expired link and reset share the auth shell', async ({ page }) => {
    await baseRoutes(page);
    let finishRestore;
    await page.route('**/users/session/restore', (route) => { finishRestore = () => fulfillJson(route, { authenticated: false }); });
    await page.goto(base);
    await shell(page, '#session-restore-panel');
    await expect(page.locator('#email-input')).toBeHidden();
    await finishRestore();
    await shell(page);
    await page.unroute('**/users/session/restore');

    let finishLink;
    await page.route('**/users/auth/email/confirm', (route) => { finishLink = () => fulfillJson(route, {
      email, auth_mode: 'password_registration', message: 'Создайте пароль.',
    }); });
    await page.goto(tokenUrl());
    await expect(page.locator('#auth-status')).toContainText('Подтверждаем ссылку');
    await shell(page);
    await finishLink();
    await expect(page.locator('#auth-title')).toHaveText('Создайте пароль');
    await shell(page);
    await page.unroute('**/users/auth/email/confirm');

    await page.goto(base);
    await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, {
      email: longEmail, auth_mode: 'verification_pending', retry_after_seconds: 60,
    }));
    await page.locator('#email-input').fill(longEmail);
    await page.locator('#request-magic-link-button').click();
    await expect(page.locator('#auth-email-sent')).toBeVisible();
    await shell(page);
    await noOverflow(page);

    await page.route('**/users/auth/password/reset/validate', (route) => fulfillJson(route, { detail: 'Срок действия ссылки истёк.' }, 400));
    await page.goto(tokenUrl('password_reset'));
    await expect(page.getByRole('heading', { name: 'Срок ссылки истёк' })).toBeVisible();
    await shell(page);
    await page.unroute('**/users/auth/password/reset/validate');
    await page.route('**/users/auth/password/reset/validate', (route) => fulfillJson(route, {
      email, auth_mode: 'password_reset', message: 'Задайте новый пароль.',
    }));
    await page.goto(tokenUrl('password_reset'));
    await expect(page.locator('#auth-title')).toHaveText('Создайте новый пароль');
    await shell(page);
    await page.route('**/users/session/restore', (route) => fulfillJson(route, { detail: 'synthetic unavailable' }, 503));
    await page.goto(base);
    await expect(page.locator('#session-restore-title')).toHaveText('Не удалось восстановить сессию');
    await shell(page, '#session-restore-panel');
    await page.reload();
    await shell(page, '#session-restore-panel');
  });

  for (const mode of ['registration', 'reset']) {
    test(`AUTH-V01 TC-14 ${mode} generates a strong password and confirms it in a separate local step`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width: 1440, height: 1024 });
      await baseRoutes(page);
      const isReset = mode === 'reset';
      const validationEndpoint = isReset ? '/users/auth/password/reset/validate' : '/users/auth/email/confirm';
      const submitEndpoint = isReset ? '/users/auth/password/reset' : '/users/auth/email/password-register';
      const writes = [];
      let validations = 0;
      await page.route('**/users/auth/**', (route) => {
        const pathname = new URL(route.request().url()).pathname;
        if (pathname === validationEndpoint) {
          validations += 1;
          return fulfillJson(route, { email, auth_mode: isReset ? 'password_reset' : 'password_registration' });
        }
        writes.push({ pathname, payload: route.request().postDataJSON() });
        return fulfillJson(route, { detail: 'Синтетический отказ TC-14' }, 503);
      });
      await page.goto(tokenUrl(isReset ? 'password_reset' : 'email_verification'));
      await expect(page.locator('#auth-title')).toHaveText(isReset ? 'Создайте новый пароль' : 'Создайте пароль');
      await fontReady(page);
      const input = page.locator('#magic-token-input');
      const button = page.locator('#verify-magic-link-button');
      const metrics = await geometry(page);
      await testInfo.attach(`auth-v01-${mode}-creation-geometry.json`, { body: Buffer.from(JSON.stringify(metrics, null, 2)), contentType: 'application/json' });
      expect(metrics.card.width).toBe(502);
      expect(metrics.card.height).toBe(547);
      expect(metrics.input.width).toBe(374);
      expect(metrics.input.height).toBe(49);
      await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 1 из 2');
      await expect(page.locator('#auth-password-confirm-input')).toHaveValue('');
      expect(validations).toBe(1);
      expect(writes).toEqual([]);

      await page.locator('#auth-password-generate-button').click();
      const generated = await input.inputValue();
      expect(generated).toHaveLength(10);
      for (const group of [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/]) expect(generated).toMatch(group);
      expect(generated).toMatch(/^[!-~]{10}$/);
      await expect(input).toHaveAttribute('type', 'text');
      await expect(page.locator('#auth-password-confirm-input')).toHaveValue('');
      await page.locator('#auth-password-toggle-button').click();
      await expect(input).toHaveAttribute('type', 'password');
      await expect(input).toHaveValue(generated);
      expect(writes).toEqual([]);

      await button.click();
      await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 2 из 2');
      await expect(page.locator('#auth-title')).toHaveText(isReset ? 'Подтвердите новый пароль' : 'Подтвердите пароль');
      await expect(input).toHaveValue('');
      await expect(input).toHaveAttribute('type', 'password');
      await expect(input).toBeFocused();
      await expect(page.locator('#auth-password-generate-button')).toBeHidden();
      await expect(page.locator('#auth-password-confirm-input')).toHaveValue('');
      expect(writes).toEqual([]);

      const mismatch = `${generated.slice(0, -1)}${generated.endsWith('X') ? 'Y' : 'X'}`;
      await input.fill(mismatch);
      await button.click();
      await expect(page.locator('#auth-error')).toHaveText('Пароли не совпадают. Попробуйте ещё раз.');
      await expect(page.locator('#auth-error')).toBeVisible();
      await expect(input).toHaveAttribute('aria-invalid', 'true');
      await expect(input).toBeFocused();
      await expect(input).toHaveValue(mismatch);
      expect(writes).toEqual([]);

      await input.fill(generated);
      await expect(input).not.toHaveAttribute('aria-invalid');
      await expect(page.locator('#auth-error')).toBeHidden();
      expect(writes).toEqual([]);
      await button.click();
      // The API boundary intentionally normalizes a mutating 503 instead of exposing detail.
      await expect(page.locator('#auth-error')).toHaveText('Сервис не смог выполнить операцию. Повторная отправка может быть небезопасна — сначала обновите состояние.');
      await expect(button).toBeEnabled();
      expect(writes).toHaveLength(1);
      expect(writes[0].pathname).toBe(submitEndpoint);
      expect(writes[0].payload).toMatchObject({ password: generated, password_confirm: generated });
      expect(writes[0].payload[isReset ? 'token' : 'verification_token']).toBe('auth-v01-local-only');
      if (!isReset) expect(writes[0].payload.email).toBe(email);
      expect(validations).toBe(1);
    });
  }

  test('AUTH-V01 TC-16 footer and normal canvas survive common panel → chat → auth transitions and reload', async ({ page }) => {
    await baseRoutes(page);
    await page.goto(base);
    await shell(page);
    // Same synthetic panel boundary fixture as REL-VERSION-01; no real account or chat request.
    const show = (panelId) => page.evaluate((id) => {
      document.querySelectorAll('.shell > .panel').forEach((panel) => panel.classList.toggle('hidden', panel.id !== id));
    }, panelId);
    await show('auth-complete-panel');
    await expect(page.locator('.auth-header')).toBeHidden();
    await expect(page.locator('.shell')).toHaveCSS('background-color', 'rgb(246, 249, 249)');
    await expect(page.locator('.app-footer')).toBeVisible();
    await expect(page.locator('.app-footer-release')).toBeVisible();
    await expect(page.locator('.app-footer-release')).toHaveText(`Версия ${appRelease}`);
    await expect(page.locator('[data-app-release-number]:visible')).toHaveCount(1);
    for (const panel of ['chat-panel', 'interview-panel', 'onboarding-panel']) {
      await show(panel);
      await expect(page.locator('.app-footer')).toBeHidden();
      await expect(page.locator('.app-footer')).toHaveAttribute('aria-hidden', 'true');
    }
    await show('auth-panel');
    await shell(page);
    await page.reload();
    await shell(page);
  });
}
