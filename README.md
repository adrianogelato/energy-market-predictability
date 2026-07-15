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
full backtested year (337 days), shifting a daily 11 kWh EV charge into the
three cheapest hours saves about €203/yr versus charging anytime. (An earlier
summer-only window said €307/yr; peak solar spreads inflated it.) Across a
six-rung ladder of forecasters, from a 28-day lookup table up to gradient
boosting, the lookup table wins the whole year outright; every model
underperforms it overall, weather models pay off only in winter, and there by
roughly €1 per season for the household — despite being fed perfect weather.
**Product implication: a smart-charging feature on this market needs
automation and UX, not ML.**
([ladder](#the-value-of-complexity-ladder-milestone-10),
[forecaster](#the-cheapest-hours-forecaster-milestone-5),
[value](#the-forecasts-money-value-milestone-8))

**The World Cup does not detectably move the German market.** Prices during
match hours: +0.89 ct/kWh vs weather-comparable days (t=0.97), collapsing to
+0.14 under a within-day contrast that nets out seasonal drift. Load forecast
error: the one marginal subset (overnight, +833 MW, t=2.04) fails the placebo
test (family-wise permutation p=0.40) and flips sign under the within-day
contrast. The study's power bounds the claim: no price effect larger than
~2.6 ct/kWh, no load effect separable from seasonal drift. Interim until the
final on 19 July. ([details](#the-world-cup-price-study-milestone-4))

**The method detects real events.** The same engine finds the weekend effect at
−6.10 ct/kWh in daytime prices (t=−12.1, permutation p < 0.0005), so the World
Cup null is a bounded finding from a working instrument, not a broken tool —
with the caveat that detecting a 6 ct effect does not prove sensitivity to
small ones, which is why every null above carries its minimum detectable
effect. ([details](#the-generic-event-study-milestone-9))

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
(milestones 6 and 7). The current answers: any priced-in effect is smaller than
~2.5 ct/kWh, and there is no forecast miss separable from seasonal drift.

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
(`python wc_permutation.py`) is the placebo test: three subsets were examined,
so any marginal result must survive a per-subset and a family-wise permutation
test before it means anything.

Milestone 9 (`python event_study.py`) generalises the method into a reusable
event-study engine and calibrates it: a method that only ever returns null
proves nothing, so it must find the certain weekend effect. It does
(about -6 ct/kWh, p < 0.0005), which is what supports reading the World Cup
null as a finding, within the limits of the study's power; every null is
reported together with its minimum detectable effect.

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
be?" with a curve — which turns out to flatten at rung one. The lookup table
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
activating the venv first. To run a single step instead, every milestone
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

The site is three small pages that read committed JSON files in the browser:
`index.html` (the findings one-pager), `tariff.html` (the daily demo, charts
via Chart.js from a CDN), and `worldcup.html` (the event study). There is no
build step, no framework, and no server to run or pay for. GitHub Pages serves
the repository directly. This keeps the whole thing free to host, trivial to
reason about, and forkable by anyone.

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

A season guard exists but ships off. `SEASON_GAP_MAX_DAYS` caps how far apart
in the calendar a day and its controls may be, which is the direct defence
against the seasonal-drift confound documented in `ROADMAP.md`. It is off by
default as a deliberate trade: with the current one-sided window (controls
almost all pre-tournament), enforcing it would starve the control pool. It
should be enabled (around 21 days) as soon as the fetch window is widened.

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
caused one. An unanticipated demand shift would surface in intraday or
imbalance prices (a parked next step) or in the load forecast error, which is
exactly what milestone 7 measures.

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
nets out day-level seasonal drift. On the current data it collapses the
+0.89 ct/kWh headline to +0.14, which is what identifies that headline as
drift rather than a match effect.

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

What the backtest actually found (real data, 37 test days): the model does NOT
beat the naive baselines. Hit-rate 0.757 ties climatology exactly and trails
persistence (0.766); in money terms the model is worth −€0.28/yr against
climatology. By this section's own criterion, the forecaster did not earn its
place — and that is the finding, not a failure to have one. The cheap hours of
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

It is split into prime-time and overnight kickoffs. Because the tournament is in
North America, many matches kick off after midnight CEST when almost nobody in
Germany is watching, and averaging those in dilutes any real effect. The study
runs three ways: all matches, prime-time kickoffs (18:00-23:59 CEST), and
overnight ones (00:00-06:59 CEST). Any TV-driven effect should concentrate in
prime time, so that subset is the sharpest test; a difference between the two
subsets is itself informative.

The synthetic check mirrors the fetcher's planted bump. On synthetic load the
match hours carry an extra fixed demand that the forecast does not see, so this
study is expected to recover it. That is how the pipeline was validated before
any real token was used. On real data, expect a smaller and possibly null
effect, especially because European-evening viewing of a North American
tournament is thin and concentrated in overnight hours.

### The permutation test (milestone 7 capstone)

`wc_permutation.py` answers a question the t-statistic alone cannot: three
subsets were tested, so how surprising is the one marginal result really?

```bash
python wc_permutation.py
```

It keeps the real match-hour patterns but attaches them to randomly chosen days,
rebuilds the weather-matched controls, and recomputes the effect thousands of
times. The share of those random runs whose effect is at least as extreme as the
real one is a distribution-free p-value. It answers the multiple-testing
question properly: each draw relabels the days once and carries every day's
subset membership along, so all three subset t's come from the same draw, and
the maximum |t| across them builds the family-wise null — the correct reference
when the most extreme of several examined subsets is the one being reported.

On the current data the overnight blip lands at a subset p of 0.228 and a
family-wise p of 0.401, so it is consistent with chance. A within-day
difference-in-differences robustness check (in `wc_load_effect.py`) agrees for
the opposite reason: it flips the overnight estimate to −758 MW, and two
estimators that disagree in sign mean the drift in the forecast-error series,
not the matches, is driving both. This is the check that keeps the null honest
instead of hand-waved.

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
window is 37 early-summer days, when solar spreads are at their widest, so the
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

The weekend case is a positive control, not filler. A method that only ever
returns null is useless, because you cannot tell "no effect" from "cannot detect
anything". The weekend effect is large and certain, so finding it (here about
-6 ct/kWh in daytime price, permutation p < 0.0005 — the floor of 2000 draws;
a permutation p is never exactly zero) proves the machinery works. One
limitation stated plainly: detecting a 6 ct effect does not demonstrate
sensitivity to small ones, which is why the World Cup null is reported with its
minimum detectable effect (~2.5 ct/kWh) rather than as an unqualified "no
effect".

The signal is price, so it runs without a token. Weekends and holidays lower
daytime demand and therefore daytime price, so the effect is visible in the
aWATTar price series alone. Load can be swapped in where a token is available.

It is honest about the holiday sample. Only one public holiday (Whit Monday) falls
in the summer data window, so the holiday test has n=1 and no usable t. The engine
says so rather than pretending. Widening the fetch window into spring (Good Friday,
Easter Monday, Labour Day, Ascension) would give a proper holiday test, and is
noted in the backlog.

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

The result (337 test days, 2025-07 to 2026-07): the curve flattens at rung
one. Climatology wins the year outright — hit-rate 0.67, regret 0.40 ct/kWh,
€203/yr saved versus charging anytime — and no model beats it overall (knn
comes closest at 0.42; the linear models and gradient boosting trail it).
Weather models do win in winter, where the price shape genuinely varies:
0.41 ct/kWh regret versus climatology's 0.51. That advantage is worth about
€1 per winter for the household. In the shoulder seasons the linear models are
actively worse than the lookup table (up to 1.02 ct/kWh regret in autumn),
overfitting weather levels while missing the hour ranking that actually
matters.

Why does a lookup table beat gradient boosting? Because the product target is
a selection, not a price. Weather moves price *levels* strongly, but the
*ranking* of hours — which three are cheapest — is pinned by the daily solar
and demand cycle almost every day. Models spend their capacity explaining
level variance that the selection task never rewards.

Two design decisions keep the comparison honest. The climatology baseline is
rolling (28 days), not full-history, so a winter day is judged against winter;
a full-history mean would have been a strawman. And every weather-using rung
sees actual weather, a perfect forecast it would never have in production,
while climatology needs no forecast at all — so the lookup table's win is
conservative, and would widen under deployed conditions. The
deployed-realism variant (archived weather forecasts) and the quarter-hourly
version remain on the backlog.

The product reading, which is the point of the study: the algorithm choice
moves €9/yr at most; being on a dynamic tariff with *any* automated timing
moves ~€200/yr. Engineering budget belongs in automation, onboarding, and
trust, not in the forecaster — at household scale. (An aggregator trading
hundreds of MW across thousands of vehicles prices the same €-per-kWh gaps
very differently; that question is out of scope here.)

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
holds the working ledger). Currently parked there, in priority order: the
post-tournament rerun, widening the fetch window into spring, the
intraday/imbalance study, a winter backtest for the forecaster, the Winter
Olympics as a second event, 15-minute resolution, and a cross-country
dose-response study.

## License

MIT, see `LICENSE`. You are free to clone, modify, and reuse this.
