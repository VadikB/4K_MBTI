// AUTH-F01 uses only local synthetic API responses; it never authenticates a real user.
export function registerAuthF01Tests({ test, expect, baseRoutes, base, fulfillJson }) {
  const email = 'person@example.test';
  const password = 'Aa7!bC9@dE';
  const emailCases = [
    { name: 'empty', value: '', message: 'Введите рабочий email' },
    { name: 'invalid', value: 'invalid.example', message: 'Введите email в формате name@company.ru' },
  ];

  for (const invalid of emailCases) {
    test(`AUTH-F01 TC-10 ${invalid.name} email focuses the field without an API request`, async ({ page }) => {
      await baseRoutes(page);
      let requests = 0;
      await page.route('**/users/auth/**', (route) => {
        requests += 1;
        return fulfillJson(route, {}, 500);
      });
      await page.goto(base);
      const input = page.locator('#email-input');
      await input.fill(invalid.value);
      await page.locator('#request-magic-link-button').click();
      await expect(page.locator('#auth-error')).toHaveText(invalid.message);
      await expect(page.locator('#auth-error')).toBeVisible();
      await expect(input).toBeFocused();
      await expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(requests).toBe(0);
    });

    test(`AUTH-F01 TC-11 editing ${invalid.name} email clears its stale error and submit validates again`, async ({ page }) => {
      await baseRoutes(page);
      let requests = 0;
      await page.route('**/users/auth/**', (route) => {
        requests += 1;
        return fulfillJson(route, {}, 500);
      });
      await page.goto(base);
      const input = page.locator('#email-input');
      const error = page.locator('#auth-error');
      await input.fill(invalid.value);
      await page.locator('#request-magic-link-button').click();
      await expect(error).toHaveText(invalid.message);
      await expect(input).toHaveAttribute('aria-invalid', 'true');

      // Even an unfinished edit makes the previous validation result stale.
      await input.pressSequentially('x');
      await expect(error).toBeHidden();
      await expect(error).toHaveText('');
      await expect(input).not.toHaveAttribute('aria-invalid');
      expect(requests).toBe(0);

      await input.press('Enter');
      await expect(error).toHaveText('Введите email в формате name@company.ru');
      await expect(error).toBeVisible();
      await expect(input).toBeFocused();
      await expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(requests).toBe(0);

      await input.fill(email);
      await expect(error).toBeHidden();
      await expect(input).not.toHaveAttribute('aria-invalid');
      await expect(page.locator('#auth-token-form')).toBeHidden();
      expect(requests).toBe(0);
    });
  }

  test('AUTH-F01 TC-11 editing email preserves an unrelated server error', async ({ page }) => {
    await baseRoutes(page);
    let requests = 0;
    await page.route('**/users/auth/email/request-link', (route) => {
      requests += 1;
      return fulfillJson(route, { detail: 'Синтетическая ошибка сервера AUTH-F01' }, 503);
    });
    await page.goto(base);
    const input = page.locator('#email-input');
    const error = page.locator('#auth-error');
    await input.fill(email);
    await page.locator('#request-magic-link-button').click();
    await expect(error).toBeVisible();
    await expect(input).toBeEnabled();
    const message = await error.textContent();
    expect(message).toBeTruthy();
    await input.fill('another.person@example.test');
    await expect(error).toHaveText(message);
    await expect(error).toBeVisible();
    await expect(input).not.toHaveAttribute('aria-invalid');
    expect(requests).toBe(1);
  });

  for (const failure of ['401', 'network abort']) {
    test(`AUTH-F01 TC-12 ${failure} restores Continue and permits retry without double submit`, async ({ page }) => {
      await baseRoutes(page);
      await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, {
        email, auth_mode: 'password', message: 'Введите пароль.',
      }));
      let requests = 0;
      let finish;
      const message = failure === '401'
        ? 'Синтетический отказ входа AUTH-F01'
        : 'Не удалось связаться с сервером. Проверьте соединение и повторите попытку.';
      await page.route('**/users/auth/email/password-login', (route) => {
        requests += 1;
        expect(route.request().postDataJSON()).toMatchObject({ email, password });
        finish = () => failure === '401'
          ? fulfillJson(route, { detail: message }, 401)
          : route.abort('failed');
      });
      await page.goto(base);
      await page.locator('#email-input').fill(email);
      await page.locator('#request-magic-link-button').click();
      const input = page.locator('#magic-token-input');
      const button = page.locator('#verify-magic-link-button');
      const controls = [input, page.locator('#auth-password-toggle-button'),
        page.locator('#auth-change-credential-email-button'), page.locator('#forgot-password-credential-button')];
      await expect(button).toHaveText('Продолжить');
      await input.fill(password);

      for (let attempt = 1; attempt <= 2; attempt += 1) {
        await button.click();
        await expect.poll(() => requests).toBe(attempt);
        await expect(button).toHaveText('Входим...');
        await expect(button).toBeDisabled();
        await expect(button).toHaveAttribute('aria-busy', 'true');
        for (const control of controls) await expect(control).toBeDisabled();

        // Repeated form submissions exercise the in-flight guard even when the CTA is disabled.
        await page.locator('#auth-token-form').evaluate((form) => {
          for (let index = 0; index < 2; index += 1) {
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          }
        });
        expect(requests).toBe(attempt);
        await finish();
        await expect(page.locator('#auth-error')).toHaveText(message);
        await expect(page.locator('#auth-error')).toBeVisible();
        await expect(button).toBeEnabled();
        await expect(button).not.toHaveAttribute('aria-busy');
        await expect(button).toHaveText('Продолжить');
        for (const control of controls) await expect(control).toBeEnabled();
        await expect(input).toHaveValue(password);
        await expect(page.locator('#auth-token-form')).toBeVisible();
        expect(requests).toBe(attempt);
      }
    });
  }
}
