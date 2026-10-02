#let data = json("report-data.json")
#let fonts = ("Inter", "Noto Sans")
#set document(title: data.title, author: "Agent_4K")
#set page(paper: "a4", margin: 16mm, numbering: "1")
#set text(font: fonts, size: 9pt, lang: "ru")
#set par(leading: 0.65em, spacing: 0.7em)
#show heading: it => { set text(font: ("Manrope", ..fonts), fill: rgb("#191c1e")); it }

= #data.title
#text(fill: rgb("#64748b"))[
  Cycle: #data.cycle_id · Results revision: #data.results_revision_no · Report: #data.report_revision_no
]

== Результаты по навыкам
#table(
  columns: (2.2fr, 1fr, 1fr, 0.9fr),
  inset: 6pt,
  stroke: 0.4pt + rgb("#cbd5e1"),
  fill: (x, y) => if y == 0 { rgb("#eef2ff") },
  table.header([*Навык*], [*Исход*], [*Score*], [*Полнота*]),
  ..data.skills.map(skill => (
    [#skill.name], [#skill.outcome], [#skill.score], [#skill.completeness],
  )).flatten(),
)

== Покрытие
#table(
  columns: (1fr, 1.5fr, 1fr),
  inset: 6pt,
  stroke: 0.4pt + rgb("#cbd5e1"),
  fill: (x, y) => if y == 0 { rgb("#eef2ff") },
  table.header([*Контур*], [*Срез*], [*Покрытие*]),
  ..data.coverage.map(item => (
    [#item.scope], [#item.name], [#item.ratio],
  )).flatten(),
)

== Ограничения
#for item in data.limitations [
  - #item
]

*Reliability:* #data.reliability
