# Ограниченное исправление dev-зависимостей PR #245

17.11.2026. Владелец прямо разрешил «отдельное ограниченное исправление
dev-зависимостей, необходимое для выпуска PR #245»: проверить все цепочки,
сохранить проверки неиспользуемого кода/зависимостей, подтвердить совместимость
локально и обязательным CI. Большой откат вслепую и ослабление npm audit запрещены.
Прежнее разрешение на merge/штатный TEST deploy после успешных проверок сохраняется.

## Диагностика и варианты

Первый CI head `c8adcc6`:
[frontend](https://github.com/VadikB/4K_MBTI/actions/runs/44145600998/job/134259751906)
остановлен штатным `npm audit --audit-level=high` на
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
Полный CI отдельно выявил три прежних browser-ожидания старой оболочки/inline
сравнения/радара; backend, integration и runtime 4/4 прошли. Эти результаты
не выдаются за успешный CI нового head.

Все пути к исходному `picomatch@4.0.4`:

1. root → Knip 6.15.0 → picomatch.
2. root → Knip → tinyglobby 0.2.17 → picomatch.
3. root → Knip → fdir 6.5.0 → optional peer picomatch.
4. root → Knip → tinyglobby → fdir → optional peer picomatch.

Проверенные варианты:

- Последний upstream picomatch 4.0.7: advisory по-прежнему включает его;
  bounded воспроизведение `+(*a)` / 80 `a` + `!` реально зависает (убит через 1 s).
- Knip 6.45.1: npm metadata требует picomatch ^4.0.7; обычное обновление не лечит.
- Предложенный npm откат Knip 3.13.2 не применялся: помимо большого изменения
  инструмента, metadata содержит micromatch 4.0.5 → picomatch ^2.3.1, также
  попадающий в advisory. Это не подтверждённое безопасное исправление.
- Выбран точный npm override `picomatch: npm:@ryotsu/picomatch@4.0.7-a`
  для всех цепочек, включая optional peer. Сам Knip 6.15.0, команда `lint:dead`
  и `knip.json` сохранены. Новых runtime-зависимостей/импортов в приложение нет.

## Происхождение и совместимость выбранного пакета

[Исходники fork](https://github.com/ryotsu-kankichi/secured-picomatch/tree/3ab5a7627d480259e3d9ca67fbc14c125d374f0e),
commit `3ab5a7627d480259e3d9ca67fbc14c125d374f0e`, npm 4.0.7-a.
Это сторонний fork, не официальный upstream-релиз. Его версия и integrity
закреплены в lock. Все 10 файлов npm-архива совпали с указанным Git commit.
`npm audit signatures`: 26 verified registry signatures, 15 verified attestations
в изолированном графе Knip; проверка завершилась успешно. MIT license сохранена.
У пакета нет runtime-зависимостей или install/preinstall/postinstall scripts.

Diff к upstream 4.0.7 полностью просмотрен: executable-изменения только
`lib/parse.js` и `lib/constants.js` (bounded repeated extglob, экранирование POSIX
punctuation, согласование globstar/переносов строк и bracket negation).
Документированные отличия: captures могут измениться; сложные небезопасные
single-branch extglobs трактуются буквально. Knip не отключает safeguard
`maxExtglobRecursion`; конфигурация проекта использует обычные `web/js/**/*.js`.

Локальное подтверждение:

- Upstream 4.0.7 на собственном наборе: 1983 PASS.
- Fork на собственном наборе: 2004 PASS, включая bounded CVE-регрессии.
- Неизменённый upstream-набор на fork: 1981 PASS, 2 FAIL. Оба FAIL сравнивают
  буквальную строку regex POSIX punctuation с прежним ошибочным экранированием;
  поведенческой регрессии в них нет. Эти FAIL сохранены и не названы PASS.
  Отдельный проектный тест проверяет реальное сопоставление backslash/буквы
  с `[[:punct:]]`, наряду с glob/scan/isMatch.
- Контрольное воспроизведение CVE на исходнике: TIMEOUT_KILLED после 1 s;
  на установленном fork: `false`, exit 0 за ~0.07 s.
- Knip JSON до/после замены на реальном checkout идентичен. Exit 1 в обоих
  случаях — ранее существующие предупреждения: неиспользуемые exports и
  browser-only absolute imports; они не скрывались и не исправлялись попутно.
- Новый обязательный frontend-тест создаёт временный проект и подтверждает,
  что Knip находит неиспользуемые файл, export и объявленную зависимость.
  Другой тест проверяет 42 CVE случая в дочернем процессе с timeout 5 s.
- `npm ci --ignore-scripts`: PASS; неизменённый
  `npm audit --audit-level=high`: PASS, high=0/critical=0. Три прежних moderate
  по minimatch остаются; порог и CI workflow не изменялись.
- `node --test tests/frontend/*.test.mjs`: 407 PASS; lint/build PASS;
  `web/dist` побайтно совпадает с принятым релизным кандидатом c8adcc6.
- Шесть browser-сценариев FIX-02/прежнего заголовка/RAD01/QA19-04: 6 PASS,
  13.8 s, workers=1/retries=0/30 s per test/10 min global. Повторный canonical
  `ready:prepare -- --candidate 2.1.29`: PASS, свежая база по-прежнему 71a9c535.

Проверен также альтернативный Bun: lock мигрирован из точного npm lock,
`bun install --frozen-lockfile --ignore-scripts` PASS, `bun why picomatch`
подтверждает тот же fork во всех четырёх путях. Это устраняет старый picomatch
из обоих lockfile, без произвольного обновления npm-графа.

Логи/metadata/JSON сравнения и SHA-256 — `evidence/deps/`. Первые неуспешные
CI и старые browser-ожидания сохранены. Три ожидания обновлены к принятой
оболочке POSTW02, самостоятельному сравнению с автозагрузкой пары и адаптивной
геометрии графика; проверки чисел/пропусков/пары/PDF/читаемости сохранены.
Перед merge необходим новый полный обязательный CI точного head.

Возврат к upstream — после выхода реального исправления, отдельным проверенным
изменением override/обоих lockfile и повтором security/Knip/CI. Удалять override
до исправления нельзя: это вернёт уязвимую библиотеку. Откат выпуска — штатный
revert PR; правила аудита при этом сохраняются.
