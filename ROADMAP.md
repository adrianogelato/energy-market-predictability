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
the perfect-foresight value over 353 backtested days (€210 of a €225/yr
ceiling for the model household). The cheap-hour ranking is pinned by the
daily solar and demand cycle in every season.

H1b, the model-value hypothesis: a weather-driven model beats naive rules at
picking those hours. **Verdict: refuted, over a full year and a six-rung
ladder (forecast_ladder.py), and the paired tests make it stronger than a
non-result.** Four of the five models are significantly *worse* per day than
the rolling lookup table: linear +0.215 ct/kWh (p=0.001), persistence +0.207
(p=0.009), richer linear +0.198 (p=0.001), gradient boosting +0.131 (p=0.022).
The fifth, k-nearest-days, is statistically indistinguishable from it (+0.020,
p=0.613, minimum detectable effect 0.115), so it ties rather than wins. All
were fed perfect actual weather. Family-wise max-|t| 3.21 (linear), p=0.003, so
this is not an artefact of five comparisons. Models win only in winter (regret
0.41 vs 0.51 ct/kWh), worth about €1 per winter for the household; in the
shoulder seasons linear models are actively worse than the lookup table. The
original summer-only verdict was a lower bound taken where models matter least;
the full year confirms it rather than overturning it, and the summer question
("does H1b fail only because solar pins the cheap hours?") is answered: it
fails everywhere at household scale, winter included.

Note the correct statement of the finding changed with the paired tests. Before
them the claim was "no model beats the lookup table", which is a null. It is now
"models are measurably worse than the lookup table, with one tie", which is a
positive result about model complexity and a sharper thing to say.

The refuted half remains the most valuable result: the algorithm choice moves
at most €9/yr while automated timing at all moves ~€210/yr, so a
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

So H2 is really three tests: a price test (was it anticipated), a forecast-error
test (did demand actually deviate), and a real-time price test (did the auction
misprice it). The World Cup study runs all three: M4 is the day-ahead price test,
M7 (on ENTSO-E load data) the forecast-error test, and R3 (on the reBAP spread,
`wc_intraday.py`) the real-time test. R3 is the only one where an unanticipated
shift could survive, because the day-ahead auction has already closed by then.

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

The real-time test (R3, added 2026-07-30, 34 of 35 match days covered) is the
third null and the most instructive one, because its headline is not null. The
raw matched comparison reads +2.18 ct/kWh with placebo p=0.005, and the Germany
subset +6.34 with p=0.033, the only significant figure anywhere in the World Cup
work. Neither survives the within-day contrast: +1.20 ct/kWh at p=0.118 pooled,
+1.90 at p=0.452 for Germany, drift-robust family-wise p=0.455. The mechanism is
visible in the raw data rather than inferred: match days sit +0.43 ct/kWh
above their matched control days across all 24 hours, which a two-to-four-hour match cannot
cause, and the effect concentrates in June (+2.48 over 20 days) while nearly
vanishing in July (+0.89 over 14 days) even though July is the knockout stage
with the larger audiences. All four Germany match days fall in June, which is
why that subset is the most drift-exposed number in the study rather than the
most interesting one.

The honest summary: any World Cup effect on the German market is smaller than
~2.2 ct/kWh in day-ahead price, not separable from seasonal drift in load, and
not separable from day-level drift in the real-time spread. One caveat on
multiplicity, since it cuts against the project's own framing: the reBAP spread
is the third outcome variable tried on a single event, and the family-wise
guards only span subsets within each study, never across the three, so a nominal
p=0.005 on the third attempt is worth less than it reads. It does not change the
conclusion, because the drift-robust estimates are null regardless.

## Milestones

All ten milestones are built. Their descriptions, run commands, and the
reasoning for their order live in the README under "What it does" (three
strands: A, see the market, M1-M3; B, the event question, M4/M6/M7/M9; C, the
forecast question, M5/M8/M10). They are not repeated here. How each maps to
the hypotheses: M5 tests H1a/H1b, M8 prices the verdict, M10 settles both on a
full year; M4 tests the anticipation half of H2, M7 the surprise half, M9
calibrates the instrument. Two later studies sit beside the ten: R9 (day-ahead
versus real-time reBAP, the market-quality question) and R3 (`wc_intraday.py`,
the World Cup tested on that real-time signal, the third and last H2 test).

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

