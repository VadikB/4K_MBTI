# Статическая проверка пакета M5

Запуск: `m5-static-15d6d89dc1731b5b`.

Пакет: draft / WORKING. Runtime и M6: NOT_RUN. Записей в БД этот этап не создаёт.

- **PASS — source_counts**: {"case_types": 20, "cases": 20, "test_situations": 40, "candidate_observability": 80, "qa_specs": 160}
- **PASS — m2_m3_references**: Проверены CT, роли, Skill/Component и заполненные IndicatorID
- **NOT_RUN — k2_resolution**: Открыто строк: 14; кандидаты сохранены без автоматического назначения
- **NOT_RUN — runtime_artifacts**: Файловый этап; БД, персонализация и взаимодействие не запускались

Исходные синтетические AS и протоколы являются проектными материалами, а не результатами исполнения.
