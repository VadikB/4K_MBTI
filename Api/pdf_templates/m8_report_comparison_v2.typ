#let data = json("report-data.json")
#let fonts = ("Inter", "Noto Sans")
#set document(title: data.title, author: "4K")
#set page(paper: "a4", margin: 18mm, numbering: "1")
#set text(font: fonts, size: 10pt, lang: "ru", fill: rgb("#222c30"))
#set par(leading: 0.7em, spacing: 0.8em)

= Сравнение оценок 4К
Предыдущее прохождение: #if data.previous.program_name == none [Оценка 4К] else [#data.previous.program_name] · #data.previous.closed_at \
Текущее прохождение: #if data.current.program_name == none [Оценка 4К] else [#data.current.program_name] · #data.current.closed_at

Числовая разность показана только там, где подтверждена сопоставимость двух сохранённых результатов. Она не означает процент роста или доказанное развитие навыка.

#if data.comparable.len() > 0 [
  == Сопоставимые навыки
  #align(center)[#image("radar-0.svg", width: 52%)]
  #text(size: 9pt, fill: rgb("#526168"))[Кольца: 1, 2, 3 из 3. Бирюзовая линия — сейчас; фиолетовая — ранее.]
  #for index in range(data.comparable.len()) [
    #let item = data.comparable.at(index)
    #(index + 1). #item.skill_name: ранее #item.previous из 3, сейчас #item.current из 3. \
  ]
  #table(
    columns: (2fr, 1fr, 1fr, 1fr),
    inset: 6pt,
    stroke: 0.4pt + rgb("#d6e2e5"),
    table.header([*Навык*], [*Ранее*], [*Сейчас*], [*Разность*]),
    ..data.comparable.map(item => (
      [#item.skill_name], [#item.previous], [#item.current], [#item.difference],
    )).flatten(),
  )
]

#if data.separate.len() > 0 [
  == Раздельные показатели
  #for item in data.separate [
    #block(stroke: 0.5pt + rgb("#d6e2e5"), inset: 9pt, radius: 4pt)[
      *#item.skill_name* \
      Ранее: #if item.previous == none [нет результата] else [#item.previous из 3] \
      Сейчас: #if item.current == none [нет результата] else [#item.current из 3] \
      #item.reason_text
    ]
  ]
]