Per-day effect estimates share control days (a pool of ~31 controls serves ~35
match days, 5 each), so they are positively correlated and plain t-statistics
are optimistic. The permutation tests are the trustworthy inference; the t's
are descriptive.

The drift is measurable, not just suspected, and it is large enough to
manufacture a significant result on its own. On the reBAP spread, match days run
+0.43 ct/kWh above their matched control days across all 24 hours (day medians
+0.32 versus −0.11; the gap widens to about +0.69 against every non-match day in
the surrounding period). Since no match occupies 24 hours, that is period drift
by construction, and any estimator that
compares match hours across days inherits it. Two consequences carried
throughout: every effect must be reported under both the headline and the
within-day estimator, and any subset whose days cluster in one part of the
window is more drift-exposed than the pooled estimate rather than less. The
Germany subset is the worst case, because all four of its days fall inside the
tournament's first half.

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
  choice moves at most €9/yr while automated timing at all moves ~€210/yr.
  Building a better model would chase the small number.
- No live or real-time operation. This stays an offline study; deployed
  realism enters only as archived forecasts (R6).

### Now

(Empty. R1 and R2 were delivered on 2026-07-22 and R3 on 2026-07-30, see the
changelog; the next items to pull are R5 and R10.)

### Delivered, kept here for the record

**R3. Test H2 in a market where surprise can exist** (path two)
**Delivered 2026-07-30. Verdict: third bounded null; see "Where H2 landed".**
One residual: match day 2026-07-18 is not yet in the quality-assured reBAP
series. Re-run `wc_intraday.py` after a later fetch to close it; on 34 of 35
days the drift-robust estimate is nowhere near significance, so the missing day
is unlikely to change the reading.
- Outcome: the surprise half of H2 gets its proper market-side test. The
  day-ahead price is fixed at 12:00 the day before delivery, so M4 could only
  ever measure anticipation; the real-time price is where an unanticipated
  demand shift would show. The signal is the reBAP (the German imbalance price),
  the zone-local real-time price built for R9.
- Why next: it closes a known logical hole in H2 rather than opening a new
  question, and the data layer now exists (R9).
- Answer looks like: event-hour reBAP deviation (or reBAP-minus-day-ahead
  spread) with MDE, run through the same robustness battery as M9.
- Depends on: the reBAP fetch built for R9 (`intraday_fetch.py`, netztransparenz
  WebAPI). ENTSO-E does NOT publish German intraday or imbalance prices
  (established in R9), so the earlier "ENTSO-E fetch, same token" plan is void.
- Who benefits: methodology; a flexibility company trading imbalance.

### Next

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
- Progress (2026-07-23, figures refreshed 2026-07-30): the real-time /
  aggregator slice is priced from R9 (in README). Two distinct value pools, not
  simply additive: the consumer's day-ahead automation is worth ~210 EUR/yr
  (M10) and needs no market access; the real-time flexibility gap is worth
  ~122 EUR/yr (R9 settlement regret, indicative not bankable since reBAP is a
  settlement price), capturable only by whoever holds the balancing position, so
  at aggregate scale, not per household. Conclusion stated plainly: no
  consumer-facing intraday product; intraday value is a B2B aggregation play.
  One refinement from the mean/median split: the 122 EUR/yr is an annual total
  and is earned unevenly, with 32% of it in the worst 5% of days (median day
  1.73 ct/kWh, about 69 EUR/yr at the same volume). For an aggregator that is a
  readiness requirement rather than a steady margin, which is a product
  statement, not just a statistical one. The consumer-configuration set and the
  storage-sizing statement remain open.

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

(R9 delivered on 2026-07-23; it left the Later queue. Its milestone
description lives in the README and the verdict is in the changelog below.)

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
5. ~~(Ladder) One local rerun of `forecast_ladder.py` to populate the
   window-size comparison and the accuracy-vs-decision-value blocks.~~ Done
   2026-07-30. `by_n`, `daily`, `accuracy` and `paired_vs_lookup` are all
   populated on 353 test days; the paired tests sharpened H1b (see its verdict).
   Verdict aggregates stay pinned to n=3.
6. (R3) Re-run `wc_intraday.py` once 2026-07-18 appears in the quality-assured
   reBAP series, to close the last uncovered match day.
