# Матрица правил, данных и проверок

Пути JSON ниже относительно `tests/fixtures/m6_gc/v1`. PASS структуры не означает
семантический PASS. Тесты runtime из предыдущего шага не объявляются прогонами GC.

| Проверка / источник | Конкретные данные и проверка | PM/LU, контракт; задача | Факт / ограничение |
| --- | --- | --- | --- |
| TECH-A01; M6.1.3, M6.6.6 | technical/interim и final: один AS, одинаковые Turns, разные границы событий; normalize восстанавливает снимок и версии | PM-04/LU-04.5 → PM-05/LU-05.1–2, C-45; 3 | PASS структуры, без IA |
| TECH-A02; M6.1.3, M7.5.6 | checksum/schema/cycle/session/as/unknown_target/unavailable_material/wrong_m2: реальные повреждённые входы с ожидаемыми исключениями | PM-05/LU-05.1, C-45; 3 | PASS указанных отказов. DialogueID в C-45 не самостоятельное поле, выводится из AS; иной Dialogue внутри корректно переподписанного envelope не обнаруживается по отдельному owner-полю. Требуется проверка происхождения в M5, не выдуманный контракт fixture |
| TECH-A03; M6.2.1–2 | quote/author/future_turn/cross_as_fragment; ссылки на чужой/отсутствующий или более поздний Turn/material/event отклоняются | PM-05/LU-05.1, C-45; 3 | PASS. `before_disclosure` сохраняет раннее сопоставление без ссылок на будущие D1/D3; происхождение самостоятельно названных чисел остаётся предметным ограничением для эксперта |
| TECH-A04; M6.5.1, M6.6.3 | empty без пользовательских Turns, empty_missing_ref; никаких фиктивных Fragment/BS | PM-05/LU-05.2; 3 | PASS структуры; пустота не назначает IA |
| TECH-A05; M6.3.2, M7.3.3 | операции replay/conflict/history в operations.json; интеграционные тесты real_c45_empty_bundle_readback_and_replay, tamper_and_conflicting_key, new_mechanism_keeps_bundle_identity_and_history | PM-05/LU-05.2/05.5; 3 | Код тестов содержит реальные запросы/изменения, прежний прогон PASS; повтор в задаче 2 NOT_RUN, PostgreSQL остановлен |
| TECH-A06; M6.9.5–6 | operations.json: invalid JSON, timeout, lease expiry/crash до save; failure_retry_expired_lease_and_late_attempt, restart_recovery_selects_queued_request | PM-05/LU-05.5; 3 | invalid JSON/lease/recovery проверены ранее. Timeout и настоящий процессный crash NOT_RUN; истечение lease — симуляция, не crash-тест |
| TECH-A07; M7.2.3/2.5 | operations.json: замена текущего profile, Case, M2, prompt после enqueue; processing_snapshot_survives_source_change | PM-04/LU-04.5, PM-05/LU-05.5; 3 | profile + запрет чтения текущих prompt/M2 проверены ранее; физическая замена Case NOT_RUN. Fixture hashes защищают пакет, но не заменяют runtime readback |
| TECH-A08; M6.9.2, M8.7.2 | operations.json: PostgreSQL nonempty readback; all_m6_endpoints_require_admin (GET/POST), repeat_uses_saved_request_without_current_package | PM-05/LU-05.6, PM-07/LU-07.2; 3/9 | HTTP тесты повторены; DB ранее PASS. Политика раскрытия будущим PM-06/07 BLOCKED контрактом C-56/C-67 |
| CAND-A01; M6.4 + M2 G/H/M/N | independent: сравнение трёх объектов K4.I05; реконструкция двух позиций K1.I13 | PM-05/LU-05.1–2; 3 | Вход/ссылки PASS, смысл NOT_REVIEWED |
| CAND-A02; M6.2.2 | character и before_disclosure: одинаковые слова с иным автором/доступностью | PM-05/LU-05.1; 3 | Структура PASS; контраст авторства проверен, смысл NOT_REVIEWED |
| CAND-A03; M6.3.1–2 | composite: две связанные реконструкции, ordered_turn_ids; dummy_composite отклоняется | PM-05/LU-05.2; 3 | PASS связей; единый смысловой вывод NOT_REVIEWED |
| CAND-A04; M6.5.1/6.3 | no_opportunity, insufficient, nonperformance, technical_loss — четыре разные записи | PM-05/LU-05.2–3, PM-04/LU-04.7; 3/4/7 | Пустые цепочки PASS. Два capture-входа BLOCKED по C-45; исходы IA отложены. Экспертное расхождение — карточка, не ещё один ответ пользователя |
| CAND-A05; M6.5.1–2, M6.6.4 | contradiction/retain: раннее среднее и исправление, сохранение позиции после D3 | PM-05/LU-05.2; 3 | Порядок/сохранение PASS структуры, интерпретация NOT_REVIEWED |
| CAND-A06; M6.9.1 | independent/paraphrase: реальные разные реплики, одинаковые автор/доступность | PM-05/LU-05.5; 3 | Различие входов PASS; семантическая эквивалентность NOT_REVIEWED |
| EXT-01–08 | Конкретные будущие данные и ожидания в extensions.md | PM-04–07; задачи 4–9 | Проектные проверки NOT_RUN, отдельные блокирующие контракты в каждой строке |
| SC-M6-M8-01 | scenario.md + frozen independent interim/final, ветви capture | C-45/C-54/C-46/C-56/C-67; 3–9 | Только файловый участок C-45/M6-A проверен; сквозной NOT_RUN |

Каждый PASS ограничен названной проверкой. Решение о допуске M6-A по методологии
остаётся открытым до независимой экспертизы и реальных прогонов. Числа тестов и
кандидатов не суммируются как «число GC».
