# EVC task brief: test SSH host verification

## Outcome

GitHub Actions `deploy-test` устанавливает SSH-соединение с test-сервером,
проверяя его публичный ED25519 fingerprint без многострочного known-hosts secret.

## Scope

- Included: настройка SSH в test deployment workflow и документация secrets.
- Excluded: код приложения, БД, pilot, deploy-скрипт и ключ авторизации.

## Constraints and risks

- `StrictHostKeyChecking` остаётся включённым.
- Приватный ключ не выводится и остаётся GitHub secret.
- Изменение fingerprint сервера должно останавливать деплой.

## Acceptance criteria

- Workflow не читает `TEST_SSH_KNOWN_HOSTS`.
- Приватный ключ проверяется до SSH-подключения.
- Полученный ED25519 host key совпадает с зафиксированным fingerprint.
- При несовпадении fingerprint deployment завершается ошибкой.

## Verification plan

- Разбор workflow как YAML.
- Shell-проверка команд fingerprint на текущем сервере.
- Стандартные проверки репозитория перед PR.
- Финальная проверка: GitHub Actions `deploy-test` после merge.

## Rollback

Revert коммита возвращает прежнюю передачу `TEST_SSH_KNOWN_HOSTS`.
