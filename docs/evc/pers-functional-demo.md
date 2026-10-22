# Демонстрация functional personalization v0.2

1. Показать `verification-report.json`: 9 Case, 55 targets, число персонажей
   `1,0,3,1,1,3,0,2,1`; отдельно показать `runtime_enabled=false`.
2. В изолированной test/pytest-БД импортировать package дважды: первый
   импорт `created=true`, второй `created=false`.
3. Создать тестовую организацию, подтвердить анкету и профиль
   `specialist_expert`; зафиксировать profile id/version/checksum.
4. Запустить реальную генерацию CASE02 для подбора, CASE03 для некоммерческих
   вкладов и CASE05 для ресурсов деятельности; показать AI operation ids,
   provider/model, prompt refs, AS versions и tester protocol. Без PASS AS не предъявлять.
5. Выполнить interaction, паузу и повторный вход. Сверить те же AS id/version,
   materials, delivered events и progress; повтор request id не должен создавать событие.
6. Завершить один Cycle через M6/M7/M8 и сверить цепочку ID в выгрузке
   методологу. Неполный Cycle показать как неполный.

Шаги 3–6 считаются выполненными только по фактической трассе; тестовые fixtures
и авторский PASS их не заменяют.
