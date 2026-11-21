# P4K-SUP-UX-05 · Визуальная сверка

Сцены из приложенного архива v1.6 открыты с оригинальными параметрами
`screen=problems&view=screen`, `screen=problem&issue=next&view=screen`,
`screen=handoff&issue=next&view=screen`. Продукт на 2.1.58, база
`dea4d565`. Имена, номера и содержимое операции синтетические.

| Экран | 1440 px | 390 px | 320 px |
| --- | --- | --- | --- |
| Очередь | [Эталон](reference-problems-1440.png) / [Продукт](product-problems-1440.png) | [Эталон](reference-problems-390.png) / [Продукт](product-problems-390.png) | [Эталон](reference-problems-320.png) / [Продукт](product-problems-320.png) |
| Карточка отказа | [Эталон](reference-problem-1440.png) / [Продукт](product-problem-1440.png) | [Эталон](reference-problem-390.png) / [Продукт](product-problem-390.png) | [Эталон](reference-problem-320.png) / [Продукт](product-problem-320.png) |
| Передача после копирования | [Эталон](reference-handoff-1440.png) / [Продукт](product-handoff-1440.png) | [Эталон](reference-handoff-390.png) / [Продукт](product-handoff-390.png) | [Эталон](reference-handoff-320.png) / [Продукт](product-handoff-320.png) |
| Потеря чтения | [Продукт](product-unknown-1440.png) | [Продукт](product-unknown-390.png) | [Продукт](product-unknown-320.png) |
| Подтверждённый допуск | [Продукт](product-confirmed-1440.png) | [Продукт](product-confirmed-390.png) | [Продукт](product-confirmed-320.png) |
| Администратор организации | [Продукт](product-administrator-1440.png) | [Продукт](product-administrator-390.png) | [Продукт](product-administrator-320.png) |
| Участник оценки | [Продукт](product-participant-1440.png) | [Продукт](product-participant-390.png) | [Продукт](product-participant-320.png) |

На трёх ширинах измерена ширина документа и проверены отсутствие
горизонтального переполнения, шрифт Onest и цвет заголовка `#222c30`.
Карточки расположены в две колонки на 1440 px и в одну на мобильных.
Проверены клавиатурный вход в карточку, возврат фокуса после потери чтения,
переход к пакету и копирование по Enter. После потери чтения прежний факт
и время остались на экране рядом с действием проверки.

Шапка UX-01 компактнее эталона, а активная вкладка подчёркнута бирюзовым. Очередь показывает
только поддержанный тип сбоя и номер организации. Участник и администратор
используют один номер P4K. Карточка отображает фактическое время чтения и
безопасный класс отказа. В пакете есть ссылка на организацию. История
передачи, сохранение черновика и внешний номер задачи отсутствуют до
подключения серверного источника. Внутренний код причины виден через закрытую диагностику.

Отдельные ролевые эталоны ответили HTTP 401. Для этих двух экранов приведены
снимки реального UI на синтетическом HTTP, парная сверка ожидает доступа.
[Эталон администратора](https://p4k-admin-ux-20261119-v3.bvv-fructus.chatgpt.site/?screen=incident) ·
[Эталон участника](https://p4k-assessment-ux-20261119.bvv-fructus.chatgpt.site/?screen=assessment-next-failed)
