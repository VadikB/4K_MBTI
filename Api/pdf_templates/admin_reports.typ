#let data = json("report-data.json")

#let text-main = rgb("#191c1e")
#let text-body = rgb("#464554")
#let text-muted = rgb("#64748b")
#let accent = rgb("#4648d4")
#let accent-soft = rgb("#e1e0ff")
#let bg-soft = rgb("#f7f9fb")
#let panel-border = rgb("#e8e7ee")
#let control-bg = rgb("#f2f4f6")
#let success = rgb("#2da430")
#let warning = rgb("#ea580c")

#let heading-fonts = ("Manrope", "Inter", "Noto Sans")
#let body-fonts = ("Inter", "Noto Sans")

#set document(title: data.title, author: "Agent_4K")
#set page(
  paper: "a4",
  flipped: true,
  margin: (top: 12mm, bottom: 12mm, left: 14mm, right: 14mm),
  fill: bg-soft,
  numbering: "1",
)
#set text(font: body-fonts, size: 8.4pt, fill: text-body, lang: "ru", hyphenate: true)
#set par(leading: 0.58em, spacing: 0.5em)

#let label(body) = text(
  font: body-fonts,
  size: 7.4pt,
  weight: 700,
  fill: accent,
  hyphenate: false,
  tracking: 0.06em,
  upper(body),
)

#let card(body, inset: 13pt) = block(
  width: 100%,
  fill: white,
  stroke: 0.6pt + panel-border,
  radius: 6pt,
  inset: inset,
  body,
)

#let status-chip(status) = {
  let color = if status == "Завершено" { success } else if status == "В процессе" { warning } else { text-muted }
  box(
    fill: color.lighten(85%),
    radius: 3pt,
    inset: (x: 5pt, y: 2.2pt),
    text(size: 7.5pt, weight: 700, fill: color, status),
  )
}

#let table-columns = (1.35fr, 1.15fr, 0.65fr, 0.52fr, 0.52fr, 0.55fr)

#let header-cell(body) = text(size: 7.2pt, weight: 700, fill: text-muted, hyphenate: false, body)

#let reports-header() = grid(
  columns: table-columns,
  gutter: 0pt,
  fill: control-bg,
  stroke: 0.4pt + panel-border,
  inset: (x: 7pt, y: 6pt),
  header-cell[Сотрудник / ID],
  header-cell[Группа / роль],
  header-cell[Статус],
  align(center, header-cell[4K score]),
  align(center, header-cell[MBTI]),
  align(center, header-cell[Дата]),
)

#let report-row(item) = grid(
  columns: table-columns,
  gutter: 0pt,
  stroke: 0.4pt + panel-border,
  inset: (x: 7pt, y: 6.5pt),
  [
    #text(size: 8.5pt, weight: 700, fill: text-main, hyphenate: false)[#item.full_name]
    #linebreak()
    #text(size: 7pt, fill: text-muted)[ID #str(item.user_id)]
  ],
  [
    #text(size: 8pt, fill: text-main, hyphenate: false)[#item.group_name]
    #linebreak()
    #text(size: 7pt, fill: text-muted, hyphenate: false)[#item.role_name]
  ],
  status-chip(item.status),
  align(center, text(size: 9pt, weight: 800, fill: accent)[#item.score_label]),
  align(center, text(size: 8pt, fill: text-body)[#item.mbti_type]),
  align(center, text(size: 8pt, fill: text-body)[#item.date_label]),
)

#grid(
  columns: (1fr, 140pt),
  gutter: 18pt,
  align: (left, right),
  [
    #label("Админ-панель")
    #v(4pt)
    #text(font: heading-fonts, size: 24pt, weight: 800, fill: text-main, hyphenate: false)[#data.title]
    #v(5pt)
    #text(size: 10pt, fill: text-body)[#data.subtitle]
  ],
  [
    #card[
      #label("Всего отчетов")
      #v(5pt)
      #text(font: heading-fonts, size: 22pt, weight: 800, fill: accent)[#str(data.total_items)]
      #v(2pt)
      #text(size: 8pt, fill: text-muted)[Средний показатель: #data.summary_score_label]
    ]
  ],
)

#v(12pt)

#card(inset: 0pt)[
  #reports-header()
  #for item in data.items [
    #report-row(item)
  ]
]
