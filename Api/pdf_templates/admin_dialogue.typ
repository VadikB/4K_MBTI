#let data = json("report-data.json")

#let text-main = rgb("#191c1e")
#let text-body = rgb("#464554")
#let text-muted = rgb("#64748b")
#let accent = rgb("#4648d4")
#let accent-soft = rgb("#e1e0ff")
#let bg-soft = rgb("#f7f9fb")
#let panel-border = rgb("#e8e7ee")
#let control-bg = rgb("#f2f4f6")
#let user-fill = rgb("#6063ee")
#let assistant-fill = rgb("#ffffff")

#let heading-fonts = ("Manrope", "Inter", "Noto Sans")
#let body-fonts = ("Inter", "Noto Sans")

#set document(title: data.title, author: "Agent_4K")
#set page(
  paper: "a4",
  margin: (top: 14mm, bottom: 14mm, left: 16mm, right: 16mm),
  fill: bg-soft,
  numbering: "1",
)
#set text(font: body-fonts, size: 9.2pt, fill: text-body, lang: "ru", hyphenate: true)
#set par(leading: 0.6em, spacing: 0.65em)

#let label(body) = text(
  font: body-fonts,
  size: 7.5pt,
  weight: 700,
  fill: accent,
  hyphenate: false,
  tracking: 0.06em,
  upper(body),
)

#let card(body, fill: white, inset: 14pt) = block(
  width: 100%,
  fill: fill,
  stroke: 0.6pt + panel-border,
  radius: 6pt,
  inset: inset,
  body,
)

#let lines(value) = {
  for line in str(value).split("\n") [
    #line
    #linebreak()
  ]
}

#let message-card(message) = {
  let is-user = message.role == "user"
  block(
    width: 100%,
    fill: if is-user { user-fill } else { assistant-fill },
    stroke: if is-user { user-fill } else { 0.6pt + panel-border },
    radius: 6pt,
    inset: 10pt,
  )[
    #text(
      size: 7.8pt,
      weight: 800,
      fill: if is-user { white } else { accent },
      hyphenate: false,
    )[#message.role_label]
    #v(4pt)
    #text(size: 8.7pt, fill: if is-user { white } else { text-body })[
      #lines(message.message_text)
    ]
  ]
}

#label("Админ-панель")
#v(4pt)
#text(font: heading-fonts, size: 23pt, weight: 800, fill: text-main, hyphenate: false)[#data.title]
#v(4pt)
#text(size: 9.5pt, fill: text-muted, hyphenate: false)[#data.full_name • #data.role_name • Сессия #str(data.session_id)]

#v(12pt)

#for case_item in data.case_items [
  #card[
    #label("Кейс " + str(case_item.case_number))
    #v(5pt)
    #text(font: heading-fonts, size: 15pt, weight: 800, fill: text-main, hyphenate: false)[#case_item.case_title]

    #if case_item.personalized_context != "" [
      #v(9pt)
      #text(size: 8pt, weight: 800, fill: text-muted, hyphenate: false)[Вводные данные]
      #v(3pt)
      #text(size: 8.8pt, fill: text-body)[#lines(case_item.personalized_context)]
    ]

    #if case_item.personalized_task != "" [
      #v(8pt)
      #text(size: 8pt, weight: 800, fill: text-muted, hyphenate: false)[Что нужно сделать]
      #v(3pt)
      #text(size: 8.8pt, fill: text-body)[#lines(case_item.personalized_task)]
    ]

    #v(10pt)
    #text(size: 8pt, weight: 800, fill: text-main, hyphenate: false)[Диалог]
    #v(5pt)
    #if case_item.dialogue.len() > 0 {
      for message in case_item.dialogue [
        #message-card(message)
        #v(5pt)
      ]
    } else [
      #block(fill: control-bg, radius: 5pt, inset: 9pt)[Диалог по кейсу не сохранен.]
    ]
  ]
  #v(10pt)
]
