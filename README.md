# Energy market predictability: forecasting the German power market, and measuring where forecasts fail

Can you predict tomorrow's cheapest electricity hours, what is that prediction
worth in euros, and can a scheduled mega-event (the 2026 World Cup) move the
German power market? Real day-ahead prices, real ENTSO-E load data, explicit
baselines, and honest statistics, published as a static page that refreshes
itself daily.

**About this project.** I built this during my job search, as a portfolio
piece for product management / product ownership and project management roles
in the energy market domain. The substance is the point, not the packaging:
real market data, a reproducible pipeline, and statistics that are allowed to
say "no effect".

**Where things live.** The findings and the reasoning behind them are on the
site, one page per study. This file covers the repository: how it is built, how
to run it, and why it is built that way. `ROADMAP.md` is the working ledger,
holding the hypotheses with their verdicts, the standing limitations, and the
backlog.

## The findings

All three live on the site, with the numbers computed at page load from the
committed result JSONs, so the pages cannot drift from the analysis:

| | Question | Answer | Page |
| --- | --- | --- | --- |
| 1 | Can you predict tomorrow's cheapest hours, and what is it worth? | Smart timing is worth real money; the algorithm barely matters. | [forecaster ladder](https://adrianogelato.github.io/energy-market-predictability/ladder.html) |
| 2 | Is the day-ahead price the right thing to predict? | Fair for the household, poor proxy for real time. | [day-ahead vs real time](https://adrianogelato.github.io/energy-market-predictability/intraday.html) |
| 3 | Can a scheduled mega-event move the market? | Not detectably, across three independent tests. | [World Cup study](https://adrianogelato.github.io/energy-market-predictability/worldcup.html) |

Start at the [project overview](https://adrianogelato.github.io/energy-market-predictability/), which carries all three with their
product implications and links onward. The reasoning, charts, method notes and
critical questions for each study live on its own page rather than here: this
file documents how the repository is built and run.

## Data and licensing, before you run anything

The code is MIT (see `LICENSE`). The data it fetches is not the project's to
relicense, and the sources differ. `NOTICE` records each one and how it is
handled.

One constraint matters before you run the fetchers. The German imbalance price
(reBAP, from netztransparenz.de) carries **no explicit reuse licence**, so this
project treats the raw series as not redistributable: `intraday_prices.csv` is
gitignored and never committed, and only derived aggregates are published. If
you fetch it, the same applies to your copy. `NOTICE` also documents a
reconstruction risk that shaped the output format, because two committed files
could otherwise be joined to recover reBAP levels for specific dates.

## What it does

The project began as a hands-on way to learn how electricity markets and
dynamic pricing work by touching real data, and grew into the studies above.
Everything is reproducible: anyone can clone the repo and run it. The
milestones below are grouped by strand, in the order they were built, with the
reason each one exists. What each study concluded is on its page; the
engineering decisions behind all of them are under Design decisions.

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
proves nothing, so it must find the certain weekend effect. Whether it does, and what that
licenses you to conclude about the World Cup result, is on the
[World Cup page](https://adrianogelato.github.io/energy-market-predictability/worldcup.html).

### Strand C: the forecast question (M5, M8, M10)

Milestone 5 (`python forecast_cheap_hours.py`, reuses `wc_prices.csv` and
`wc_weather.csv`) tests whether tomorrow's cheapest hours are predictable at
all, and whether a model beats naive rules (hypotheses H1a and H1b in
`ROADMAP.md`). It sits after M4 only because it reuses that milestone's
dataset; conceptually it is the start of the forecast strand.

Milestone 8 (`python forecast_value.py`, reads `forecast_results.json`)
converts the backtest into euros per year and separates the value of any smart
timing from the value the model adds. On the summer window it hinted at the
headline result; milestone 10 then tested it properly.

Milestone 10 (`python year_fetch.py && python forecast_ladder.py`) is the
value-of-complexity study: a full backtested year, a six-rung ladder of
forecasters from a 28-day lookup table to gradient boosting, every rung scored
identically per season. It answers "how advanced does the algorithm need to
be?" with a curve; the curve and its verdict are on the
[ladder page](https://adrianogelato.github.io/energy-market-predictability/ladder.html).


### Beside the strands: market quality (R9) and the real-time event test (R3)

R9 (`python intraday_fetch.py && python intraday_analysis.py`) asks how good the
day-ahead price is as a forecast of the price that forms at delivery, the German
imbalance price. R3 (`python wc_intraday.py`) reuses that data layer to run the
World Cup against the real-time price, the one place an unanticipated shift could
survive the auction closing. Results on
[intraday.html](https://adrianogelato.github.io/energy-market-predictability/intraday.html) and
[worldcup.html](https://adrianogelato.github.io/energy-market-predictability/worldcup.html).

### Two conventions across every study

Every null reports the minimum effect the study could have detected, so "no
effect found" is a bounded claim rather than a shrug. And permutation (placebo)
tests are the inference of record, because event days share control days, which
makes plain t-statistics optimistic.

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

Why the project is built the way it is, with the alternatives considered and
rejected, is in **[`docs/design-decisions.md`](docs/design-decisions.md)**:

- Data source: aWATTar
- The cost model is deliberately honest about savings
- Freshness: a daily GitHub Actions job, not a live browser fetch
- A static site on GitHub Pages, no backend
- Shared page furniture: page-nav.css and page-nav.js
- One stylesheet, and a design that reports its own limits
- Files as the interface, no database
- Reproducibility: a per-machine virtual environment
- Units: convert wholesale EUR/MWh to ct/kWh
- A synthetic fallback so the scripts always run
- What a "weather-comparable day" means (matching.py)

The analytical choices, what counts as a comparable day and why the statistics
are shaped the way they are, are argued on the study pages and in `ROADMAP.md`.

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
docs/design-decisions.md   why the project is built the way it is
ROADMAP.md                 working ledger: hypotheses, verdicts, limitations, backlog
NOTICE                     data sources, their terms, and how each is handled
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

`ROADMAP.md` is the working ledger: hypotheses with verdicts, the standing
limitations every result is read against, outcome-level bets grouped by
horizon, and the task backlog.


## License

MIT, see `LICENSE`. You are free to clone, modify, and reuse this.
