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

## Regenerating the CV PDF

The PDF at `assets/files/CV_Joshua_Sims.pdf` is rendered from
`build/cv-print.html`, so it stays consistent with `cv.html`. Edit the print
source, then:

    ./build/make-cv-pdf.sh

It drives headless Chrome and writes straight over the PDF in `assets/files`.
Update `cv.html` to match when you change one of them.

## Going live

The repo is not yet on GitHub. To publish:

    gh repo create joshazerty.github.io --public --source=. --push
    gh api -X POST repos/joshazerty/joshazerty.github.io/pages \
      -f 'source[branch]=main' -f 'source[path]=/'

The site then serves at https://joshazerty.github.io within a minute or two.