7. (Housekeeping) Add `wc_intraday.png` to `.gitignore`. Every other generated
   PNG is ignored and no page references them, so it should not be tracked.

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

- 2026-07-30: R3 delivered, and it is the study that most needed its own
  robustness check. Headline: match-hour reBAP-minus-day-ahead +2.18 ct/kWh,
  placebo p=0.005 on 34 of 35 covered match days. Drift-robust within-day
  contrast: +1.20 ct/kWh, p=0.118. The Germany subset headline (+6.34 ct/kWh,
  p=0.033) was the only significant figure in the whole World Cup body of work
  and collapsed to +1.90 ct/kWh at p=0.452 once the same contrast was applied,
  with a within-day inter-quartile range of 10.56 ct/kWh on four days. Two
  method changes followed from that and are now permanent: the Germany subset
  gets its own within-day estimate (it previously had none, which is exactly the
  subset where it mattered most), and the family-wise guard is reported on both
  estimators, with the drift-robust one designated as the number to quote.
  Verdict: third bounded null for H2. The drift itself was quantified rather
  than assumed, at +0.43 ct/kWh across all 24 hours of match days versus their
  matched controls, and it concentrates in June (+2.48 ct/kWh over 20 days)
  while July, the knockout stage with the larger audiences, is nearly flat
  (+0.89 over 14 days). Both diagnostics are now emitted into the results JSON
  (`day_level_drift`, `calendar_split`) and plotted, rather than living in a
  throwaway script. Also filed: the reBAP spread is the third outcome variable
  tried on one event and no correction spans the three studies, so the nominal
  headline p-values are optimistic. Conclusion unaffected, since the drift-robust
  estimates are null.
- 2026-07-30: a fetch-window bug was found and fixed, and it had been silently
  truncating the R9 window for six days. `intraday_fetch.py` derived its window
  from the extent of `year_prices.csv`, which was last fetched 2026-07-14 and
  therefore ended 2026-07-12. That end date became the reBAP request's end date,
  so 13-19 July was never requested, and the day-ahead/reBAP intersection would
  have dropped it even if it had been. The symptom looked exactly like the
  documented reBAP publication lag, and the meta JSON recorded the run as a
  successful `live` fetch with no hint of truncation. Fix: `window_from` now
  computes how far behind today the day-ahead reference ends, warns with the
  commands that repair it, records the staleness in `intraday_meta.json` so a
  truncated window is auditable afterwards, and flags explicit end dates that
  run past the day-ahead extent. Covered by three offline cases in
  `--selftest`. After refetching (`year_fetch.py 2025-07-12 2026-07-28`, then
  `intraday_fetch.py --since auto`) the window runs to 2026-07-28, 8,925 hours,
  and R3 gained three match days. Lesson recorded because it generalises: a
  derived window silently inheriting another file's staleness is a failure mode
  the "files are the interface" design invites, and the guard belongs on every
  fetcher that reads another fetcher's output.
- 2026-07-30: full-year data refresh, and the R9 aggregates barely moved, which
  is itself the useful result. The window grew 16 days (366 to 372 days of
  ranking data, 8,781 to 8,925 hours). Median spread +0.051 to +0.041 ct/kWh,
  IQR 4.777 to 4.787, volatility ratio 1.908 to 1.907, correlation 0.5439 to
  0.5448, cheapest-three survival 12.6% in both. Settlement regret 2.976 to
  3.029 ct/kWh (119.5 to 122 EUR/yr). The forecast ladder moved from 337 to 353
  test days: climatology 203 to 210 EUR/yr saved against a ceiling that moved
  219 to 225, so the "~93% of perfect foresight" headline holds at 93%. The
  event-study instrument check also refreshed: weekend effect -3.93 to
  -4.08 ct/kWh (n=106 to 110, t=-13.52 to -14.22), holiday effect unchanged at
  -6.91 ct/kWh with permutation p 0.013 to 0.0035.
- 2026-07-30: settled how to report the settlement regret, after an internal
  argument that reversed once. The study leads with medians everywhere because
  the spread is fat-tailed, so the annual euro figure using a mean looked
  inconsistent. It is not: an annual figure is a sum over days and a sum is the
  day count times the mean, so the mean is the correct input for anything
  annual, and the median annualised (69 EUR/yr) is not an annual total but "a
  typical day, 365 times", which nobody experiences. Both numbers are now
  reported with their scope attached, mean for annual totals and "median day"
  otherwise, plus the concentration statistic that explains the gap between
  them: the worst 5% of days carry 32.5% of the annual total.
  `intraday_analysis.py` emits `settlement_regret_median_ct_per_kwh` and
  `regret_share_from_top_5pct_days` so the pages can state both without
  hardcoding either.
