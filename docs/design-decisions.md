# Design decisions

Why this project is built the way it is, including the alternatives that were
considered and rejected. Split out of `README.md`, which covers what the
repository contains and how to run it; the findings themselves live on the
site, one page per study.

These are engineering and presentation decisions. The analytical choices
(what counts as a comparable day, why permutation tests are the inference of
record, why every null carries a minimum detectable effect) are argued on the
study pages and in `ROADMAP.md`.

## Contents

- [Data source: aWATTar](#data-source-awattar)
- [The cost model is deliberately honest about savings](#the-cost-model-is-deliberately-honest-about-savings)
- [Freshness: a daily GitHub Actions job, not a live browser fetch](#freshness-a-daily-github-actions-job-not-a-live-browser-fetch)
- [A static site on GitHub Pages, no backend](#a-static-site-on-github-pages-no-backend)
- [Shared page furniture: page-nav.css and page-nav.js](#shared-page-furniture-page-navcss-and-page-navjs)
- [One stylesheet, and a design that reports its own limits](#one-stylesheet-and-a-design-that-reports-its-own-limits)
- [Files as the interface, no database](#files-as-the-interface-no-database)
- [Reproducibility: a per-machine virtual environment](#reproducibility-a-per-machine-virtual-environment)
- [Units: convert wholesale EUR/MWh to ct/kWh](#units-convert-wholesale-eurmwh-to-ctkwh)
- [A synthetic fallback so the scripts always run](#a-synthetic-fallback-so-the-scripts-always-run)
- [What a "weather-comparable day" means (matching.py)](#what-a-weather-comparable-day-means-matchingpy)

## Data source: aWATTar

The prices come from the aWATTar API. aWATTar is a German dynamic-tariff
provider whose published hourly price is the EPEX SPOT day-ahead price passed
through directly, which is exactly the wholesale market price this project is
about. It is free, needs no API key, and returns clean JSON.

Two alternatives were considered. ENTSO-E's Transparency Platform is the
canonical, pan-European source and carries more than price (load, generation
mix), but it requires registering for an API token, which adds friction for the
first runnable step and for anyone cloning the repo. energy-charts.info from
Fraunhofer is free and token-free and adds generation mix, which is useful for
the residual-load concept. aWATTar was chosen for milestone 1 because zero setup
keeps momentum, and because using an actual retail provider's feed ties the
abstract market price to a product a real household buys. ENTSO-E or
energy-charts are the natural upgrade if the project later needs the generation
mix.

## The cost model is deliberately honest about savings

A naive model would compare the flat rate against the raw wholesale price and
report enormous savings. That is wrong. A real dynamic-tariff bill is the
wholesale price plus a fixed adder made up of grid fees, levies, tax, and
supplier margin, and that adder is identical in every hour. Shifting
consumption to a cheap hour only moves the wholesale part of the bill, not the
adder.

The model encodes this as `price(hour) = wholesale(hour) + FIXED_ADDER`. The
consequence is that modelled savings are meaningful but bounded, not unlimited.
This is the single most important modelling choice in the project, because it is
the difference between a credible analysis and a misleading one.

## Freshness: a daily GitHub Actions job, not a live browser fetch

The page needs current prices, and there were three ways to get them.

A live fetch from the browser on each visit would always be current and needs no
backend, but it depends on the data provider allowing cross-origin (CORS)
requests, which is not guaranteed and would break the page if the provider
changed its headers.

A static snapshot committed once is the simplest option but goes stale the day
after you commit it.

A scheduled GitHub Actions workflow re-runs the fetch daily and commits the new
`results.json`, which triggers a Pages redeploy. This was chosen because it is
robust regardless of CORS, keeps the page a pure static site, and demonstrates a
small CI/CD automation, which is a relevant signal for the kind of work this
project is a portfolio piece for. The cost is more moving parts, which is an
acceptable trade for a piece meant to be shown.

## A static site on GitHub Pages, no backend

The site is five small pages that read committed JSON files in the browser:
`index.html` (the findings one-pager), `tariff.html` (the daily demo, charts
via Chart.js from a CDN), `worldcup.html` (the event study), `intraday.html`
(day-ahead versus real time), and `ladder.html` (the value-of-complexity
study). There is no build step, no framework, and no server to run or pay for.
GitHub Pages serves the repository directly. This keeps the whole thing free to
host, trivial to reason about, and forkable by anyone.

## Shared page furniture: page-nav.css and page-nav.js

The section menu and the back-to-top button live in one CSS file and one JS
file that pages link, instead of being copied into each page's inline `<style>`
and `<script>`. The rule this follows: content belongs to its page, behaviour
that must be identical everywhere does not. The visual system moved out for the
same reason (see "One stylesheet, and a design that reports its own limits").

A page opts in with three lines: the stylesheet link, `<script src="page-nav.js"
defer>`, and an empty `<nav id="toc">` placeholder marking where the menu sits
in the flow on narrow screens. On wide screens the menu is fixed beside the
text column, so the placeholder's position only matters below 1320px, where the
menu becomes a collapsible block instead. That breakpoint is set by geometry:
860px of text plus a 12.5rem menu and a 1.5rem gap on each side needs 1308px.
It read 1180px until a screenshot at 1280px showed the menu clipped off the
left edge of the window, which is what any width between the two did. A page
without the placeholder gets neither feature, which is how `index.html` and
`tariff.html` opt out today.

The menu is built from every `section[id] > h2`, so it cannot drift from the
page: add a section with an id and an entry appears, reword a heading and the
label follows. Sections without an id are skipped, since there is no anchor to
link to. Explicit ids were chosen over slugs derived from heading text, which
would silently break saved links whenever a heading is reworded. Pages that
reveal a section only after its data loads call `window.syncPageNav()` once
rendered, so the entry appears with the section.

The colour contract is one variable: each page defines `--accent`, and the
shared stylesheet uses it for the active entry, so every page keeps its own
palette.

This was extracted at the third page, not the first. Two copies were cheaper to
read than an indirection; the third copy, plus pages still to come, flipped it.

## One stylesheet, and a design that reports its own limits

Every page used to carry its own copy of the same tokens and components: body
measure, `.card`, `.note`, `figcaption`, tables, footer. Five copies had already
drifted (one page's accent, another's warm grey, three different table rules),
so the visual system moved into `site.css`. Pages keep an inline `<style>` for
their DATA colours only, because those are shared with the matplotlib figures
and belong to the study rather than to the chrome.

This did not shrink the CSS. The 106 duplicated inline lines became 17 inline
plus 317 in `site.css`, about 228 lines more. The extraction removed the
duplication, and then the file spent the space on things no page had before: a
type scale, visible keyboard focus, the bound bar, reduced-motion handling, and
tables that scroll instead of pushing the page sideways. The win is one place to
change and no drift, not fewer lines.

The direction is called "bounded null", and it comes from what this project
actually produces. Most of the findings here are nulls with a stated minimum
detectable effect, and the standard visual grammar for a result page, a big
coloured number, is wrong for that: it makes "no effect" look like either a
triumph or a failure. So the chrome is deliberately monochrome, and colour is
spent in exactly one place, when a measured effect clears its own bound.

That grammar is a component, `bound.js`. It draws a caliper scale: the jaws are
the smallest effect the study could have detected, the dot is what it measured,
and a dot resting inside the jaws is the finding. It reads its numbers from the
committed JSONs and derives the word "null" or "effect" from the dot's position,
so the label cannot disagree with the data. It appears on `index.html` beside
the World Cup finding and on `worldcup.html` in the verdict box.

Typography follows the same idea: IBM Plex Sans for prose, IBM Plex Mono for
every number, unit, label and caption. Mono is not decoration here, it marks
measured or machine-derived text and gives tabular figures on pages built out
of `ct/kWh` values. `chart-theme.js` pushes the same fonts and greys into
Chart.js so figures match the page instead of carrying library defaults.

## Files as the interface, no database

Every script's contract is a file: fetchers write CSVs, analyses read CSVs and
write JSONs, the pages read JSONs. A database was considered and rejected, for
reasons of scale and of fit.

Scale: the whole project moves 24 to 96 rows per day. A database at that volume
is pure operational overhead: a server or file to manage, credentials, one more
thing a cloner must set up before anything runs.

Fit: the deployment target is a static host, which can serve files but cannot
run a database. And git already provides what a database would be bought for.
The daily workflow commits the refreshed `results.json`, so the repository's
history IS the time series, versioned, diffable, and free. Intermediate state
is inspectable with a text editor, which matters in a project whose point is
that the reasoning can be audited.

The threshold where this flips is worth stating: multi-zone data (the
cross-country study in the backlog), years of 15-minute records, or concurrent
writers would justify an embedded analytical store (SQLite or DuckDB), still
not a database server. Until then, files win on every axis that matters here.

## Reproducibility: a per-machine virtual environment

Anyone should be able to clone the repo and run it. Reproducibility here rests on
`requirements.txt`, the README steps, and `setup.sh`, which creates a local
`.venv`. The virtual environment is never committed, because it contains
operating-system-specific binaries that are meaningless on another machine, and
it is listed in `.gitignore`. Each user, and the GitHub Actions runner, builds
its own environment from `requirements.txt`.

Dependencies are pinned with version floors (`>=`) rather than exact pins. Floors
keep the repo installable over time without breaking on a yanked patch release,
which suits a small learning project. A production system would pin exact
versions and use a lockfile.

The `.vscode/settings.json` file is committed but optional. It only points
VS Code at the local `.venv` so the editor picks the right interpreter. It has no
effect on running the scripts or on the GitHub Actions job, and users of other
editors can ignore it.

## Units: convert wholesale EUR/MWh to ct/kWh

The market quotes prices in EUR/MWh. Household bills are in ct/kWh. The code
converts once (`EUR/MWh / 10 = ct/kWh`) and works in ct/kWh everywhere after
that, so every number on the page is in the unit a person actually recognises
from their bill.

## A synthetic fallback so the scripts always run

If `prices.csv` is missing, `cost_model.py` generates a plausible synthetic day
instead of failing. This keeps the model runnable offline and testable in CI
without a network call, and makes the first-run experience forgiving. The
synthetic day is clearly a fallback, and any committed `results.json` is replaced
by real data on the first successful fetch.

## What a "weather-comparable day" means (matching.py)

Both event studies rest on one definition, kept in a single module so it cannot
drift between them. `matching.py` picks, for each event day, the k most
comparable non-event days: daily temperature mean and max, a solar proxy
(radiation where available, cloud cover otherwise) and wind, all z-scored,
with controls required to share the day type (weekday / Saturday /
Sunday-or-holiday) and to fall within a bounded number of calendar days so a
seasonal gap cannot open up. The exact pairings chosen, with distances, are
published on the [World Cup page](https://adrianogelato.github.io/energy-market-predictability/worldcup.html) so the matching can be
inspected rather than trusted.
