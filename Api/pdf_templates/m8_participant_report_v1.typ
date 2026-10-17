#let data = json("report-data.json")
#let fonts = ("Inter", "Noto Sans")
#set document(title: data.title, author: "4K")
#set page(paper: "a4", margin: 18mm, numbering: "1")
#set text(font: fonts, size: 10pt, lang: "ru", fill: rgb("#222c30"))
#set par(leading: 0.7em, spacing: 0.8em)
#show heading: it => { set text(font: ("Manrope", ..fonts), fill: rgb("#222c30")); it }

= Результат оценки
#text(fill: rgb("#526168"))[Индивидуальный отчёт · версия #data.report_revision_no]

Ниже — результаты по вашим ответам, их основания и ограничения.

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

== Компетенции и навыки
#for competency in data.skills.map(item => item.competency).dedup() [
  === #competency
  #for skill in data.skills.filter(item => item.competency == competency) [
    #block(stroke: 0.5pt + rgb("#d5dfe2"), inset: 9pt, radius: 4pt, breakable: false)[
      *#skill.name* \
      #skill.outcome \
      *Балл:* #skill.score · *Полнота:* #skill.completeness \
      В этой версии оценки общий уровень навыка не присваивается.
    ]
  ]
]

== Покрытие и ограничения результата
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

#if data.recommendations.len() > 0 [
  == Что можно развивать
  #for recommendation in data.recommendations [
    === #recommendation.goal
    *Практика:* #recommendation.practice

    *Где попробовать:* #recommendation.application_context

    *Признак прогресса:* #recommendation.progress_signal

    #for basis in recommendation.at("basis_refs", default: ()) [
      *Основание:* #basis.manifestation
      #for fragment in basis.at("material_excerpts", default: ()) [
        #quote(block: true)[#fragment.quote]
      ]
    ]
    #for limitation in recommendation.limitations [
      - #limitation
    ]
  ]
]

#if data.recommendation_notices.len() > 0 [
  == Когда рекомендаций нет
  #for notice in data.recommendation_notices [
    - #notice.text
  ]
]
