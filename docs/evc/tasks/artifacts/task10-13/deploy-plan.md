# План конфигурации и отката Task-10-13

Публикация этой задачей не выполняется. Для будущего test rollout владелец должен
сохранить snapshot каталога, configuration, M4/AS и operation; установить
`DEEPSEEK_MODEL=deepseek-flash` и штатный endpoint; выполнить safe preflight без
вывода ключа; затем отдельно разрешить capped run по `future-run-manifest.json`.

Откат: вернуть приложение на предыдущий принятый commit и предыдущую test-конфигурацию.
Начатые операции продолжают использовать сохранённый operation snapshot; исторические
catalog/configuration/provider snapshots не переписываются. Общая SQL и `.env` этой
задачей не изменялись.
