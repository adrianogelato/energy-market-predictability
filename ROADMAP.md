# Roadmap and working ledger

Two documents, two jobs, no duplication. The README is the presentation layer:
the story, the findings, what each milestone does and how to run it, and the
design decisions. This file is the working ledger: the hypotheses and their
verdicts, the limitations that constrain every result, the roadmap (outcome
level bets, grouped by horizon), and the task backlog that feeds it. If a
milestone description is what you want, it lives in the README's three strands,
not here.

## The theme

Predicting the electricity market, and measuring where the predictions fail.

A dynamic-tariff price is nothing more than the day-ahead spot price passed
through to the consumer. That spot price is the outcome of a market auction that
clears on forecasts: forecast demand and forecast wind and solar. So the price
already contains a forecast. The value a flexibility company adds is not in
displaying the price, it is in forecasting it well enough to move flexible
load and trade flexibility. The forecast, and its errors, are the interesting
object of study. Collecting and plotting prices is only the foundation under it.

## Working hypotheses

The project is organised around two linked hypotheses. H1 was originally one
claim ("cheap hours are predictable from weather and calendar, measurably
better than naive guessing"); the results forced a split, because its two
halves came out differently. Conflating them hid the most interesting finding.

H1a, the predictability hypothesis: tomorrow's cheapest hours are predictable.
**Verdict: confirmed, now on a full year.** A 28-day rolling climatology
("charge at the usual cheap times, refreshed monthly") captures about 93% of
the perfect-foresight value over 337 backtested days (€203 of a €219/yr
ceiling for the model household). The cheap-hour ranking is pinned by the
daily solar and demand cycle in every season.

H1b, the model-value hypothesis: a weather-driven model beats naive rules at
picking those hours. **Verdict: refuted, over a full year and a six-rung
ladder (forecast_ladder.py).** No model beats the rolling lookup table
overall — not the linear models, not k-nearest-days, not gradient boosting,
all fed perfect actual weather. Models win only in winter (regret 0.41 vs
0.51 ct/kWh), worth about €1 per winter for the household; in the shoulder
seasons linear models are actively worse than the lookup table. The original
summer-only verdict was a lower bound taken where models matter least; the
full year confirms it rather than overturning it, and the summer question
("does H1b fail only because solar pins the cheap hours?") is answered: it
fails everywhere at household scale, winter included.

The refuted half remains the most valuable result: the algorithm choice moves
at most €9/yr while automated timing at all moves ~€200/yr, so a
smart-charging product built on this market needs automation and UX, not ML.
The open remainder is deployed realism (archived weather forecasts instead of
actuals, which can only widen the lookup table's lead) and the aggregator
scale, where the same €-per-kWh gaps price differently.

Note the original framing also claimed H1 "has to be true before anything else
is meaningful". That was wrong: the event studies (H2) never depended on the
forecaster, and the value analysis (M8) is meaningful precisely because the
model failed. What downstream work actually needs is H1a, not H1b.

H2, the event-effect hypothesis. Planned, scheduled large-scale events such as
the FIFA World Cup shift electricity demand in a way that is visible in the
market once weather is controlled for. There is an important distinction inside
H2:

Anticipated effects are already priced in. The World Cup is scheduled years
ahead, so any demand impact traders expect is already in the day-ahead price. If
the effect shows up in day-ahead prices, the market anticipated it.

Unanticipated effects show up as forecast error, not in the day-ahead price. The
cleaner and more direct measure of an event's impact is the day-ahead load
forecast versus the actual load, which is the market's own prediction and its
miss. A spike in that error concentrated around match hours is strong evidence.

So H2 is really two tests: a price test (was it anticipated) and a forecast-error
test (did demand actually deviate). The World Cup study runs both: M4 is the
price test, M7 (on ENTSO-E load data) the forecast-error test.

## What an answer looks like

Success criteria for the delivered hypotheses. Future work carries its own
"answer looks like" line per roadmap item below.

For H1a/H1b: a forecast skill number. The hit-rate of the predicted cheapest
hours and the mean error, both compared against explicit naive baselines, plus
the money a household or aggregator captures by acting on the forecast versus
perfect foresight and versus naive behaviour. (Delivered by M5 and M8 on the
summer window and settled by M10 on a full year; verdicts above.)

For H2: an effect size with uncertainty, and, when the estimate is null, the
minimum detectable effect, so "no effect found" is a bounded statement rather
than a shrug. A price difference in ct/kWh and a load deviation in MW during
match hours relative to weather-comparable days, robust to the weather controls
and to a within-day difference-in-differences contrast, with permutation
p-values (per subset and family-wise across subsets).

Where H2 landed (final; complete tournament window 11 June to 19 July 2026,
35 match days, season guard on): no robust effect anywhere. The price test
reads +0.60 ct/kWh (t=0.75, MDE ≈ 2.2 ct/kWh) and +0.83 under the within-day
contrast (t=1.62), both consistent with no effect. The load forecast-error
test's once-marginal overnight subset is consistent with chance (subset
p=0.922, family-wise p=0.938 over four subsets, Germany-only included) and
still flips sign under the within-day contrast (+625 MW main, −570 MW
within-day), which says the error series drifts across the window in a way
neither estimator fully removes. The Germany-only subset is flat in both
tests (+0.27 ct/kWh price, +632 MW load, n=4, MDEs 6.7 ct/kWh and 5,600 MW).
The honest summary: any World Cup effect on the German market is smaller than
~2.2 ct/kWh in price and not separable from seasonal drift in load.

## Milestones

All ten milestones are built. Their descriptions, run commands, and the
reasoning for their order live in the README under "What it does" (three
strands: A, see the market, M1-M3; B, the event question, M4/M6/M7/M9; C, the
forecast question, M5/M8/M10). They are not repeated here. How each maps to
the hypotheses: M5 tests H1a/H1b, M8 prices the verdict, M10 settles both on a
full year; M4 tests the anticipation half of H2, M7 the surprise half, M9
calibrates the instrument.

## Limitations to carry throughout

This is the standing risk register: every roadmap item and every published
number is read against these constraints.

The control pool is seasonal, and this is the binding constraint. Because
matches run almost daily from 11 June to 19 July, nearly all non-match control
days fall in mid-May to early June, which is cooler than July. Weather-matching
helps but is stretched across a seasonal gap. The data shows the damage
directly: on "comparable" days the midday load forecast error runs around
−3,700 MW versus −1,100 MW on match days, at hours where no matches happen, so
part of any measured "match effect" is period drift, not matches. The
within-day difference-in-differences contrast removes additive day-level drift,
but the drift here changes the intraday *shape* (midday solar forecast bias),
which is why the main estimate and the DiD disagree in sign for load. The
season guard in `matching.py` (controls at most 21 calendar days away,
delivered with R2) caps how far the drift can stretch, but inside the
one-sided World Cup window the controls remain mostly pre-tournament, so the
constraint is reduced, not removed; the sign-flipping DiD on the final window
shows the residual drift.

Per-day effect estimates share control days (a pool of ~28 controls serves ~30
match days, 5 each), so they are positively correlated and plain t-statistics
are optimistic. The permutation tests are the trustworthy inference; the t's
are descriptive.

Weather is local, the price is zonal. The day-ahead price covers the whole
German-Luxembourg bidding zone, while the weather signal is currently a single
Berlin point. A population-weighted or multi-point weather input would be a
better proxy for zone-wide conditions.

Price is downstream of demand. Price also moves with wind, solar, and fuel, so it
is a noisy proxy for the demand effect we care about. This is exactly why the
load-based forecast-error test in M7 matters.

## Roadmap

How to read it. Items are outcome-level bets, not tasks, grouped into Now
(committed and being worked), Next (committed direction, starts when Now
clears), and Later (believed valuable, not yet committed). Horizons instead of
dates on purpose: a solo research project's capacity is uncertain, and dated
promises would be false precision. Each item states the outcome, why it sits
where it does, what an answer looks like, its dependencies, and who benefits
(household, tariff/flexibility company, or the methodology itself). Concrete
work lives in the task backlog below; every task points at a roadmap item.

Two research paths share one spine. Path one, forecasting-algorithm
complexity: how much of the price shape is predictable, and how much model
does that take? Path two, event-effect measurement: do scheduled events move
the market beyond its predictable baseline? The spine: an event effect is
nothing but a deviation from a counterfactual baseline, so the better the
forecasting model from path one, the sharper the event tests in path two. The
paths converge in R8, where the forecaster itself replaces comparable-day
matching as the control.

### Non-goals

- No database, no dashboard framework. Files are the interface; the rationale
  is a README design decision and it holds at this scale.
- No production ML forecaster. H1b's refutation is the finding: algorithm
  choice moves at most €9/yr while automated timing at all moves ~€200/yr.
  Building a better model would chase the small number.
- No live or real-time operation. This stays an offline study; deployed
  realism enters only as archived forecasts (R6).

### Now

(Empty. R1 and R2 were delivered on 2026-07-22, see the changelog; the next
items to pull are R3-R5.)

### Next

**R3. Test H2 in a market where surprise can exist** (path two)
- Outcome: the surprise half of H2 gets its proper market-side test. The
  day-ahead price is fixed at 12:00 the day before delivery, so M4 could only
  ever measure anticipation; intraday or imbalance prices are where an
  unanticipated demand shift would show.
- Why next: it closes a known logical hole in H2 rather than opening a new
  question.
- Answer looks like: event-hour intraday or imbalance price deviation with
  MDE, run through the same robustness battery as M9.
- Depends on: an ENTSO-E intraday or imbalance price fetch (same token).
- Who benefits: methodology; a flexibility company trading imbalance.

**R4. Winter Olympics study: the reuse test** (path two)
- Outcome: does the methodology generalize? Milano Cortina (6-22 February
  2026) varies what the World Cup could not: a winter market where heating
  demand and scarce daylight drive the price shape instead of solar, and a
  host in Germany's own timezone (CET), so finals landed in German daytime
  and prime-time viewing hours. If a TV effect exists anywhere, this is the
  well-powered place to look.
- Why next: it is the designed reuse vehicle for the M9 engine plus an events
  CSV, and the February window is already covered by the full-year fetch, so
  no new price or weather data is needed.
- Answer looks like: effect sizes with MDEs on curated high-German-viewership
  sessions (biathlon, ski jumping, medal finals; the Olympics run all day for
  17 days, and flagging every hour would dilute exposure to nothing), with
  controls on BOTH sides of the event (late January and March), avoiding the
  one-sided seasonal drift that undermined the World Cup study.
- Depends on: proper Europe/Berlin handling in `entsoe_fetch.py` (it hardcodes
  the summer +2 h CEST conversion); a curated events file.
- Who benefits: methodology (external validity of the whole event framework).

**R5. Price the findings for the stakeholders** (path one, product lens)
- Outcome: finding 1 (the lookup table captures ~93% of perfect-foresight
  value) turned into decisions. Household side: which consumer configurations
  beyond the EV case profit from a smart tariff and by how much; relevant
  sizing for local storage (Home Energy Management System as a product).
  Company side: what the result means for computational requirements (a
  lookup table needs almost none) and where product value concentrates
  (automation and UX, not model complexity).
- Why next: it converts the strongest existing result into the project's
  product argument; no new data is needed.
- Answer looks like: €/yr per consumer configuration; a defined set of
  relevant consumers; a storage-sizing statement; company-side implications
  stated plainly.
- Depends on: nothing new; extends M8's cost model.
- Who benefits: household and company both.

### Later

**R6. Deployed realism for the forecast ladder** (path one)
- Outcome: the ladder scored against archived weather forecasts instead of
  actuals, bounding the lookup table's lead under real deployment conditions.
  It can only widen: the models lose their information edge, the lookup table
  never had one.
- Why later: it sharpens a settled verdict rather than answering a new
  question.
- Answer looks like: the ladder curve rerun on forecast inputs, same metrics.
- Depends on: open-meteo archived forecasts (already available).
- Who benefits: a company deciding whether to buy model complexity.

**R7. 15-minute resolution** (serves both paths)
- Outcome: the first resolution where the classic TV-pickup (kettles at
  half-time and full-time) could appear at all; hourly averaging dilutes it
  toward zero. Also the resolution a real smart-charging product would trade,
  since the European day-ahead auction (SDAC) switched to 15-minute products
  on 1 October 2025, so the entire study window is already quarter-hourly at
  the source.
- Why later: mechanical touch across fetchers, cost model, and pages. The
  load half is cheap (`entsoe_fetch.py` already receives quarter-hourly load
  and deliberately averages it to hourly, so the sharper M7 test only needs
  the averaging removed) and can be pulled forward if the event studies stay
  null at hourly resolution.
- Answer looks like: M7 rerun on quarter-hours; the cost model's EV window
  and the forecaster's target as 15-minute blocks if aWATTar serves them.
- Depends on: removing the averaging; checking whether aWATTar's API returns
  quarter-hour prices.
- Who benefits: methodology and product.

**R8. Cross-country dose-response, where the two paths converge** (path two endpoint)
- Outcome: treatment variation the single-zone design lacks. Germany dropped
  out early but several European teams kept playing: the same match hours,
  watched intensely in one country and not in another. Signal is the load
  forecast error, not price: day-ahead prices are coupled across European
  zones, so a price effect smears across borders, while the forecast error is
  zone-local. The sharp test: a semifinal country's forecast error during its
  match hours versus Germany's (neutral) in the same hours, each with its own
  weather-matched controls; the same-hours cross-zone contrast also nets out
  Europe-wide common shocks, which the single-zone design cannot. Endpoint of
  the spine: a model-based event study where the forecaster replaces
  comparable-day matching as the control.
- Why later: largest scope. Every ingredient exists (ENTSO-E carries load and
  day-ahead load forecast for every European zone under the same token,
  open-meteo covers any city, the matching and event engines are
  zone-agnostic), but it multiplies data volume and analysis surface.
- Answer looks like: per-country event-hour forecast-error contrasts with
  MDEs and the full permutation battery.
- Depends on: R1 finalized; a multi-zone fetch.
- Who benefits: methodology (the strongest identification design available
  to this project).

**R9. Day-ahead versus intraday: how good is the market's own forecast?**
(path one, market lens)
- Outcome: the study treats day-ahead prices as ground truth, which they are
  for the bill (dynamic tariffs settle at the day-ahead auction price), but
  they embody the market's day-ahead forecasts of load and renewables. This
  item measures how well that forecast holds up: compare day-ahead against
  intraday and imbalance prices for the same delivery hours, quantify the
  spread by hour and season, and test whether the cheapest-3 ranking
  survives from day-ahead to intraday, i.e. whether a cheap-hour picker
  would choose different hours under intraday settlement.
- Why later: it cannot move the household verdict, because the household is
  billed at day-ahead prices regardless. It becomes decision-relevant only
  for intraday-settled tariffs or flexibility traded closer to delivery.
- Answer looks like: day-ahead minus intraday spread distributions with the
  usual honest-null bounds; a rank-stability number for the cheapest hours;
  one verdict sentence on whether day-ahead is a good proxy for real-time
  scarcity at household-relevant hours.
- Depends on: an intraday price source (ENTSO-E publishes intraday and
  imbalance prices under the existing token; coverage to be checked before
  committing).
- Who benefits: tariff and flexibility companies; methodology (it tests the
  premise, stated on ladder.html, that predicting the day-ahead price is the
  right target).

**R10. Implications from cheapest hour prediction** (path one, product lens)
- Outcome: Use cases for individuals, fleet operators, tariff and flexibility companies.
  Can the finding of using a lookup table to predict the cheapest hours be transformed
  into a usable product? Could I built my own energy management system (EMS) at home if
  I had an EV-comparable stationary energy storage (e.g. with a programmable BMS for a
  battery)? What is the loss when the cheapest hours are mis-predicted?
- Why later: it is the progression from the finding while still being an independent
  development module/step.
- Answer looks like: Virtual EMS as a browser page with configurable setup (number of
  EVs, capacity of available storage, electricity tariff, etc.).
- Depends on: ENTSO-E data, weather data
- Who benefits: individuals, fleet operators, tariff and flexibility companies.

## Task backlog

Concrete, executable work, priority top to bottom. Every task points at a
roadmap item or names its purpose.

1. (R4) Fix `entsoe_fetch.py` timezone handling: ZoneInfo("Europe/Berlin")
   instead of the hardcoded summer +2 h CEST conversion, so it can serve a
   February window.
2. (R4) Curate the Olympics events CSV: high-German-viewership sessions only.
3. (R5) Define the relevant consumer configurations beyond the EV case and
   run the cost model per configuration.
4. (R5) Local storage sizing analysis (wall-box scale).
5. (Ladder) One local rerun of `forecast_ladder.py` to populate the
   window-size comparison (n=2/3/4, `by_n` aggregates plus per-day `daily`
   blocks in `forecast_ladder.json`) and the accuracy-vs-decision-value
   blocks (`accuracy`, `paired_vs_lookup`; needs scikit-learn for the gbm
   rung) already built into the script and ladder.html. Verdict aggregates
   stay pinned to n=3.

## Parked

Parked means: not on the roadmap, with a stated condition that would unpark it.

Module separation beyond `matching.py` (aWATTar price data, ENTSO-E load data,
and event data as inspectable components). Unpark when a second consumer of
the fetchers appears, which R4's February window or R8's multi-zone fetch
would create.

Raw-data browser (a way to inspect the underlying hourly prices, load,
weather, and forecast error directly, not only the aggregated results).
Unpark if debugging an event study demands it or the project needs an
exploration surface.

## Changelog

A roadmap is a living document; the revisions are part of the record.

- 2026-07-22: R1 delivered. Full pipeline rerun on the complete tournament
  window (through the 19 July final, Spain 1-0 Argentina; finalist labels
  filled into wc_matches.csv): H2 final verdict is a bounded null, numbers in
  "Where H2 landed" above, all cited numbers reconciled. The interim notices
  on index.html and worldcup.html retired themselves as designed.
- 2026-07-22: R2 delivered. Season guard enabled in `matching.py`
  (SEASON_GAP_MAX_DAYS=21, degrading to the full pool when fewer than K days
  fall inside the gap, so the narrow World Cup window keeps working);
  event_study.py now runs on `year_prices.csv`/`year_weather.csv` with a
  fallback to the World Cup files. Result: the holiday test went from n=1 to
  n=9 and found −6.91 ct/kWh (t=−3.8, permutation p=0.013), a second positive
  control next to the weekend effect (−3.93 ct/kWh, n=106, p < 0.0005 on the
  year window).

- 2026-07-21: page navigation (section menu + back-to-top) added to
  ladder.html and worldcup.html, then extracted to shared `page-nav.css` and
  `page-nav.js` once the second copy appeared and more pages were planned.
  Pages opt in with an empty `<nav id="toc">`; the menu is generated from
  `section[id] > h2`, so it cannot drift from the headings. index.html and
  tariff.html do not opt in yet: tariff.html has two sections, too few to
  navigate. Design decision recorded in README, "Shared page furniture".
- 2026-07-21: R9 added (day-ahead vs intraday). Prompted by the accuracy
  discussion: day-ahead prices are settlement truth for the bill but embody
  the market's own forecasts; whether they proxy real-time conditions is a
  separate, answerable question. Filed under Later because it cannot change
  the household verdict.
- 2026-07-21: accuracy vs decision value made explicit (old tasks 9 and 10,
  verdict hygiene + ladder metrics). `forecast_ladder.py` now emits per-rung
  price-accuracy metrics (MAE, RMSE, guarded MAPE, and MAE/RMSE over the
  picked hours only) and a paired sign-flip permutation test of each rung's
  daily cost against the lookup table (per-rung p, MDE at 80% power,
  family-wise max-|t|). ladder.html gained the "Accuracy is the wrong
  yardstick" section: both metric families in one table plus the test
  verdict, with a data-driven guard that flips the text if a rerun ever
  shows a model beating the lookup table. Finding on the committed daily
  records: no model beats the lookup table on decision value; knn is
  statistically indistinguishable (p about 0.66) and gbm trails by about
  5 euro/yr (p about 0.06), while several rungs beat the lookup table on
  MAE/RMSE. Accuracy and decision value rank the models differently, which
  is finding 1 stated precisely. One local rerun (task 9) populates the new
  JSON blocks.
- 2026-07-20: restructured this file from a flat prioritized backlog into a
  roadmap (Now/Next/Later, outcome-level items with rationale, success
  criteria, dependencies, stakeholders) plus a task backlog. No open work
  dropped; completed items moved here.
- 2026-07, World Cup near-final pass: Germany-only subset implemented across
  the full chain (price test, load test, permutation with family-wise
  correction over four subsets) and surfaced on worldcup.html; H2 interim
  verdict updated on the window through 18 July (weaker than the earlier
  blips); worldcup.html hourly price chart gained the min-max band and
  per-hour match counts; the interim info boxes now hide themselves once
  wc_results.json reaches 2026-07-19; units are no longer spelled out in any
  chart caption (non-unit acronyms like CEST and RMSE stay spelled out per
  the chart design rules).
- 2026-07, full-year ladder study (M10) delivered: H1a confirmed, H1b
  refuted. H1 split into H1a and H1b because its two halves came out
  differently; the original single claim hid the main finding. Ladder
  diagnostics and ladder.html published, including the window-size
  comparison (task 11 populates it with one local rerun).
- Earlier: hour-alignment fix in the cost model; timezone-explicit fetches
  (CI-safe); sample-SD t-statistics; minimum detectable effects reported with
  every null; within-day difference-in-differences robustness checks;
  family-wise permutation test across subsets; permutation p-values surfaced
  on the results page; comparable-day matching engine extracted into
  `matching.py` with richer market-specific features (wind, radiation,
  temperature max), day-type classes with holiday exclusion, and the exact
  pairings exposed in the JSONs and on the page.

## Data sources

aWATTar for day-ahead prices (free, no key, equals EPEX SPOT). open-meteo for
weather, historical archive and forecast (free, no key; temperature, cloud,
wind, shortwave radiation). ENTSO-E Transparency
Platform for load, load forecast, and generation mix (free, needs a token),
added at M6. Match schedule in wc_matches.csv, converted to German local time (CEST).
