# joshazerty.github.io

Personal research site for Joshua M. Sims, served by GitHub Pages at
<https://joshazerty.github.io>.

Plain static HTML and CSS. No build step, no framework, no dependencies, no
tracking. Edit a file, commit, push, and the site updates.

## Layout

    index.html            Home: intro, research strands, selected papers, recent news
    research.html         Project write-ups
    publications.html     Full publication and conference list
    software.html         Public code
    teaching.html         Courses, supervision, outreach
    cv.html               Web CV
    assets/css/site.css   All styling, including design tokens at the top
    assets/fonts/         Self-hosted Archivo and JetBrains Mono (latin subsets)
    assets/img/           Figures and favicon
    assets/files/         CV PDF

## Editing

Colours, spacing and type scale live in the `:root` block at the top of
`assets/css/site.css`, with the dark-mode overrides directly below it. Change a
token there and it applies everywhere.

To add a publication, copy an `<article class="pub">` block in
`publications.html` and edit it. To add a news item, copy a `<li class="row">`
block in `index.html`.

## Local preview

    python3 -m http.server 8000

Then open <http://localhost:8000>.
