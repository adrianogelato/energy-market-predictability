# Energy market predictability: forecasting the German power market, and measuring where forecasts fail

Can you predict tomorrow's cheapest electricity hours, what is that prediction
worth in euros, and can a scheduled mega-event (the 2026 World Cup) move the
German power market? Real day-ahead prices, real ENTSO-E load data, explicit
baselines, and honest statistics, published as a static page that refreshes
itself daily.

**About this project.** I built this during my job search, as a portfolio
piece for product management / product ownership and project management roles
in the energy market domain. The write-up follows the conventions of a
portfolio item: findings first, every design decision argued, the working
process visible (`ROADMAP.md` holds the hypothesis ledger and backlog). The
substance is the point, not the packaging: real market data, a reproducible
pipeline, and statistics that are allowed to say "no effect".

## Findings at a glance

**Smart timing is worth real money, and the algorithm barely matters.** Over a
full backtested year (353 days), shifting a daily 11 kWh EV charge into the
three cheapest hours saves about €210/yr versus charging anytime, against a
€225/yr perfect-foresight ceiling. (The summer-only window alone says €303/yr;
peak solar spreads inflate it.) Across a six-rung ladder of forecasters, from a
28-day lookup table up to gradient boosting, the lookup table wins the whole
year outright. Paired sign-flip tests put a number on the gap: four of the five
models are significantly *worse* than the lookup table (linear +0.215 ct/kWh,
p=0.001; persistence +0.207, p=0.009; richer linear +0.198, p=0.001; gradient
boosting +0.131, p=0.022), and k-nearest-days only ties it (+0.020, p=0.613).
All of them were fed perfect weather. Weather models pay off in winter alone,
and there by roughly €1 per season for the household.
**Product implication: a smart-charging feature on this market needs
automation and UX, not ML.**
([ladder](#the-value-of-complexity-ladder-milestone-10),
[forecaster](#the-cheapest-hours-forecaster-milestone-5),
[value](#the-forecasts-money-value-milestone-8))

**Day-ahead is a fair price for the household, but a poor proxy for real time.**
Against a full year of the German real-time price (reBAP), the day-ahead price a
dynamic-tariff household is billed carries a near-zero systematic gap (median
reBAP-minus-day-ahead spread +0.04 ct/kWh; the largest hour-of-day bias is
−0.92 ct/kWh, in the 19:00 evening ramp). But real time is 1.9x as volatile as
day-ahead (2.2x in winter, 1.6x in summer), only 0.54 correlated with it, and
the three cheapest day-ahead hours are all still cheapest at real time on just
12.6% of days. **Product implication: no consumer-facing intraday product,
because the household gap is zero; the real-time value is variance, capturable
only by whoever holds the balancing position, so it is a business-to-business
aggregation play worth about €122/yr of flexibility per household-equivalent,
not a household saving.** That €122 is an annual total and is earned unevenly:
the median day is worth 1.73 ct/kWh, and the top 5% of days carry 32% of the
year.
([details](#day-ahead-versus-real-time-how-good-is-the-markets-own-forecast-r9))

**The World Cup did not detectably move the German market.** Final verdict on
the complete tournament window (11 June to 19 July, 35 match days, seasonal
controls enforced): prices during match hours +0.60 ct/kWh vs
weather-comparable days (t=0.75), +0.83 under a within-day contrast that nets
out seasonal drift, both consistent with no effect. Load forecast error: every
subset, the once-marginal overnight one included, is consistent with chance
(overnight subset permutation p=0.92, family-wise p=0.94 over four subsets
including Germany-only), and the within-day contrast still flips its sign,
which points at drift in the error series, not matches. A third test looks at
the real-time price, the one place an unanticipated shift could still surface
after the auction closes (R3): match-hour reBAP-minus-day-ahead runs
+2.18 ct/kWh in the raw matched comparison (placebo p=0.005), but the within-day
contrast that nets out day-level drift shrinks it to +1.20 at p=0.118, and the
Germany subset's eye-catching +6.34 collapses to +1.90 at p=0.45. The study's
power bounds the claim: no price effect larger than ~2.2 ct/kWh, no load effect
separable from seasonal drift, and no real-time effect that survives the drift
control.
([details](#the-world-cup-price-study-milestone-4))

**The method detects real events.** On a full year of data the same engine
finds the weekend effect at −4.08 ct/kWh in daytime prices (n=110, t=−14.22,
permutation p < 0.0005) and also a public-holiday effect at −6.91 ct/kWh (n=9,
permutation p=0.0035), so the World Cup null is a bounded finding from a working
instrument, not a broken tool. The caveat stands that detecting a 4 ct effect
does not prove sensitivity to small ones, which is why every null above carries
its minimum detectable effect.
([details](#the-generic-event-study-milestone-9))

**Live demo:** https://adrianogelato.github.io/energy-market-predictability/

## The story, and the logic of the sequence

This project started with the demand-and-price dynamic. Demand and
weather-driven supply set the spot price hour by hour, and I wanted to see that
mechanism in real data, so the first milestones just fetch and display prices.
Working with them forced a realization: displaying prices is the easy part. The
actual brainwork, and the IP of any company in this market, is the forecast.
The price is only where a good or bad forecast turns into profit or loss. That
reframed the project around forecasting, and it sharpened my original curiosity
into a testable question: had the forecasts considered the 2026 World Cup?

That question splits in two, and the split drives the architecture of
everything that follows. "Was it priced in?" is a question about anticipation,
and anticipation can only show up in the day-ahead price, which is fixed by
auction at noon the day before delivery (milestone 4). "Did the forecast miss
it?" is a question about surprise, and surprise can only show up in the
market's own forecast error, actual load minus the day-ahead load forecast
(milestones 6 and 7). The final answers: any priced-in effect is smaller than
~2.2 ct/kWh, and there is no forecast miss separable from seasonal drift.

So the milestones are not one sequence but three strands, interleaved because
they share data. Strand A (M1-M3) builds contact with the market. Strand B
(M4, M6, M7, M9) chases the event question, upgrading the measured variable
from price to forecast error as the question sharpened, then hardening the
inference with placebo tests and a positive control. Strand C (M5, M8, M10)
chases the forecast question: is the price shape predictable, what is that
worth, and how much algorithm does it take?
The ordering rule throughout: each milestone is the smallest runnable artifact
that unblocks the next.

## What it does

The project began as a hands-on way to learn how electricity markets and
dynamic pricing work by touching real data, and grew into the study above.
Everything is reproducible: anyone can clone the repo and run it. The
milestones below are grouped by strand; details and design decisions for each
follow further down.

### Strand A: see the market (M1-M3)

Milestone 1 (`python fetch_prices.py`, writes `prices.csv` and `prices.png`)
fetches the hourly day-ahead price and plots it. First because it is the
cheapest possible contact with the real market: no API key, one call, and the
volatility that everything downstream is about becomes visible.

Milestone 2 (`python cost_model.py`, reads `prices.csv`, writes `results.json`)
turns those prices into money: what does one household's day cost on a flat
versus a dynamic tariff, and what does shifting an EV charge into the cheapest
hours save. Its real contribution is the honest bill model
(wholesale + fixed adder), which bounds every later savings claim.

Milestone 3 (`tariff.html` plus the GitHub Actions workflow; preview locally
with `python -m http.server 8000`) publishes the price curve and the cost
comparison as a static page that a scheduled job keeps current. After this,
nothing else in the project is plumbing. (The site root, `index.html`, is a
findings one-pager added later: it computes the headline numbers live from
the committed result JSONs, so a first-time visitor lands on the conclusions
rather than a chart without context.)

### Strand B: the event question (M4, M6, M7, M9)

Milestone 4 (`python wc_fetch_data.py && python wc_analysis.py`, viewed on
`worldcup.html`) is the first attack on the motivating question, using the
data already at hand: do prices behave differently during World Cup match
hours than on weather-comparable days? It runs into a structural wall worth
knowing in advance: the day-ahead price is fixed the day before delivery, so a
price test can only measure anticipation, never a forecast miss. Quietly, this
milestone also builds the historical dataset that the forecaster (M5) trains
on, which is why strand C starts after it.

Milestone 6 (`python entsoe_fetch.py`, needs a free ENTSO-E token, writes
`wc_load.csv`) is the consequence of that wall: to test whether the forecast
missed the event, you need the market's own forecast and its miss. Actual load
minus the day-ahead load forecast is exactly that.

Milestone 7 (`python wc_load_effect.py`) asks the sharp version of the
question: did demand deviate from what was forecast during match hours, split
into prime-time and overnight kickoffs? Its capstone
(`python wc_permutation.py`) is the placebo test: several subsets were examined,
so any marginal result must survive a per-subset and a family-wise permutation
test before it means anything.

Milestone 9 (`python event_study.py`) generalises the method into a reusable
event-study engine and calibrates it: a method that only ever returns null
proves nothing, so it must find the certain weekend effect. It does
(about -4 ct/kWh on the full-year window, p < 0.0005), which is what supports
reading the World Cup null as a finding, within the limits of the study's
power; every null is reported together with its minimum detectable effect.

### Strand C: the forecast question (M5, M8, M10)

Milestone 5 (`python forecast_cheap_hours.py`, reuses `wc_prices.csv` and
`wc_weather.csv`) tests whether tomorrow's cheapest hours are predictable at
all, and whether a model beats naive rules (hypotheses H1a and H1b in
`ROADMAP.md`). It sits after M4 only because it reuses that milestone's
dataset; conceptually it is the start of the forecast strand.

Milestone 8 (`python forecast_value.py`, reads `forecast_results.json`)
converts the backtest into euros per year and separates the value of any smart
timing from the value the model adds. On the summer window it hinted at the
headline finding; milestone 10 then tested it properly.

Milestone 10 (`python year_fetch.py && python forecast_ladder.py`) is the
value-of-complexity study: a full backtested year, a six-rung ladder of
forecasters from a 28-day lookup table to gradient boosting, every rung scored
identically per season. It answers "how advanced does the algorithm need to
be?" with a curve, and the curve flattens at rung one. The lookup table
wins the year outright.

## Quickstart

```bash
git clone https://github.com/adrianogelato/energy-market-predictability.git
cd energy-market-predictability
bash setup.sh                     # creates .venv and installs dependencies
source .venv/bin/activate
python run_all.py                 # the whole pipeline, in dependency order
```

`run_all.py` is the one command to remember. It fetches fresh data and runs
every analysis in the right order; `python run_all.py --skip-fetch` re-runs
all analyses on the existing CSVs without touching the network. It knows the
dependencies: the ENTSO-E stage is skipped (not clobbered with synthetic data)
when no token is set, and it warns loudly if any fetch fell back to synthetic
data. It also finds the project's `.venv` by itself, so it works even when
started with the system python (an editor's Run button, for example) without
activating the venv first.

Everyday loop: after the first full run, `python run_all.py --skip-fetch` is the
command you use most. It rebuilds every analysis from the CSVs already on disk
with no network call. The R9 reBAP layer is fetched separately and on demand, not
by `run_all.py`: `python intraday_fetch.py --since` tops it up with only the new
tail (it re-fetches a few days of overlap to catch late-published values and
never overwrites real data with synthetic), while a plain `python
intraday_fetch.py` backfills the whole year. After either, `run_all.py
--skip-fetch` picks up the refreshed `intraday_prices.csv`.

To run a single step instead, every milestone
script still works on its own, e.g.:

```bash
python fetch_prices.py            # writes prices.csv and prices.png
python cost_model.py              # writes results.json and cost_comparison.png
```

To preview the page locally, serve the folder over HTTP:

```bash
python -m http.server 8000        # then open http://localhost:8000
```

Do not open the HTML pages by double-clicking them. That loads them from a
`file://` URL, and browsers block `fetch()` of local files over `file://`, so
the pages cannot read their JSON data and show a "could not load" error. The
local server above serves the files over `http://`, which fixes it. GitHub
Pages serves over `https://`, so the deployed pages have no such issue.

## How it works

The data flows in one direction. `fetch_prices.py` calls the aWATTar API and
writes `prices.csv`. `cost_model.py` reads that CSV, applies the tariff model,
and writes `results.json`. `tariff.html` reads `results.json` in the browser and
draws the charts; `index.html` (the one-pager) and `worldcup.html` read the
study JSONs the same way. The GitHub Actions workflow runs the first two steps
on a schedule and commits a fresh `results.json`, which makes GitHub Pages
redeploy.

Nothing talks to a database and there is no server. The only moving inputs are
the daily prices.

## Design decisions

This section documents why the project is built the way it is, including the
alternatives that were considered and rejected. The reasoning matters more than
the code.

### Data source: aWATTar

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

### The cost model is deliberately honest about savings

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

### Freshness: a daily GitHub Actions job, not a live browser fetch

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

### A static site on GitHub Pages, no backend

The site is five small pages that read committed JSON files in the browser:
`index.html` (the findings one-pager), `tariff.html` (the daily demo, charts
via Chart.js from a CDN), `worldcup.html` (the event study), `intraday.html`
(day-ahead versus real time), and `ladder.html` (the value-of-complexity
study). There is no build step, no framework, and no server to run or pay for.
GitHub Pages serves the repository directly. This keeps the whole thing free to
host, trivial to reason about, and forkable by anyone.

### Shared page furniture: page-nav.css and page-nav.js

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

### One stylesheet, and a design that reports its own limits

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

### Files as the interface, no database

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

### Reproducibility: a per-machine virtual environment

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

### Units: convert wholesale EUR/MWh to ct/kWh

The market quotes prices in EUR/MWh. Household bills are in ct/kWh. The code
converts once (`EUR/MWh / 10 = ct/kWh`) and works in ct/kWh everywhere after
that, so every number on the page is in the unit a person actually recognises
from their bill.

### A synthetic fallback so the scripts always run

If `prices.csv` is missing, `cost_model.py` generates a plausible synthetic day
instead of failing. This keeps the model runnable offline and testable in CI
without a network call, and makes the first-run experience forgiving. The
synthetic day is clearly a fallback, and any committed `results.json` is replaced
by real data on the first successful fetch.

### What a "weather-comparable day" means (matching.py)

All three event studies (M4, M7, M9) stand on the same definition of
"comparable day", so it lives in one inspectable module, `matching.py`, and
every result JSON embeds the definition it was produced with plus the exact
pairings chosen, which `worldcup.html` renders as an expandable table. The
parameter choices below are design decisions for the German bidding zone
specifically, not generic defaults, so each carries its reasoning.

Wind speed is a matching feature (when the weather file carries it). This is
the most market-specific decision in the module: Germany's price is set by
residual load, demand minus wind and solar infeed, and wind moves the German
day-ahead price at least as much as solar. Two days with identical temperature
and cloud but different wind regimes are not price-comparable at all. Omitting
wind was the initial design's biggest gap.

Solar is matched on radiation, falling back to cloud cover. Cloud percentage
is only a proxy: what displaces price is PV output, which follows shortwave
radiation. A 60%-cloud day in February and a 60%-cloud day in June are
entirely different solar days, which matters as soon as the window spans
seasons (the Olympics study will). Radiation also encodes season implicitly,
which cloud does not. Cloud is kept as the fallback so weather files fetched
before the radiation column existed keep working.

Temperature enters twice, as daily mean and daily max. Demand responds
nonlinearly to temperature: a mild-mean day with a hot afternoon drives
cooling load that a uniformly mild day does not, and in winter the same logic
applies to heating through the daily minimum. Mean-only matching would call
those days equal.

Day types are weekday / Saturday / sunlike, where "sunlike" is a Sunday or a
public holiday. Two decisions in one: Saturdays and Sundays are separate
classes because their load differs materially, and a public holiday is
classified as a Sunday because that is how the grid behaves. The second rule
exists because of a concrete failure: Whit Monday sat in this project's window
and was being offered as a "weekday" control while carrying a Sunday-sized
daytime price discount of roughly 6 ct/kWh, silently biasing every match day
it was paired with. (Removing it strengthened the measured weekend effect,
which is the direction you'd expect if it had been contaminating the pool.)

A season guard is on. `SEASON_GAP_MAX_DAYS` (21 days) caps how far apart in
the calendar a day and its controls may be, which is the direct defence
against the seasonal-drift confound documented in `ROADMAP.md`. It was off
while the only data was the one-sided World Cup window, where enforcing it
would have starved the control pool; it went on when the event studies moved
to the full-year files. The guard degrades gracefully: when fewer than K pool
days lie within the gap, the full pool is used, so the World Cup studies keep
working on their narrow window while the year-wide studies get strictly
seasonal controls.

Mechanics, not design decisions: features are z-scored and combined by
Euclidean distance with K=5 nearest; the matcher degrades gracefully to
whatever columns the weather file has; the event studies (M9) disable the
day-type filter on purpose, because comparing weekends against weekday
controls is their entire point.

### The World Cup price study (milestone 4)

The idea: people watching a match shift when they cook, heat, and use
appliances, which changes demand and therefore price. The "TV pickup" effect
(demand surges at half-time and full-time) is well documented in grid
operations. The question is whether it is visible in day-ahead prices.

Run it with:

```bash
python wc_fetch_data.py     # pulls historical prices + weather (or synthesizes)
python wc_analysis.py       # runs the study, writes wc_results.json
```

Then view `worldcup.html` through the local server.

Several design decisions shape this milestone.

The dependent variable is price, not demand. The honest, more direct signal
would be electricity demand (load), because the causal chain is match, then
demand, then price. Price is downstream and noisier, since it also moves with
wind, solar, and fuel. Price was chosen for this first pass because it kept
the study on the data source already at hand and, at the time, needed no API
token. That constraint no longer exists: the ENTSO-E token was obtained for
milestone 6 and the load-based test was built as milestone 7. M4 stays in
place because it still answers its own half of the question, anticipation
(was it priced in); M7 answers the other half, surprise (did demand deviate
from the forecast).

One market-design point bounds what this test can mean: the day-ahead price is
fixed in an auction at 12:00 the day before delivery. Nothing that happens
during a match can move that day's day-ahead price, so this is strictly a test
of whether traders *anticipated* a match effect, never of whether the match
caused one. An unanticipated demand shift would surface in the imbalance price,
which is what the R3 study tests, or in the load forecast error, which is
exactly what milestone 7 measures. Both come back null.

Match hours are kickoff plus two clock hours. That ignores extra time and
penalties in knockout games, and hourly data cannot resolve the classic "TV
pickup" (kettles at half-time and full-time), which is a minute-scale
phenomenon. Both simplifications dilute a real effect toward zero and are
accepted for a first pass on hourly data.

Weather is controlled by matched comparison, not ignored. Comparing match days
to arbitrary days would confound the match effect with weather, which drives
most price movement. Instead, each match day is paired with the five most
weather-comparable non-match days, with "comparable" defined once in
`matching.py` (see the section above), and prices are compared only within the
same clock hours. The chosen pairings are written into the results JSON and
shown on the page. This is the core of the method and the reason any result is
worth taking seriously.

Two honest footnotes on the statistics. The per-day deltas share control days
(the pool is smaller than the match-day count), so they are positively
correlated and the plain t is optimistic; the permutation test is the
trustworthy inference. And because the control days are mostly pre-tournament,
the analysis also reports a within-day difference-in-differences contrast that
nets out day-level seasonal drift. On the final window the two estimators read
+0.60 and +0.83 ct/kWh, both well inside noise (t=0.75 and 1.62), so they
agree on the verdict: no detectable price effect.

The match schedule is an editable CSV, not a hard-coded list or an API call.
There is no clean, keyless World Cup schedule API, and the knockout fixtures
depend on results. `wc_matches.csv` holds the kickoff times in German local time (CEST) and ships
with clearly marked EXAMPLE rows to be replaced with the official fixtures. The
scripts ignore rows that are blank or commented.

Everything has a synthetic fallback with a planted effect. If the price or
weather fetch fails (offline, or a blocked host), the fetcher generates a
realistic dataset in which match hours carry a deliberate price bump. This lets
the whole pipeline run and be validated without a network: the analysis is
expected to recover that planted effect, which is how the method was tested.
Real data carries no planted effect, so a null result on real data is a genuine
finding, not a bug. The results page shows a banner whenever it is displaying
synthetic data, so the two are never confused.

Times are handled in German local time (CEST for the whole study window, which
is summer) throughout. The 2026 tournament is hosted in North America, so
matches watchable in Europe are US afternoon kickoffs that land in the German
late evening and overnight. All match hours are expressed on that clock so they
line up with the price and weather series, and the fetchers convert timestamps
explicitly via Europe/Berlin rather than trusting the machine's local zone
(a CI runner is UTC, which would silently shift every hour label).

### The cheapest-hours forecaster (milestone 5)

This is the building block for the whole forecasting theme: if tomorrow's cheap
hours are not predictable, no downstream question is measurable. Run it with:

```bash
python forecast_cheap_hours.py     # after wc_fetch_data.py has produced the data
```

It reuses the milestone-4 dataset (`wc_prices.csv`, `wc_weather.csv`) rather than
fetching again.

#### How the model works

For every hour of a day, the model predicts that hour's electricity price from a
small set of inputs: the hour of day (encoded as sine and cosine waves so the
model can see the daily cycle rather than treating 23:00 and 00:00 as far
apart), whether it is a weekend, the temperature, and a solar term. The solar
term is shortwave radiation when the weather file carries it (the same upgrade
the matching engine got: radiation is the actual PV driver and already encodes
the daylight curve); on older weather files it falls back to cloud cover plus
a hand-built cloud-at-midday interaction (cloud matters most around midday,
when it blocks the solar generation that would otherwise push prices down).
These are combined with ordinary least squares, which is plain linear
regression: it finds the weighting of those inputs that best fits the past
prices. To predict a day, the model scores all 24 hours and takes the
lowest-priced N (default 3) as its predicted cheap hours. Note the honest
consequence for the H1b verdict: it is tied to the feature set and window it
was measured on, so it is worth re-checking after the refetch fills the
radiation column, and again on a winter window.

Training is walk-forward: to score a given day, the model is fit only on the days
before it, never on the day itself or later ones. That mimics real life, where
you only ever have the past to learn from, and it is what makes the backtest
honest.

#### Reading the output

The run compares four ways of choosing which hours to charge in, and scores each
against what actually happened.

The four strategies:

- **Perfect foresight** is the yardstick, not a real strategy. It assumes you
  already knew the day's prices and charged in the genuinely cheapest N hours.
  Nobody can do this in advance; it defines the best possible outcome.
- **Model** is the weather-and-calendar prediction described above.
- **Persistence** is a naive baseline: assume tomorrow's cheapest hours are the
  same clock hours that were cheapest yesterday. The "nothing changes" guess.
- **Climatology** is the other naive baseline: always pick the hours that are
  cheapest on average across the training period (typically overnight and the
  solar-rich midday). The "typical day" guess.

The three numbers reported for each:

- **Hit-rate** is the share of the N hours a strategy picked that were truly among
  the N cheapest that day. 1.0 means it picked exactly the right hours; with N=3,
  0.67 means it got two of the three right.
- **Cost** (ct/kWh) is what you would actually pay charging in the hours that
  strategy picked, valued at the real prices. Lower is better.
- **Regret** is cost minus the perfect-foresight cost: how much extra you paid
  compared with having known the prices in advance. 0 means you did as well as
  perfect; a regret of 0.30 means your timing cost you 0.30 ct/kWh more than the
  ideal, on average per day.

So a summary line like "best hit-rate: model" simply means that, of the three
real strategies, the model identified the cheapest hours most often; and "model
regret vs perfect: 0.34 ct/kWh" means acting on the model's picks cost you
0.34 ct/kWh more than perfect timing would have. The forecaster earns its place
only if it beats persistence and climatology on these numbers. If it does not,
that is a real result worth reporting, not a bug.

#### Design decisions

Several design decisions shape it.

The target is a selection, not a price. The model predicts the price of each
hour, but the thing scored is which N hours are cheapest, because that is what a
household or aggregator acts on. N defaults to 3, the EV-charge window from the
cost model.

The backtest is walk-forward, not a single split. For each test day the model is
trained only on earlier days (an expanding window), which is the honest way to
evaluate a time series and avoids leaking the future into the past.

It is measured against explicit baselines, not in a vacuum. Persistence (tomorrow
equals yesterday's cheap hours) and climatology (the usual cheap hours by time of
day) are the naive strategies any forecaster must beat to justify itself. The
report shows hit-rate, the real cost paid, and regret against perfect foresight,
so the model's value is a concrete number rather than an accuracy score in
isolation.

The model is deliberately simple and dependency-light. A linear model with daily
harmonics and a cloud-at-midday interaction, fit with numpy, captures the daily
shape and the solar effect without a heavy machine-learning stack. A stronger
model is a later milestone; the point here is a correct, honest baseline.

What the backtest actually found (real data, 45 test days): the model does NOT
meaningfully beat the naive baselines. On the refreshed window its hit-rate
edges ahead (0.785 vs climatology's 0.770 and persistence's 0.763), but in
money terms that is worth €0.60/yr against climatology, which is noise, not
product value. By this section's own criterion, the forecaster did not earn its
place, and that is the finding, not a failure to have one. The cheap hours of
a German summer day are so stable (overnight plus solar-rich midday) that a
lookup table is the right product. Two caveats keep this honest in both
directions: the backtest feeds the model actual weather (a perfect forecast),
so the model's true deployed skill would be even lower; and the window is
summer-only, so whether a model earns its keep in winter, when solar no longer
pins the midday dip, is an open question. On the synthetic dataset the price is
generated from weather, so the model wins by construction there; that result
only proves the machinery works.

### ENTSO-E load data (milestone 6)

`entsoe_fetch.py` pulls two series for the DE-LU zone: actual load and the
day-ahead load forecast. It writes `wc_load.csv` with both plus their difference,
the forecast error.

```bash
export ENTSOE_TOKEN=your-token-here     # see below
python entsoe_fetch.py
```

Getting a token. ENTSO-E's API is free but gated. Register at
https://transparency.entsoe.eu, then email transparency@entsoe.eu with the
subject "RESTful API access" and your registered address in the body. Access is
granted within a few working days and the token appears in your account settings. More 
details in their [online guide](https://transparencyplatform.zendesk.com/hc/en-us/articles/12845911031188-How-to-get-security-token).

#### Design decisions

The token comes from the environment, never the repository. The script reads
`ENTSOE_TOKEN`, either from a shell `export` or from a local `.env` file, and
nothing else. Copy `.env.example` to `.env` and put your token there:

```bash
cp .env.example .env      # then edit .env and paste your token
```

`.env` is gitignored, so the secret is never committed; `.env.example` is a
committed template with a placeholder. The loader does not overwrite a value
already set in the shell, so an explicit `export` still wins. Without a token,
the script falls back to synthetic data rather than failing.

Forecast error is the target, not raw load. The interesting quantity is actual
minus day-ahead forecast, because that is where the market was surprised. This is
the variable the M7 study will test during match hours, and it is a more direct
measure of an event's demand impact than price, which also moves with wind, solar,
and fuel.

Times are converted to CEST to match the rest of the project. ENTSO-E returns
values in UTC. The whole study window is summer, so the code adds a fixed two
hours to reach CEST, keeping load, prices, weather, and match times on one clock.
Sub-hourly data (the DE zone often reports quarter-hourly) is averaged to hourly.

The synthetic fallback plants a demand bump, not a price bump. On the synthetic
path, actual load carries an extra fixed amount during match hours while the
forecast does not, so the forecast error spikes on match hours. The M7 analysis
is expected to recover that bump, which is how the load pipeline was validated.

### The forecast-error study (milestone 7)

`wc_load_effect.py` answers the sharper half of the event hypothesis. Run it
after the load fetch:

```bash
python wc_load_effect.py     # needs wc_load.csv from entsoe_fetch.py
```

#### Design decisions

The variable is the forecast error, not raw demand. Raw demand is dominated by
weather and the daily cycle. Actual minus day-ahead forecast strips most of that
out and isolates where the market's own prediction was wrong, which is the
cleanest signature of an unanticipated event.

It reuses the M4 comparable-days design unchanged. The same weather-matched
control days and the same match-hour definition are applied, only the measured
quantity changes from price to forecast error. Reusing the method keeps the two
studies directly comparable: M4 asks "was it priced in", M7 asks "did demand
actually move".

The effect is reported in MW and as a share of load. A raw MW number is hard to
judge, so it is also expressed as a percentage of average load, which is the
honest way to say whether an effect is large or trivial. Every null also
reports its minimum detectable effect (80% power), so "no effect" always means
"no effect larger than X", and a within-day difference-in-differences contrast
is reported alongside the main estimate as a robustness check against the
day-level drift described in `ROADMAP.md`.

It is split into prime-time and overnight kickoffs, plus a Germany-only subset.
Because the tournament is in North America, many matches kick off after
midnight CEST when almost nobody in Germany is watching, and averaging those in
dilutes any real effect. The study runs four ways: all matches, prime-time
kickoffs (18:00-23:59 CEST), overnight ones (00:00-06:59 CEST), and matches
with Germany playing. Any TV-driven effect should concentrate in prime time, so
that subset is the sharpest test; a difference between the subsets is itself
informative. The Germany subset exists because the home team is by far the
best-followed single event in this market, at the price of a very small n, so
its minimum detectable effect does most of the talking.

The synthetic check mirrors the fetcher's planted bump. On synthetic load the
match hours carry an extra fixed demand that the forecast does not see, so this
study is expected to recover it. That is how the pipeline was validated before
any real token was used. On real data, expect a smaller and possibly null
effect, especially because European-evening viewing of a North American
tournament is thin and concentrated in overnight hours.

### The permutation test (milestone 7 capstone)

`wc_permutation.py` answers a question the t-statistic alone cannot: several
subsets were tested, so how surprising is the one marginal result really?

```bash
python wc_permutation.py
```

It keeps the real match-hour patterns but attaches them to randomly chosen days,
rebuilds the weather-matched controls, and recomputes the effect thousands of
times. The share of those random runs whose effect is at least as extreme as the
real one is a distribution-free p-value. It answers the multiple-testing
question properly: each draw relabels the days once and carries every day's
subset membership along, so all subset t's come from the same draw, and
the maximum |t| across them builds the family-wise null, the correct reference
when the most extreme of several examined subsets is the one being reported.

On the final window the overnight blip lands at a subset p of 0.922 and a
family-wise p of 0.938 (over four subsets, the Germany-only one included), so
it is consistent with chance. A within-day difference-in-differences
robustness check (in `wc_load_effect.py`) agrees for the opposite reason: it
flips the overnight estimate to −570 MW, and two estimators that disagree in
sign mean the drift in the forecast-error series, not the matches, is driving
both. This is the check that keeps the null honest instead of hand-waved.

### The forecast's money value (milestone 8)

`forecast_value.py` reads the M5 backtest and expresses it in euros per year for
a household shifting one EV charge per day into the cheap hours.

```bash
python forecast_value.py     # needs forecast_results.json from forecast_cheap_hours.py
```

#### Design decisions

It separates three distinct values. Charging in cheap hours at all versus charging
whenever is one number; the model's gain over naive heuristics (persistence,
climatology) is a second; the gap from the model to a perfect forecast is a third.
Conflating them would overstate what the model itself is worth.

It uses wholesale price differences, which is legitimate. The fixed adders on a
real bill are equal in every hour, so they cancel when comparing strategies. The
euro figures are therefore the true savings from timing, independent of the
tariff's fixed part. But they are annualized at summer rates: the backtest
window is 45 early-summer days, when solar spreads are at their widest, so the
per-year numbers are a summer-rate extrapolation, not a calendar-year estimate.
Winter would need its own window.

It is willing to report that the model adds little. On the real data the
sophisticated model roughly ties the trivial climatology heuristic: the cheap
hours are so stable that "just charge at the usual cheap times" captures nearly
all the value. Reporting that honestly, rather than burying it, is the point of
the exercise.

### The generic event study (milestone 9)

`event_study.py` makes the World Cup analysis one instance of a general tool: does
a set of special days behave differently from weather-comparable normal days?

```bash
python event_study.py     # uses prices, so no ENTSO-E token needed
```

It runs two demonstrations: weekends versus comparable weekdays, and German public
holidays (`events_holidays.csv`) versus comparable weekdays, each with a
permutation p-value.

#### Design decisions

It runs on the full-year files when they exist. The studies read
`year_prices.csv` and `year_weather.csv` (milestone 10) and fall back to the
World Cup window files on a clone that only ran the short fetch. The year-wide
pool is what turned the holiday test from n=1 into a real test, and it is the
window where the season guard in `matching.py` (controls at most 21 calendar
days away) has room to work.

The weekend case is a positive control, not filler. A method that only ever
returns null is useless, because you cannot tell "no effect" from "cannot detect
anything". The weekend effect is large and certain, so finding it (here
−4.08 ct/kWh in daytime price over 110 weekend days, permutation p < 0.0005,
which is the floor of 2000 draws, since a permutation p is never exactly zero)
proves the machinery works. One limitation stated plainly: detecting a 4 ct
effect does
not demonstrate sensitivity to small ones, which is why the World Cup null is
reported with its minimum detectable effect (~2.2 ct/kWh) rather than as an
unqualified "no effect".

The holiday test is now a second positive control. On the year window nine
German public holidays carry data, and the engine finds −6.91 ct/kWh
(t=−3.80, permutation p=0.0035): holidays price like Sundays, as the grid folk
wisdom says. The earlier summer-only window held a single holiday (Whit
Monday, n=1, no usable t), and the engine said so rather than pretending;
widening the window was the backlog item that fixed it.

The signal is price, so it runs without a token. Weekends and holidays lower
daytime demand and therefore daytime price, so the effect is visible in the
aWATTar price series alone. Load can be swapped in where a token is available.

### The value-of-complexity ladder (milestone 10)

The M5/M8 verdict ("the model adds nothing over a lookup table") came from 37
summer days, the season where solar pins the cheap hours in place and a lookup
table cannot lose. This study asks the question properly, and reframes it from
a binary into a curve: how advanced does the forecasting algorithm need to be?

```bash
python year_fetch.py          # 365 days of prices + weather (new files, no fallback)
python forecast_ladder.py     # the ladder; add scikit-learn for the gbm rung
```

Six rungs, every one scored with the same walk-forward backtest, the same
metrics, per season: a 28-day rolling climatology (a lookup table refreshed
monthly), persistence, the M5 linear model, a richer linear model (annual
harmonics, day types, wind), a dependency-free k-nearest-days kernel
regression, and gradient boosting.

The result (353 test days, 2025-07 to 2026-07): the curve flattens at rung one.
Climatology wins the year outright at hit-rate 0.68 and regret 0.38 ct/kWh,
€210/yr saved versus charging anytime against a €225/yr perfect-foresight
ceiling, which is 93% of the ceiling captured by a monthly-refreshed lookup
table.

The paired sign-flip tests say how firm that is, and they are stronger than
"no model beats it". Four of the five models cost significantly *more* per day
than the lookup table: linear +0.215 ct/kWh (p=0.001, €8.63/yr), persistence
+0.207 (p=0.009, €8.33/yr), richer linear +0.198 (p=0.001, €7.94/yr), gradient
boosting +0.131 (p=0.022, €5.24/yr). Only k-nearest-days is indistinguishable
from it (+0.020 ct/kWh, p=0.613, minimum detectable effect 0.115 ct/kWh), and it
ties rather than wins. Family-wise max-|t| is 3.21 (linear), p=0.003, so the
result is not an artefact of running five comparisons.

Weather models do win in winter, where the price shape genuinely varies:
0.41 ct/kWh regret versus climatology's 0.51, worth about €1 per winter for the
household. In the shoulder seasons the linear models are actively worse than the
lookup table (up to 1.02 ct/kWh regret in autumn), overfitting weather levels
while missing the hour ranking that actually matters.

Why does a lookup table beat gradient boosting? Because the product target is
a selection, not a price. Weather moves price *levels* strongly, but the
*ranking* of hours, which three are cheapest, is pinned by the daily solar
and demand cycle almost every day. Models spend their capacity explaining
level variance that the selection task never rewards.

Accuracy and decision value are therefore different yardsticks, and the study
reports both. `forecast_ladder.py` emits per-rung price-accuracy metrics (MAE,
RMSE, and MAPE guarded against near-zero prices, plus MAE/RMSE over the picked
hours only) next to the regret ladder, and a paired sign-flip permutation test
of each rung's daily cost against the lookup table, with a minimum detectable
effect for every null and a family-wise max-|t| across the five comparisons.
Four rungs predict price levels more accurately than the lookup table (k-nearest
days at MAE 2.59 ct/kWh, gradient boosting 2.69, richer linear 2.79, persistence
2.81, against climatology's 2.95) and none of them converts that into better
hour picks; three of the four are significantly worse on the decision task. The
common objection "a well-built model is more accurate than a lookup table" is
usually true, and beside the point; ladder.html shows both metric families in
one table ("Accuracy is the wrong yardstick").

Two design decisions keep the comparison honest. The climatology baseline is
rolling (28 days), not full-history, so a winter day is judged against winter;
a full-history mean would have been a strawman. And every weather-using rung
sees actual weather, a perfect forecast it would never have in production,
while climatology needs no forecast at all, so the lookup table's win is
conservative and would widen under deployed conditions. The
deployed-realism variant (archived weather forecasts) and the quarter-hourly
version remain on the backlog.

The product reading, which is the point of the study: the algorithm choice
moves €9/yr at most; being on a dynamic tariff with *any* automated timing
moves ~€210/yr. At household scale, engineering budget belongs in automation,
onboarding, and trust, not in the forecaster. (An aggregator trading
hundreds of MW across thousands of vehicles prices the same €-per-kWh gaps
very differently; that question is out of scope here.)

The whole chain is published on `ladder.html`: the verdict, the reasoning in
seven steps, the ladder curve, a residual-by-hour chart showing where each
model systematically misses, single inspected days (each rung's worst fit),
and the critical questions answered as design decisions. The script also
writes `forecast_ladder_diagnostics.json` and two diagnostic PNGs.

### Day-ahead versus real time: how good is the market's own forecast (R9)

The whole project treats the day-ahead price as ground truth. It is, for the
bill: a dynamic tariff settles the household at the day-ahead auction price. But
that price is itself a forecast, the outcome of an auction that clears on
forecast demand and forecast wind and solar. This study measures how good that
forecast is by comparing the day-ahead price against the price that forms at
real time, when the actual system state is known.

```bash
python intraday_fetch.py      # day-ahead (year_prices.csv) + reBAP; needs credentials
python intraday_analysis.py   # writes intraday_results.json + intraday_analysis.png
```

Then view `intraday.html` through the local server. The reBAP fetch is a
deliberate on-demand step and is NOT part of `run_all.py`: it backfills a full
year from netztransparenz on every call, the source only updates a few times a
month, and the rate limit rewards infrequent use, so re-fetching it on every
pipeline run would be wasteful. `run_all.py` only (re)builds
`intraday_results.json` from whatever `intraday_prices.csv` already exists; fetch
fresh reBAP by hand when you want it, and otherwise run `run_all.py --skip-fetch`.

The data source is the finding that shaped the study. The first plan compared
day-ahead against the intraday auction and the imbalance price from ENTSO-E.
A probe (`intraday_probe.py`) proved ENTSO-E carries neither for Germany: the
intraday "A07" query just returns the day-ahead series, and every imbalance
(A85) query returns "no matching data" for every German control-area domain and
every window. Germany's real-time price, the reBAP (the uniform balancing-energy
price the four transmission system operators settle deviations at), is published
on netztransparenz.de instead. So R9 is day-ahead versus reBAP, a single
zone-local real-time signal, and the ROADMAP assumption that ENTSO-E would serve
intraday and imbalance prices under the existing token is corrected in place.

The reBAP comes from the netztransparenz WebAPI, which needs its own OAuth2
client credentials (separate from the ENTSO-E token): register for the
"WebAPIReader" role, create a client to get an ID and secret, and put them in
`.env` as `IPNT_CLIENT_ID` and `IPNT_CLIENT_SECRET`. The fetcher reads the
documented endpoint `NrvSaldo/reBAP/Qualitaetsgesichert` (CSV "Format 9"),
converts its UTC timestamps to Europe/Berlin and its EUR/MWh values to ct/kWh,
and averages the quarter-hours to hourly (the quarter-hour version is a backlog
item). It has the same synthetic fallback discipline as the other fetchers, and
`python intraday_fetch.py --selftest` checks the parser against the
documentation's own sample without any network call.

Mind the rate limit. The netztransparenz firewall allows at most two requests
per second per source IP, and a repeated breach blocks the IP for two hours. The
fetcher spaces its requests, warns before it would approach the cap, and backs
off if the server returns 429, so a normal yearly run (one request per monthly
chunk) is well clear. If you script your own calls against the API, keep them
under two per second.

Official documentation, useful when the API changes or a fetch fails:

- WebAPI overview and getting started: https://www.netztransparenz.de/en/Web-API
- WebAPI FAQ (endpoints, Swagger, 401 troubleshooting): https://www.netztransparenz.de/en/FAQ/FAQ-WebAPI
- Full WebAPI documentation (endpoint table, CSV "Format 9", rate limits), PDF v1.14:
  https://www.netztransparenz.de/xspproxy/api/staticfiles/ntp-relaunch/dokumente/web-api/dokumentation-webserviceapi-netztransparenz_v1.14.pdf
- Swagger (all endpoints, "Try it out"): https://api-portal.netztransparenz.de/public-swagger-ui
- reBAP data (definition, calculation model): https://www.netztransparenz.de/en/Balancing-Capacity/Imbalance-price/Uniform-imbalance-price-reBAP
- OAuth token endpoint: https://identity.netztransparenz.de/users/connect/token

On data handling: netztransparenz.de publishes no explicit reuse licence for the
reBAP, so the raw series is treated as not redistributable. The fetched
`intraday_prices.csv` is gitignored and stays local; only `intraday_results.json`
is committed, and it holds derived aggregates (median spreads by hour, volatility
ratios, overlap counts), never the raw reBAP series.

Several design decisions shape the analysis. The imbalance price is heavy-tailed,
most hours quiet and a few scarcity hours extreme, and those tails are the
phenomenon, not noise, so every spread is reported as a median and inter-quartile
range alongside the mean and no outliers are trimmed. The study reports the
systematic day-ahead bias by hour (where the day-ahead auction reliably under- or
over-prices), the real-time volatility relative to day-ahead by season, and
whether the three cheapest day-ahead hours are still the three cheapest at real
time, with the extra cost of acting on the day-ahead ranking but valuing it at
real time. That euro figure is framed throughout as a flexibility hypothetical,
never a household saving: the household is billed at the day-ahead price no matter
what real time does, so this study cannot move the household verdict. It answers
the narrower, honest question of whether the day-ahead price is a good proxy for
real-time scarcity, which matters for flexibility settled closer to delivery and
is the zone-local signal the event work reuses (R3, below). The verdict on
`intraday.html` is computed live from `intraday_results.json`, so it always
matches the committed numbers.

#### What it found

On the full year of real reBAP (2025-07-12 to 2026-07-28, 8,925 hours),
day-ahead is nearly unbiased in level: the median reBAP-minus-day-ahead spread is
+0.04 ct/kWh, and the systematic hour-of-day bias never exceeds about 1 ct/kWh
(the largest is −0.92 ct/kWh at 19:00, day-ahead running slightly dear into the
evening ramp, and slightly cheap around midday). The action is all in the
variance. Real time is 1.9 times as volatile as day-ahead (2.2x in winter, 1.6x
in summer), the two are only 0.54 correlated, and reBAP ranges from about -420 to
+260 ct/kWh. The three cheapest day-ahead hours are all still the three cheapest
at real time on only 12.6% of days (87 of 372 days share none). The verdict:
day-ahead is a good proxy for the typical hour's price level, but a poor proxy
for real-time scarcity and for which hours are actually cheapest.

The cost of that ranking failure needs two numbers, not one, because the spread
is fat-tailed. Averaged over the year the settlement regret is 3.03 ct/kWh, about
122 EUR/yr at 11 kWh/day. On a typical day it is 1.73 ct/kWh, about 69 EUR/yr at
the same volume. Both are correct and they answer different questions: an annual
figure is a sum over days, and a sum is the day count times the mean, so 122
EUR/yr is what someone holding the position all year actually accumulates, while
1.73 ct/kWh is what an ordinary day looks like. The gap between them is the tail:
the worst 5% of days carry 32% of the annual total. Quoting only the mean
overstates the typical day; quoting only the median understates the year. This
README leads with the mean wherever the figure is annual, and says "median day"
whenever it is not.

A robustness note, since the window grew by 16 days in the 2026-07-30 refetch:
almost nothing moved. The median spread went from +0.051 to +0.041 ct/kWh, the
inter-quartile range from 4.777 to 4.787, the volatility ratio from 1.908 to
1.907, the correlation from 0.5439 to 0.5448, and the cheapest-three survival
rate stayed at 12.6%. These are year-scale aggregates over ~9,000 hours and they
are stable, which is the reason to trust them.

#### Product reading: household versus aggregator

This prices the real-time slice of the product argument (ROADMAP R5), and it
splits cleanly by who holds the balancing position. For the household, billed at
day-ahead, the systematic gap is zero at every hour, so there is no
consumer-facing intraday product: nothing to pass through. The consumer's value
stays where the ladder study put it, automated day-ahead timing worth about
210 EUR/yr, model-agnostic (M10). The real-time value is entirely in the
variance, and a median spread of zero means there is no free arbitrage: a
provider profits by managing its reBAP exposure well, which is skill against a
1.9x-volatile, fat-tailed price, not a guaranteed margin. The size of that
real-time flexibility pool is about 122 EUR/yr per household-equivalent (the
settlement regret), roughly 58% of the day-ahead timing prize, but capturable
only by whoever holds the position, so it is a business-to-business aggregation
play (a virtual power plant or flexibility aggregator), not a household one. The
tail concentration matters for that reading too: a third of the pool sits in 5%
of days, so capturing it means being ready on the days that matter rather than
grinding out a daily margin. The two euro figures are different pools, not
simply additive, and the 122 EUR/yr is
indicative rather than bankable, since reBAP is a settlement price for imbalance,
not a quote anyone can freely trade at.

### The World Cup in real time: where a surprise could still hide (R3)

```bash
python wc_intraday.py          # needs intraday_prices.csv from intraday_fetch.py
```

The day-ahead price study (M4) has a structural ceiling on what it can detect.
The auction clears at 12:00 the day before delivery, so a day-ahead price can
only ever show whether traders *anticipated* a match effect. An unanticipated
demand shift arrives after the auction closes and shows up in the price that
forms at delivery. In the German zone that is the reBAP, which R9 built the data
layer for. So this study asks the same question against the one outcome variable
where a genuine surprise could survive: is the reBAP-minus-day-ahead spread
different during match hours than on weather-comparable days?

It reuses the whole World Cup apparatus, the match-hour schedule, the
`matching.py` comparable-days engine, the Germany subset and the permutation
battery, and swaps only the outcome. Medians throughout, because the spread is
fat-tailed for the same reason R9's is.

#### What it found

Nothing that survives a drift control. Coverage is 34 of 35 match days
(2026-07-18 is still not published in the quality-assured reBAP series).

The raw matched comparison looks like a hit: match-hour spread +2.18 ct/kWh
versus comparable days, placebo p=0.005, against a null 95th percentile of
1.55 ct/kWh. The within-day contrast, which subtracts each day's own non-match
hours before comparing against controls and therefore removes any day-level
shift, cuts it to +1.20 ct/kWh at p=0.118. That is the estimate to read, and it
does not clear the bar.

The reason is visible directly in the data: match days run +0.43 ct/kWh above
the matched control days across **all 24 hours**, not just match hours (+0.32
versus −0.11 on the day medians; against every non-match day in the surrounding
period rather than the matched pool the gap is wider still, about
+0.69 ct/kWh). A football
match lasting two to four hours cannot lift a whole day's imbalance spread, so
that shift is period drift and the headline estimator absorbs it. The same
signature shows up in the calendar split, where the effect concentrates in June
(+2.48 ct/kWh over 20 days) and largely vanishes in July (+0.89 over 14 days),
even though July is the knockout stage with the larger audiences. A causal
viewing effect should run the other way.

The Germany subset is the trap in this study and is worth stating plainly. Its
headline reads +6.34 ct/kWh at placebo p=0.033, which is the only figure anywhere
in the World Cup work that clears a significance threshold. It does not survive:
all four Germany match days (14, 20, 25 and 29 June) fall inside the drift-heavy
first half of the tournament, and under the same within-day contrast the effect
drops to +1.90 ct/kWh at p=0.452. On four days the within-day inter-quartile
range is 10.56 ct/kWh, so that subset cannot support a claim in either direction.
The family-wise guard is reported on both estimators for exactly this reason:
p=0.033 on the headline, p=0.455 drift-robust. The second is the one to quote.

So H2 now has three independent tests and three bounded nulls: the day-ahead
price (was it anticipated), the load forecast error (did demand actually
deviate), and the real-time price (did the auction misprice it). None shows an
effect that survives its drift control. Worth noting for honesty about
multiplicity: the real-time spread is the third outcome variable tried on one
event, and the family-wise correction only spans subsets within a study, not
across the three studies, so a nominal p=0.005 on the third attempt is worth
less than it reads. That does not change the conclusion here, because the
drift-robust estimates are null anyway.

## Assumptions and limitations

The numbers are a model, not a bill. The flat rate, the fixed adder, the
household load shape, and the EV charge size are all assumptions set at the top
of `cost_model.py` and are easy to change. The model covers one household over
one day and does not account for standing charges, billing intervals shorter than
an hour, battery storage, or self-generation from solar. It is meant to build
intuition for how dynamic pricing works, not to advise a purchase.

## Repository layout

```
run_all.py                 runs the whole pipeline in dependency order
fetch_prices.py            milestone 1: fetch and plot day-ahead prices
cost_model.py              milestone 2: flat vs dynamic tariff cost model
index.html                 the findings one-pager (site root; computes numbers from the JSONs)
tariff.html                milestone 3: the daily tariff demo (reads results.json)
results.json               model output, committed and refreshed daily
matching.py                the comparable-days matching engine (shared by M4/M7/M9)
wc_fetch_data.py           milestone 4: historical prices + weather fetcher
wc_matches.csv             milestone 4: editable match schedule (fill from fixtures)
wc_analysis.py             milestone 4: the comparable-days price study
worldcup.html              milestone 4: study results page (reads wc_results.json)
forecast_cheap_hours.py    milestone 5: cheapest-hours forecaster + backtest
entsoe_fetch.py            milestone 6: ENTSO-E actual + forecast load fetcher
wc_load_effect.py          milestone 7: forecast-error study during match hours
wc_permutation.py          milestone 7 capstone: placebo / permutation test
forecast_value.py          milestone 8: euros-per-year value of the forecast
event_study.py             milestone 9: generic event-study engine
year_fetch.py              milestone 10: full-year price + weather fetcher
forecast_ladder.py         milestone 10: the value-of-complexity ladder
forecast_ladder.json       milestone 10 results, committed (index.html reads it)
ladder.html                milestone 10: the value-of-complexity page
intraday_fetch.py          R9: day-ahead + reBAP fetcher (netztransparenz WebAPI)
intraday_analysis.py       R9: day-ahead vs real-time reBAP study
intraday_results.json      R9 results, committed (intraday.html reads it)
intraday.html              R9: day-ahead vs real-time reBAP page
intraday_probe.py          R9 diagnostic: proves ENTSO-E lacks DE intraday/imbalance
netztransparenz_probe.py   R9 diagnostic: finds the reBAP WebAPI endpoint
wc_intraday.py             R3: World Cup match hours in the reBAP spread
wc_intraday_results.json   R3 results, committed (aggregates only)
site.css                   shared: the visual system (tokens, type, components)
bound.js                   shared: the bound bar, effect against detectable limit
chart-theme.js             shared: Chart.js fonts and greys, load without defer
page-nav.css               shared: section menu + back-to-top styling
page-nav.js                shared: builds the section menu from the headings
events_holidays.csv        German public holidays (event study + day-typing)
data/                      raw schedule source files (provenance only, see data/README.md)
ROADMAP.md                 working hypothesis and milestone plan
requirements.txt           dependencies (version floors)
setup.sh                   one-time local environment setup
.github/workflows/         the daily refresh workflow
.vscode/settings.json      optional VS Code interpreter hint
.gitignore                 ignores .venv and regenerable outputs
LICENSE                    MIT
```

## Deploy your own

1. Create a GitHub repository and push this folder to it.
2. Run the scripts once locally and commit the generated `results.json` so the
   page has data on first load.
3. In the repository, open Settings, then Pages, and set the source to "Deploy
   from a branch", branch `main`, folder `/ (root)`.
4. The refresh workflow runs daily on its own. To run it immediately, open the
   Actions tab, select "Refresh price data", and use "Run workflow". The workflow
   needs write permission, which is granted by the `permissions` block in the
   workflow file.

## Roadmap

The hypotheses and their verdicts, the limitations, and the prioritized backlog
live in `ROADMAP.md` (this README holds the milestone descriptions; that file
holds the working ledger). The post-tournament rerun and the seasonal-control
repair are done (2026-07-22); the day-ahead-versus-real-time study (R9) is built
against the reBAP price after a probe established that ENTSO-E does not carry
German intraday or imbalance prices; and the event-side real-time test (R3) is
built on that layer and comes back null once day-level drift is controlled
(2026-07-30). Queued there, in priority order: pricing the findings for
stakeholders, a virtual home energy management system built on the lookup-table
finding, the Winter Olympics as a second event, deployed-realism forecasts,
15-minute resolution, and a cross-country dose-response study.

## Data sources and attribution

The code is MIT-licensed (below), but the data it fetches is not the project's to
relicense, and the sources differ, so provenance is tracked explicitly here and
in the `NOTICE` file.

Electricity load and day-ahead load forecast (milestones 6 and 7) come from the
[ENTSO-E Transparency Platform](https://transparency.entsoe.eu), which publishes
its open-reuse data under the Creative Commons Attribution 4.0 International
licence (CC-BY 4.0). Reuse and redistribution are permitted with attribution to
ENTSO-E. Day-ahead prices come through the free
[aWATTar API](https://www.awattar.de/services/api) (EPEX SPOT day-ahead prices
passed through), and weather comes from [Open-Meteo](https://open-meteo.com),
also CC-BY 4.0. For all three, the raw fetched CSVs are gitignored and only
derived, aggregated results are committed.

The German real-time price, the reBAP, comes from
[netztransparenz.de](https://www.netztransparenz.de), published by the four German
transmission system operators. It carries no explicit reuse licence, so this
project treats the raw reBAP series as not redistributable: `intraday_prices.csv`
is gitignored and never committed, and only `intraday_results.json` (median
spreads by hour, volatility ratios, overlap counts, all derived aggregates, never
the raw series) is committed. The match schedule and holiday list were compiled by
the author from public information. None of this is legal advice; where a source
grants no licence, the project keeps the raw data local and publishes only its own
analysis.

## License

MIT, see `LICENSE`. You are free to clone, modify, and reuse this.
