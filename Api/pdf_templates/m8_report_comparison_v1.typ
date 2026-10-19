#let data = json("report-data.json")
#let fonts = ("Inter", "Noto Sans")
#set document(title: data.title, author: "4K")
#set page(paper: "a4", margin: 18mm, numbering: "1")
#set text(font: fonts, size: 10pt, lang: "ru", fill: rgb("#222c30"))
#set par(leading: 0.7em, spacing: 0.8em)

= Сравнение оценок 4К
Предыдущая оценка: #data.previous.closed_at \
Текущая оценка: #data.current.closed_at

Числовая разница показана только там, где сервер подтвердил сопоставимость двух сохранённых результатов.

#if data.comparable.len() > 0 [
  == Сопоставимые навыки
  #table(
    columns: (2fr, 1fr, 1fr, 1fr),
    inset: 6pt,
    stroke: 0.4pt + rgb("#d6e2e5"),
    table.header([*Навык*], [*Предыдущая*], [*Текущая*], [*Разница*]),
    ..data.comparable.map(item => (
      [#item.skill_name], [#item.previous], [#item.current], [#item.difference],
    )).flatten(),
  )
]

#if data.separate.len() > 0 [
  == Независимые срезы
  #for item in data.separate [
    #block(stroke: 0.5pt + rgb("#d6e2e5"), inset: 9pt, radius: 4pt)[
      *#item.skill_name* \
      Предыдущая: #if item.previous == none [нет результата] else [#item.previous] \
      Текущая: #if item.current == none [нет результата] else [#item.current] \
      #item.reason_text
    ]
  ]
]
