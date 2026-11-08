# CODEX-WORKFLOW-02 — STATE

- Base: `origin/main@65a62aca6b5f3fb870826a7f41977a4fd0f3b590`.
- Branch/worktree: `codex/codex-workflow-02` /
  `/Users/vadim_bogachev/Developer/4K/worktrees/codex-workflow-02`.
- Полномочия: [карточка](../codex-workflow-02.md#полномочия-этапа), Decision ID
  `CODEX-WORKFLOW-02-AUTH`.
- Завершено: package integrity, разведка main, изоляция, официальный readback
  auto-review, draft правил/реестра/карточки.
- Candidate: `c08dd49f` (`Add Codex decision recovery workflow`).
- Завершено дополнительно: `git diff --cached --check` PASS; все адресные источники
  реестра существуют.
- Активный шаг: контрольные сессии A/B.
- Следующий шаг: восстановить штатный способ запуска новой сессии либо получить
  прямой запрос владельца на два отдельных desktop-чата; затем выполнить A/B.
- Проверки: package SHA PASS; auto-review worktree escalation PASS, manual=0,
  auto-review=1, denied=0; local candidate diff PASS. AC06–AC07 `BLOCKED`:
  `/usr/local/bin/codex` завершается `ENOENT` на отсутствующем darwin-x64 binary.
- Блокеры: две новые сессии, human review/CI/merge; client model/effort безопасному
  readback недоступны (`UNKNOWN`).
- Ограничения: без PATH/AUTH/AC18, БД, писем, product LLM, deploy/version bump/
  предметной публикации; чужая root-ветка и untracked files не изменяются.
