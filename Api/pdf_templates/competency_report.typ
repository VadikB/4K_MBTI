#let data = json("report-data.json")
#let recommendations = data.at("recommendations", default: ())
#let strengths = data.at("strengths", default: ())
#let growth-areas = data.at("growth_areas", default: recommendations)
#let quotes = data.at("quotes", default: ())

#let text-main = rgb("#191c1e")
#let text-body = rgb("#464554")
#let text-muted = rgb("#64748b")
#let text-soft = rgb("#94a3b8")
#let accent = rgb("#4648d4")
#let accent-bright = rgb("#6063ee")
#let accent-soft = rgb("#e1e0ff")
#let accent-surface = rgb("#eef2ff")
#let bg-soft = rgb("#f7f9fb")
#let panel-border = rgb("#e8e7ee")
#let line = rgb("#e2e8f0")
#let control-bg = rgb("#f2f4f6")
#let warning = rgb("#b55d00")
#let warning-soft = rgb("#fff7ed")

#let heading-fonts = ("Manrope", "Inter", "Noto Sans")
#let body-fonts = ("Inter", "Noto Sans")

#set document(title: data.title, author: "Agent_4K")
#set page(
  paper: "a4",
  margin: (top: 14mm, bottom: 14mm, left: 16mm, right: 16mm),
  fill: bg-soft,
  numbering: "1",
)
#set text(font: body-fonts, size: 9.5pt, fill: text-body, lang: "ru", hyphenate: true)
#set par(leading: 0.62em, spacing: 0.72em, justify: false)

#show heading: it => {
  set text(font: heading-fonts, fill: text-main)
  it
}

#let pct(value) = str(value) + "%"

#let label(body) = text(
  font: body-fonts,
  size: 7.6pt,
  weight: 700,
  fill: accent,
  hyphenate: false,
  tracking: 0.06em,
  upper(body),
)

#let card(body, fill: white, inset: 14pt, stroke: panel-border) = block(
  width: 100%,
  fill: fill,
  stroke: 0.6pt + stroke,
  radius: 6pt,
  inset: inset,
  body,
)

#let section-title(body) = text(font: heading-fonts, size: 15pt, weight: 800, fill: text-main, hyphenate: false, body)

#let chip(body, fill: accent-soft, color: text-main) = box(
  fill: fill,
  radius: 2pt,
  inset: (x: 5pt, y: 2.5pt),
  text(size: 7.8pt, weight: 700, fill: color, hyphenate: false, body),
)

#let stat-card(title, value, note) = card[
  #label(title)
  #v(5pt)
  #text(font: heading-fonts, size: 24pt, weight: 800, fill: accent)[#value]
  #v(2pt)
  #text(size: 8.3pt, fill: text-muted)[#note]
]

#let progress(value) = {
  let clamped = if value < 0 { 0 } else if value > 100 { 100 } else { value }
  box(width: 70pt, height: 5pt)[
    #place(left + top, rect(width: 70pt, height: 5pt, radius: 2.5pt, fill: line))
    #place(left + top, rect(width: clamped / 100 * 70pt, height: 5pt, radius: 2.5pt, fill: accent))
  ]
}

#let competency-pill(item) = card(inset: 10pt, fill: accent-surface, stroke: rgb("#dedcff"))[
  #text(size: 8.2pt, weight: 700, fill: text-main, hyphenate: false)[#item.name]
  #v(4pt)
  #text(font: heading-fonts, size: 17pt, weight: 800, fill: accent-bright)[#pct(item.avg_percent)]
  #v(5pt)
  #progress(item.avg_percent)
  #v(4pt)
  #text(size: 7.5pt, fill: text-muted)[#item.interpretation]
]

#let insight-list(items, fallback, color: text-body) = {
  let source = if items.len() > 0 { items } else { (fallback,) }
  for item in source [
    #block(fill: rgb("#fbfcfe"), stroke: 0.4pt + panel-border, radius: 5pt, inset: 8pt)[
      #text(size: 8.2pt, weight: 600, fill: color)[#item]
    ]
    #v(4pt)
  ]
}

#let quote-card(value) = block(fill: white, stroke: 0.5pt + panel-border, radius: 5pt, inset: 9pt)[
  #text(size: 16pt, weight: 800, fill: accent)[“]
  #text(size: 8.4pt, fill: text-body)[#value]
]

#let skill-header() = grid(
  columns: (1.15fr, 0.72fr, 0.42fr, 1.45fr),
  gutter: 0pt,
  fill: control-bg,
  stroke: 0.4pt + panel-border,
  inset: 7pt,
  text(size: 7.5pt, weight: 700, fill: text-muted, hyphenate: false)[Навык],
  align(center, text(size: 7.5pt, weight: 700, fill: text-muted, hyphenate: false)[Уровень]),
  align(center, text(size: 7.5pt, weight: 700, fill: text-muted, hyphenate: false)[Прогресс]),
  text(size: 7.5pt, weight: 700, fill: text-muted, hyphenate: false)[Комментарий],
)

