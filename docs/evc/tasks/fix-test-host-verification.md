# Краткое описание задачи EVC: проверка SSH-узла test-среды

## Результат

GitHub Actions `deploy-test` устанавливает SSH-соединение с test-сервером,
проверяя его публичный ED25519 fingerprint без многострочного known-hosts secret.

## Область

- Included: настройка SSH в test deployment workflow и документация secrets.
- Excluded: код приложения, БД, pilot, deploy-скрипт и ключ авторизации.

## Ограничения и риски

- `StrictHostKeyChecking` остаётся включённым.
- Приватный ключ не выводится и остаётся GitHub secret.
- Изменение fingerprint сервера должно останавливать деплой.

## Критерии приёмки

- Workflow не читает `TEST_SSH_KNOWN_HOSTS`.
- Приватный ключ проверяется до SSH-подключения.
- Полученный ED25519 host key совпадает с зафиксированным fingerprint.
- При несовпадении fingerprint deployment завершается ошибкой.

## План проверки

- Разбор workflow как YAML.
- Shell-проверка команд fingerprint на текущем сервере.
- Стандартные проверки репозитория перед PR.
- Финальная проверка: GitHub Actions `deploy-test` после merge.

## Откат

Отмена коммита возвращает прежнюю передачу `TEST_SSH_KNOWN_HOSTS`.
