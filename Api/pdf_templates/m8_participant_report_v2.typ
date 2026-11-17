#let data = json("report-data.json")
#let fonts = ("Inter", "Noto Sans")
#set document(title: data.title, author: "4K")
#set page(paper: "a4", margin: 18mm, numbering: "1")
#set text(font: fonts, size: 10pt, lang: "ru", fill: rgb("#222c30"))
#set par(leading: 0.7em, spacing: 0.8em)
#show heading: it => { set text(font: ("Manrope", ..fonts)); it }

= Ваши результаты
#if data.program_name == none [Программа оценки не указана] else [#data.program_name] \
Дата прохождения: #if data.closed_at == none [не указана] else [#data.closed_at]
#if data.participant_name != none [Участник: #data.participant_name]

#if data.correction != none [
  #block(fill: rgb("#eaf4f5"), inset: 10pt, radius: 4pt)[
    *Отчёт исправлен* · #data.correction.created_at \
    Причина: #data.correction.reason
  ]
]

Ниже — подтверждённые результаты, объяснения и ограничения. Баллы по навыкам имеют шкалу от 0 до 3; отсутствие балла не означает ноль.

== Главное из вашей оценки
#if data.descriptive.status == "ready" and data.descriptive.summary.len() > 0 [
  #for item in data.descriptive.summary [#item \ ]
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

#if data.partial_result != none and (data.partial_result.is_incomplete or data.partial_result.limitation_reasons.len() > 0) [
  #block(fill: rgb("#fff8e1"), inset: 10pt, radius: 4pt)[
    *#data.partial_result.messages.title* \
    Подтверждено #data.partial_result.progress.completed из #data.partial_result.progress.planned запланированных ситуаций. \
    #for reason in data.partial_result.limitation_reasons [#reason.message \ ]
  ]
]

== Результаты по навыкам
#if data.skills.len() == 0 [
  Результаты по навыкам пока недоступны. Отсутствие балла не означает ноль.
]
#for index in range(data.radars.len()) [
  #let radar = data.radars.at(index)
  === #radar.name
  #if radar.axes.any(axis => axis.current != none) [
    #align(center)[#image("radar-" + str(index) + ".svg", width: 42%)]
    #text(size: 9pt, fill: rgb("#526168"))[Кольца: 1, 2, 3 из 3. Пустая ось — нет числового результата. Пунктирный маркер — частичный результат.]
    #for axis_index in range(radar.axes.len()) [
      #let axis = radar.axes.at(axis_index)
      #(axis_index + 1). #axis.name — #if axis.current == none [нет балла] else [#axis.current из 3 #if axis.partial [(частичный результат)]] \
    ]
  ] else [
    Числовых результатов пока нет. Отсутствие балла не означает ноль.
  ]
  #for skill in data.skills.filter(item => item.competency_id == radar.competency_id) [
    #block(stroke: 0.5pt + rgb("#d5dfe2"), inset: 9pt, radius: 4pt, breakable: false)[
      *#skill.name* \
      #if skill.description != "" [#skill.description \ ]
      #skill.outcome \
      *Балл:* #skill.score \
      #for reason in skill.reasons [#reason \ ]
      Общий уровень навыка в этой версии не присваивается.
    ]
  ]
]

== Ограничения
#for item in data.limitations [- #item]

#if data.descriptive.status == "ready" and data.descriptive.claims.len() > 0 [
  == Почему сделан такой вывод
  #for claim in data.descriptive.claims [
    #if claim.kind == "quote" [#quote(block: true)[#claim.text]] else [#claim.text]
    #for limitation in claim.limitations [- #limitation]
  ]
]
