# UX-R04-CLOSE — завершение входа и приветствия

Дата: 16.10.2026. Ветка: `codex/ux-r04-close`.
База: `main@39ffa2bdd43c002341a6630b905018d080f396ef`, версия 2.1.34.

## Результат и границы

Закрыты визуальные остатки R04: генератор пароля использует Onest 14/400,
создание/подтверждение нового пароля выровнено по принятому R01, экран проверки
почты получил 24/700/32, контурную email-иконку и текстовое действие изменения
email. Добавлен общий статический подвал без фиктивных ссылок; на мобильном он
остаётся в потоке и складывается вертикально.

Существующий повторный вход, auth-клиент, серверный допуск, journey и парольная
политика не переписывались. Настройки реальной почтовой инфраструктуры, URLs
юридических документов и физическая кросс-браузерная приёмка не входят в реализацию.

## Источники и решения

- `UX-R04_CLOSE_2026-10-16.txt`, rev 1.0,
  SHA-256 `1d9d46121a1664af416c64bf8277a6e787dfcebd4a0922fd2e8f5eadea67c3e3`.
- `UX-02_Authentication.docx`, rev 1.4,
  SHA-256 `0cdd52938c802da1aa0fa45437692fe5d92d1ddcbae52bc57870a027beb47d75`.
- `UX-R01_Login_Layout.docx`, rev 8,
  SHA-256 `72771139435efb088216c53c7949ddd6f74f2d1cbd17a155597933d5ba54bc9f`.
- `P4K_Auth_Review_2026-10-12.txt`, rev 8,
  SHA-256 `a3fd8bdbe988e2fe482a2613fa2e8c35db808ffca812d659c4ed0c8ef057e256`.
- `README.md`, `CONTRIBUTING.md`, EVC workflow и verification matrix; текущие
  auth/frontend/HTTP/PostgreSQL/browser tests.

Product Lead Дмитрий принял R01 12.10.2026. UX-R04-CLOSE явно разрешил подвал с
текущим годом и текстовыми названиями без URL; это более позднее адресное решение
для данного результата. Новых предметных правил, PM/LU-контрактов, схем или
публикуемых артефактов не добавлено. Стоп-условий для визуальной реализации нет.

## Изменённые файлы

- `web/index.html` — mail-state, cache key и общий правовой подвал.
- `web/styles/screens/auth.css` — финальные R01/R04 размеры, типографика,
  responsive footer и mobile-safe layout.
- `web/assets/icons/auth-email-outline.svg` — локальная контурная email-иконка.
- `tests/frontend/auth-ux.test.mjs`, `tests/browser/auth-r03.spec.mjs` — DOM,
  computed-style, desktop/mobile и tooltip regression.
- `tests/integration/test_r03_auth_full_flow_db.py` — реальный путь registration →
  reset → login, одноразовость токена и отсутствие новых Cycle/Session.
- `tests/integration/test_r03_auth_invitation_db.py` — граница срока и историческая
  consumed-запись в UTC и Europe/Moscow.

## Проверки

- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — 14 PASS.
- `npm run build:web` — PASS; bundle не изменился, поскольку изменены HTML/CSS и
  тесты, а не `web/js`.
- `git diff --check` — PASS.
- Адресная Chromium UI-проверка: 6 PASS; после исправления вертикального отступа
  повторная проверка exact metrics — 1 PASS.
- Полный `STAND_ADMIN_URL=<isolated pytest DB> npm run test:browser` — 32 PASS за
  8.2 минуты. Включает exact allowlist, tenant, cookie/session, поздний 401, две
  вкладки, journey, interruption и отсутствие подмены владельца.
- PostgreSQL/HTTP invitation, full auth и email admission — 27 PASS после
  восстановления локального Python entrypoint; расширенный full-flow — 1 PASS.
- PostgreSQL invitation boundary UTC/Europe-Moscow — 12 PASS.
- `npm run test:backend:http` — 55 PASS, 10 deselected.
- `npm run test:backend` — 411 PASS / 13 FAIL. FAIL воспроизводят известный baseline
  M6 (`INPUT_NOT_READY`, `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`) и не связаны с
  auth/UI diff R04; auth policy/invitation/journey tests в этом прогоне PASS.

## Критерии R04

- Визуальные размеры R01, mail state, footer, 360 px reflow и tooltip — PASS в
  локальном Chromium; длинный текст переносится, горизонтального overflow нет.
- Existing/new participant, exact allowlist, invitation tenant, cookie restore,
  revoked membership recheck, lost response, two tabs и late 401 — PASS.
- Регистрация, две последовательные установки пароля через register/reset,
  старый/новый пароль, одноразовый reset token и отсутствие запуска Cycle/Session — PASS.
- Invitation TTL около 72 часов, exact expiry (`410 Gone`), UTC/Europe-Moscow и
  сохранение consumed historical context — PASS.
- Реальная внешняя доставка письма — NOT_RUN: использован контролируемый sink;
  почтовая инфраструктура остаётся этапом 2.
- iOS Safari/Яндекс/Chrome, Android Chrome/Яндекс, Windows Chrome/Яндекс,
  macOS Safari/Chrome/Яндекс с физической клавиатурой/устройствами — NOT_RUN:
  доступен только локальный Chromium и viewport 320/360; это не заменяет матрицу.

## Риски и откат

- Config/schema/deploy: нет изменений. Секреты и реальные пользовательские данные
  не использовались; PostgreSQL имел `pytest` в имени, stand-базы disposable.
- Footer общий для всех экранов и находится после активной панели; у полноэкранных
  рабочих экранов он появляется ниже содержимого, не перекрывая composer/клавиатуру.
- Откат: вернуть HTML/CSS/SVG и тестовые изменения одним revert. Auth-данные и
  исторические invitation записи не требуют миграции или удаления.

## Следующий минимальный шаг

Локальный результат зафиксирован коммитом `HEAD` ветки `codex/ux-r04-close`;
точный неизменяемый SHA фиксируется Git после формирования отчёта. Далее: push, PR,
обязательный GitHub CI и review. После merge команда
продукта выполняет физическую browser/device matrix на test; только она закрывает
оставшийся NOT_RUN. Production activation и mail setup — отдельное решение.

## Открытые вопросы

Нет блокеров для PR. Физическая browser/device matrix и внешняя доставка письма
остаются обязательной последующей приёмкой владельца test-инфраструктуры.