#let skill-row(skill) = grid(
  columns: (1.15fr, 0.72fr, 0.42fr, 1.45fr),
  gutter: 0pt,
  stroke: 0.4pt + panel-border,
  inset: 7pt,
  text(size: 8.2pt, weight: 600, fill: text-main, hyphenate: false)[#skill.name],
  align(center, chip(skill.level, fill: accent-soft)),
  align(center, text(size: 8.2pt, weight: 700, fill: text-main)[#pct(skill.percent)]),
  text(size: 7.8pt, fill: text-body)[#skill.rationale],
)

#grid(
  columns: (1fr, 155pt),
  gutter: 16pt,
  align: (left, right),
  [
    #label("Профиль компетенций")
    #v(4pt)
    #text(font: heading-fonts, size: 25pt, weight: 800, fill: text-main, hyphenate: false)[Ваш профиль компетенций]
    #v(5pt)
    #text(size: 10.5pt, fill: text-body)[#data.subtitle]
  ],
  [
    #stat-card("Интегральный показатель", pct(data.overall_score), "по завершенной сессии")
  ],
)

#v(12pt)

#grid(
  columns: (0.92fr, 1.5fr),
  gutter: 12pt,
  [
    #card[
      #label("Пользователь")
      #v(7pt)
      #text(font: heading-fonts, size: 13.5pt, weight: 800, fill: text-main, hyphenate: false)[#data.user.full_name]
      #v(4pt)
      #text(size: 8.5pt, fill: text-muted)[Должность: #data.user.job_description]
      #linebreak()
      #text(size: 8.5pt, fill: text-muted)[Телефон: #data.user.phone]
    ]
    #v(8pt)
    #card(fill: warning, stroke: warning)[
      #text(size: 8pt, weight: 700, fill: white)[Рекомендации по росту]
      #v(6pt)
      #for recommendation in recommendations [
        #block(fill: rgb("#c46b14"), stroke: 0.4pt + rgb("#d18434"), radius: 4pt, inset: 7pt)[
          #text(size: 8pt, weight: 600, fill: white)[#recommendation]
        ]
        #v(4pt)
      ]
    ]
  ],
  [
    #card[
      #label("Сводка")
      #v(7pt)
      #grid(
        columns: (1fr, 1fr),
        gutter: 8pt,
        ..data.competencies.map(competency-pill),
      )
    ]
    #v(8pt)
    #card(fill: rgb("#fbfcfe"), stroke: panel-border, inset: 16pt)[
      #chip("AI insights", fill: rgb("#ebeafd"), color: accent)
      #v(8pt)
      #text(font: heading-fonts, size: 14pt, weight: 800, fill: text-main, hyphenate: false)[#data.insight.title]
      #v(5pt)
      #text(size: 9.3pt, fill: text-body)[#data.insight.text]
      #v(8pt)
      #text(size: 8pt, weight: 700, fill: text-main)[Основание вывода]
      #v(4pt)
      #for basis in data.basis_items [
        #text(size: 7.8pt, fill: text-muted)[• #basis]
        #linebreak()
      ]
    ]
  ],
)

#v(10pt)

#pagebreak()

#grid(
  columns: (1fr, 1fr),
  gutter: 12pt,
  [
    #card[
      #section-title("Сильные стороны")
      #v(7pt)
      #insight-list(strengths, "Сильные стороны будут определены после появления более устойчивых сигналов по сессии.")
    ]
  ],
  [
    #card[
      #section-title("Зоны роста")
      #v(7pt)
      #insight-list(growth-areas, "Зоны роста будут определены после накопления результатов.")
    ]
  ],
)

#if quotes.len() > 0 [
  #v(10pt)
  #card[
    #section-title("Цитаты из оценки")
    #v(3pt)
    #text(size: 9pt, fill: text-muted)[Фрагменты, повлиявшие на результат]
    #v(7pt)
    #grid(
      columns: (1fr, 1fr, 1fr),
      gutter: 8pt,
      ..quotes.map(quote-card),
    )
  ]
]

#pagebreak()

#text(font: heading-fonts, size: 20pt, weight: 800, fill: text-main, hyphenate: false)[Детализация по навыкам]
#text(size: 9.2pt, fill: text-muted)[Результаты сгруппированы по компетенциям. Прогресс рассчитан на основе весов уровней оценки.]

#for competency in data.competencies [
  #v(10pt)
  #text(font: heading-fonts, size: 15pt, weight: 800, fill: text-main, hyphenate: false)[#competency.name]
  #skill-header()
  #for skill in competency.skills [
    #skill-row(skill)
  ]
]
