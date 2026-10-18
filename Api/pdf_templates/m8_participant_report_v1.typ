#let data = json("report-data.json")
#let fonts = ("Inter", "Noto Sans")
#set document(title: data.title, author: "4K")
#set page(paper: "a4", margin: 18mm, numbering: "1")
#set text(font: fonts, size: 10pt, lang: "ru", fill: rgb("#222c30"))
#set par(leading: 0.7em, spacing: 0.8em)
#show heading: it => { set text(font: ("Manrope", ..fonts), fill: rgb("#222c30")); it }

= Ваши результаты
#text(fill: rgb("#526168"))[Индивидуальный отчёт · версия #data.report_revision_no]

Ниже — результаты по вашим ответам, их основания и ограничения. Этот отчёт не содержит рекомендаций, упражнений или плана развития.

== Главное из вашей оценки
#if data.descriptive.status == "ready" and data.descriptive.summary.len() > 0 [
  #for item in data.descriptive.summary [
    #item
  ]
] else if data.descriptive.status == "failed" [
  *Пояснение временно недоступно.* Фактический результат и ограничения доступны ниже.
] else if data.descriptive.status == "historical" [
  Показана сохранённая фактическая версия без прежних рекомендаций.
] else [
  *Пояснение готовится.* Фактический результат уже доступен ниже.
]

#if data.processing.status == "failed" [
  #block(fill: rgb("#fff4e5"), inset: 10pt, radius: 4pt)[
    *Обработка результата ограничена.* #data.processing.message
  ]
]

#if data.partial_result != none and data.partial_result.is_incomplete [
  #block(fill: rgb("#fff8e1"), inset: 10pt, radius: 4pt)[
    *Оценка завершена не полностью.* \
    Подтверждено #data.partial_result.progress.completed из #data.partial_result.progress.planned запланированных ситуаций.
    Показаны только подтверждённые результаты; непокрытые элементы не считаются неуспехом.
  ]
]

== Ваши результаты по 4К
#for competency in data.skills.map(item => item.competency).dedup() [
  === #competency
  #for skill in data.skills.filter(item => item.competency == competency) [
    #block(stroke: 0.5pt + rgb("#d5dfe2"), inset: 9pt, radius: 4pt, breakable: false)[
      *#skill.name* \
      #if skill.description != "" [#skill.description \
      ]
      #skill.outcome \
      *Балл:* #skill.score · *Полнота:* #skill.completeness \
      В этой версии оценки общий уровень навыка не присваивается.
    ]
  ]
]

== Что удалось оценить и где данных недостаточно
#table(
  columns: (1.2fr, 2fr, 1.2fr),
  inset: 6pt,
  stroke: 0.4pt + rgb("#cbd5e1"),
  fill: (x, y) => if y == 0 { rgb("#eef2f3") },
  table.header([*Область*], [*Разрез*], [*Покрытие*]),
  ..data.coverage.map(item => (
    [#if item.scope == "full_m2" [Полный состав методологии] else [План этой оценки]],
    [#item.name], [#item.ratio],
  )).flatten(),
)

#for item in data.limitations [
  - #item
]

#if data.reliability == "verified" [
  *Проверка механизма:* подтверждена в указанной области.
] else if data.reliability == "not_verified" [
  *Проверка механизма:* нормативная проверка ещё не подтверждена.
] else [
  *Проверка механизма:* сведения отсутствуют.
]

#if data.descriptive.status == "ready" and data.descriptive.claims.len() > 0 [
  == Почему сделан такой вывод
  #for claim in data.descriptive.claims [
    #if claim.kind == "quote" [
      #quote(block: true)[#claim.text]
    ] else [
      #claim.text
    ]
    #for limitation in claim.limitations [
      - #limitation
    ]
  ]
]
