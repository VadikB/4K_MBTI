#let data = json("report-data.json")
#set document(title: data.title, author: "4К Ассистент")
#set page(paper: "a4", margin: 18mm, numbering: "1")
#set text(font: ("Inter", "Noto Sans"), size: 10pt, lang: "ru", fill: rgb("#222c30"))
#set par(leading: 0.7em, spacing: 0.8em)

= Сравнение оценок
Предыдущая оценка: #if data.previous.program_name == none [Оценка 4К] else [#data.previous.program_name] · #data.previous.closed_at \
Текущая оценка: #if data.current.program_name == none [Оценка 4К] else [#data.current.program_name] · #data.current.closed_at

Разность расчётных показателей не доказывает развитие навыка и не означает процент роста. Шкала 0–3. Площадь фигуры не является общим баллом 4К. Пропуски не заменяются нулями.

#for (key, name) in (("previous", "Предыдущая оценка"), ("current", "Текущая оценка")) [
  #for limitation in data.at(key).at("limitations", default: ()) [#name: #limitation \ ]
]

#if data.radars.len() > 0 [
  #align(center)[#image("radar-0.svg", width: 52%)]
  #text(size: 9pt, fill: rgb("#64748b"))[Текущая серия — бирюзовая; предыдущая — серый пунктир и квадраты. Незакрашенные маркеры — частичные показатели. Номера осей соответствуют списку ниже. Несопоставимые оси оставлены открытыми.]
]

#let side(item, key, value) = {
  let result = item.at(key, default: none)
  [*#value* #if value != "—" [из 3] \
  #if result == none [Полнота результата не сохранена.] else [
    #result.label
    #if result.completeness == none and value != "—" [\ Сведения о полноте отдельно не сохранены.]
    #for reason in result.reasons [\ #reason.at("message", default: "Причина ограничения требует уточнения.")]
    #for limitation in result.limitations [\ #limitation]
  ]]
}

#for (index, item) in data.rows.enumerate() [
  #block(breakable: false, stroke: 0.5pt + rgb("#cbd5e1"), inset: 10pt, radius: 8pt)[
    == #(index + 1). #item.skill_name
    #grid(columns: (1fr, 1fr), gutter: 12pt,
      [*Предыдущая оценка* \ #side(item, "previous_result", item.previous_text)],
      [*Текущая оценка* \ #side(item, "current_result", item.current_text)],
    )
    #if item.comparability.status == "allowed" [
      *Разность: #item.difference_text*
    ] else [Разность не выводится: #item.reason_text]
  ]
]
