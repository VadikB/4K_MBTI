# P3-A+P3-B: локальный маршрут визуального просмотра

Совместный code SHA `abce5f73cb452a6a71e9369e7a45d94533436a4e`:
`npx playwright test tests/browser/p3b-visual.spec.mjs --reporter=line` — PASS.
Шесть состояний × четыре ширины — 24 PASS; дополнительный `active-long`
при viewport 390 px и computed text 200% — PASS: documentWidth=390,
viewportWidth=390, offenders=[]. Первичное evidence:
`.test-stand/p3-b-visual/manifest.json` и `active-long-390-text200.png`.
Это технический Chromium subset; физические iOS/Android, native text zoom,
software keyboard и приёмка владельцем — NOT_RUN. Длинные подписи действий
при 200% занимают несколько строк; отсутствие горизонтального переполнения
не заменяет оценку их читаемости владельцем. Исторический P3-B FAIL
на SHA `43c42c2f` (543 px при viewport 390 px) сохранён ниже, не переименован.

## Исторический стенд P3-B до объединения

Сборка: `APP_RELEASE=2.0.87`, product/release commit `43c42c2f4b0b825007af97f844f2d3946e055687`,
base `023bf85ec796d212d29b33218d906a1ed2023941`. Это локальный
синтетический UI/runtime-стенд, не TEST-deploy и не полный путь создания/назначения
Cycle из AC18. Пользователь, Cycle, AS и диалог созданы только в памяти fixture;
рабочая БД, реальные данные, LLM и платная генерация не используются.

Из worktree `/Users/vadim_bogachev/Developer/4K/worktrees/ac18-p3-b-time-return`:

```sh
node scripts/p3b_visual_preview.mjs
```

На той же машине открыть `http://127.0.0.1:18769/p3b-visual`. Сервер слушает только
loopback, работает пока активна команда; остановить `Ctrl-C`. Ссылка `Сбросить`
очищает состояние Continue. Для автоматического повтора:

```sh
npx playwright test tests/browser/p3b-visual.spec.mjs --reporter=line
```

| State / URL-параметр | Data | Действие и фактическое состояние |
|---|---|---|
| `active-long` | `p3b-active-long`, план 8, позиция 1 | Длинная AS, серверный прогресс `1 из 8`, 70 мин.; без паузы. |
| `active-short` | `p3b-active-short`, план 5, позиция 2 | Короткая AS, прогресс `2 из 5`, 90 мин. |
| `pause` | `p3b-pause`, план 8, позиция 3 | Пауза, завершено `2 из 8`, 60 мин., явный Continue. |
| `return` | `p3b-return`, план 8, позиция 1 | Continue открывает ту же AS и сохранённый диалог; reload сохраняет историю. |
| `unknown` | `p3b-unknown`, план 8, позиция 1 | Остаток неизвестен, не `0`/безлимит; потеря ответа и неудачный readback не обещают успех, ключ команды переживает reload. |
| `recovered` | `p3b-recovered`, план 8, позиция 1 | Уже восстановленный диалог с сохранёнными turn. |

Первичное evidence: `.test-stand/p3-b-visual/manifest.json` и PNG рядом с ним.
Для каждого из шести состояний Chromium проверен на 1440, 768, 390 и 320 px:
24/24 PASS, включая отсутствие горизонтального переполнения при обычном тексте.
`active-long-390-text200.png` на прежнем SHA `43c42c2f` — отдельная проверка
удвоенных вычисленных размеров текста: **исторический FAIL**, ширина документа
543 px при viewport 390 px. За край выходили общий topbar и `textarea`;
совместный кандидат выше исправил это без изменения предметных правил.
Физические iOS Safari/Android Chrome и клавиатура — NOT_RUN. Эмуляция Chromium
не доказывает их поведения. Решение владельца: **не просмотрено**.

Ручной маршрут: открыть длинную и короткую AS; сравнить прогресс; открыть `pause`
и `return`, нажать Continue и перезагрузить; открыть `unknown`, нажать Continue,
убедиться в честном неизвестном исходе, перезагрузить и проверить сохранённый ключ
через автоматический тест. Тестовый стенд не требует создания аккаунта или SQL.