- 2026-07-23: R9 delivered on real reBAP data. The netztransparenz fetch was run
  for the trailing year (2025-07-12 to 2026-07-12, 8,781 hours) and
  `intraday_analysis.py` run on it; `intraday_results.json` holds the aggregates
  and `intraday.html` computes the verdict live from them. Verdict: day-ahead is
  nearly unbiased in level (median reBAP-minus-day-ahead spread +0.05 ct/kWh, and
  the systematic hour-of-day bias stays within about 1 ct/kWh, slightly cheap
  midday and slightly dear in the evening ramp), but a poor proxy for real time
  in variance and in ranking. Real-time is 1.9x as volatile as day-ahead (2.3x in
  winter, 1.5x in summer), the two are 0.54 correlated, and the three cheapest
  day-ahead hours are all still cheapest at real time on only 12.6% of days
  (settlement regret about 2.98 ct/kWh, ~120 EUR/yr at 11 kWh/day, a flexibility
  hypothetical, since reBAP is a settlement price, not a tradeable quote). Product
  reading: no consumer-facing intraday product, because the household is billed
  day-ahead and the median gap is zero; the real-time value is variance, not a
  harvestable spread, and is capturable only by whoever holds the balancing
  position, so it is a B2B aggregation play, not a household one. R9 left the
  Later queue; all numbers match `intraday_results.json`. R3's dependency moved
  onto this reBAP fetch, since ENTSO-E carries no German intraday or imbalance
  price. This priced the real-time slice of R5 (see its Progress note).
- 2026-07-23: R9 built against the reBAP price, after a probe corrected a wrong
  data-source assumption. The 2026-07-21 entry filed R9 expecting ENTSO-E to
  serve intraday and imbalance prices under the existing token; it does not. A
  probe (`intraday_probe.py`) showed ENTSO-E returns the day-ahead series for the
  intraday "A07" query and "no matching data" for the imbalance (A85) query on
  every German control-area domain and every window back to 60 days. Germany's
  real-time price, the reBAP, is published on netztransparenz.de instead, so R9
  is now day-ahead versus reBAP: a single, zone-local real-time signal.
  `intraday_fetch.py` pulls the reBAP from the netztransparenz WebAPI (OAuth2
  client credentials, endpoint `NrvSaldo/reBAP/Qualitaetsgesichert`, CSV
  "Format 9", UTC and EUR/MWh converted to Europe/Berlin and ct/kWh);
  `intraday_analysis.py` reports the day-ahead bias by hour, the real-time
  volatility by season, and whether the three cheapest day-ahead hours survive to
  real time, all with medians and inter-quartile ranges because the price is
  fat-tailed. `intraday.html` shows it, verdict computed live from the JSON. The
  study is built, wired into the pipeline, and parser-tested against the
  documented sample (`intraday_fetch.py --selftest`), but the verdict awaits a
  real reBAP fetch; the numbers are synthetic until then. Framing kept honest:
  the household is billed at day-ahead regardless, so R9 cannot move the household
  verdict and its euro figure is a flexibility hypothetical.
  Implications for the roadmap: R3 (the event-side surprise test) will need to
  take its intraday or imbalance signal from netztransparenz too, not ENTSO-E, so
  its "Depends on" is the reBAP fetch rather than an ENTSO-E intraday fetch. Data
  handling: the reBAP carries no explicit reuse licence, so the raw series
  (`intraday_prices.csv`) is gitignored and never committed and only the derived
  aggregates (`intraday_results.json`) are; a `NOTICE` file and a README
  attribution section record provenance (ENTSO-E and Open-Meteo are CC-BY 4.0).
  Operational: the reBAP fetch is kept out of `run_all.py` (it backfills a year
  and the source only updates a few times a month), runs on demand with an
  incremental `--since` mode that never clobbers real data with synthetic, and
  stays under the WebAPI's two-requests-per-second limit with a warning before it
  would approach it.
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
