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
    assets/img/         Portrait, illustrations and favicon
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

## The portrait

`assets/img/joshua-sims.jpg` is currently a grey placeholder. Drop the real
photo in at that exact path and filename and the home page picks it up. It is
displayed at a 4:5 crop anchored near the top of the frame, so a portrait
around 1000 x 1250 or larger works well.

## Illustrations

The research-direction drawings and every diagram on the site are hand-authored
inline SVG in the HTML, styled by the `g-*` classes at the bottom of
`assets/css/site.css`. They read their colours from the theme tokens, so they
follow light and dark mode without a second set of values. There are no image
files behind them.

## A note on the stylesheet link

Pages link the CSS as `site.css?v=<number>`. That query string is only a
cache-buster: bump it after a visible CSS change if a browser stubbornly serves
the old file. Nothing depends on the value.
