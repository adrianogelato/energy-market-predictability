# Working hypotheses and backlog

Two documents, two jobs, no duplication. The README is the presentation layer:
the story, the findings, what each milestone does and how to run it, and the
design decisions. This file is the working ledger: the hypotheses and their
verdicts, what an answer has to look like, the limitations that constrain every
result, and the prioritized backlog. If a milestone description is what you
want, it lives in the README's three strands, not here.

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
test (did demand actually deviate). The current World Cup study does only the
price test; the forecast-error test needs load data.

## What an answer looks like

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

Where H2 landed (interim, tournament ends 19 July): no robust effect. The price
test reads +0.89 ct/kWh (t=0.97, MDE ≈ 2.6 ct/kWh) and collapses to +0.14 under
the within-day contrast. The load forecast-error test's one marginal subset
(overnight, +833 MW, t=2.04) fails the placebo test (subset p=0.228,
family-wise p=0.401) and flips sign under the within-day contrast (−758 MW),
which says the error series drifts across the window in a way neither estimator
fully removes. The honest summary: any World Cup effect on the German market is
smaller than ~2.6 ct/kWh in price and not separable from seasonal drift in load.

## Milestones

All ten milestones are built. Their descriptions, run commands, and the
reasoning for their order live in the README under "What it does" (three
strands: A, see the market, M1-M3; B, the event question, M4/M6/M7/M9; C, the
forecast question, M5/M8/M10). They are not repeated here. How each maps to
the hypotheses: M5 tests H1a/H1b, M8 prices the verdict, M10 settles both on a
full year; M4 tests the anticipation half of H2, M7 the surprise half, M9
calibrates the instrument.

## Limitations to carry throughout

The control pool is seasonal, and this is the binding constraint. Because
matches run almost daily from 11 June to 19 July, nearly all non-match control
days fall in mid-May to early June, which is cooler than July. Weather-matching
helps but is stretched across a seasonal gap. The data shows the damage
directly: on "comparable" days the midday load forecast error runs around
−3,700 MW versus −1,100 MW on match days, at hours where no matches happen, so
part of any measured "match effect" is period drift, not matches. The
within-day difference-in-differences contrast removes additive day-level drift,
but the drift here changes the intraday *shape* (midday solar forecast bias),
which is why the main estimate and the DiD disagree in sign for load. Widening
the window into adjacent summer weeks or matching on solar radiation directly
is the real fix.

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

## Backlog and parked ideas

Two paths forward. The items below sort into two research paths that share one
spine. Path one, forecasting-algorithm complexity (items 4, 8): how much of the
price shape is predictable, and how much model does that take? Path two,
event-effect measurement (items 1, 2, 3, 5, 7): do scheduled events move the
market beyond its predictable baseline? Item 6 (15-minute resolution) serves
both. The shared spine: an event effect is nothing but a deviation from a
counterfactual baseline, so the better the forecasting model from path one,
the sharper the event tests in path two. The paths converge in a model-based
event study, where the forecaster itself replaces comparable-days matching as
the control.

In priority order. The first block matters most; the older ideas follow.

1. Post-tournament rerun. The tournament ends 19 July 2026; all World Cup
   results are interim until the fetch and the full analysis chain are re-run
   on the complete window. Split out Germany's matches as their own subset:
   a Germany knockout match is the single best-powered event in the data.

2. Widen the fetch window into spring. This is the structural fix for the
   seasonal control gap described in Limitations, and it simultaneously turns
   the n=1 holiday test into a real one (Good Friday, Easter Monday, Labour
   Day, Ascension, Whit Monday all land in March-May). Needs a local run of
   `wc_fetch_data.py` with an earlier START_DATE; the refetch also fills the
   new wind and radiation columns the matching engine already knows how to
   use. When widening, enable the season guard in `matching.py`
   (SEASON_GAP_MAX_DAYS, around 21 days) so controls stay seasonal neighbours.

3. Test the event hypothesis in the market where surprise can exist. The
   day-ahead price is fixed at 12:00 the day before delivery, so M4 could only
   ever measure anticipation. Intraday or imbalance prices are where an
   unanticipated demand shift would show; adding either (both on ENTSO-E)
   would complete H2 properly.

4. DONE: the value-of-complexity study (`year_fetch.py`,
   `forecast_ladder.py`, results in `forecast_ladder.json` and the README's
   milestone 10 section). The curve flattens at rung one: a 28-day rolling
   lookup table wins the full year outright against five more complex models
   including gradient boosting, all fed perfect weather. Verdicts under
   "Working hypotheses". Two follow-ups remain open here: the
   deployed-realism variant (score against archived weather *forecasts*
   instead of actuals; can only widen the lookup table's lead), and note
   that the full-year files (`year_prices.csv`, `year_weather.csv`) now also
   provide the widened control pools and real holiday test that item 2 asks
   for — the event studies just need pointing at them.

5. A second event: the Milano Cortina Winter Olympics, 6-22 February 2026.
   Parked because it is the reuse test for the whole methodology (the M9
   engine plus an events CSV is exactly the intended vehicle), and because it
   varies the dimensions the World Cup could not. It is a winter market, where
   heating demand and scarce daylight drive the price shape instead of solar.
   And unlike the North American World Cup, the host sits in Germany's own
   timezone (CET), so finals landed in German daytime and prime-time viewing
   hours: if a TV effect exists anywhere, this is the well-powered place to
   look. Three design notes captured now so they are not rediscovered later.
   First, the February window is already covered by item 4's full-year fetch,
   so no new price or weather data is needed. Second, the event-hours definition is the
   hard part: the Olympics run all day for 17 days, and flagging every hour
   would dilute exposure to nothing; curate the high-German-viewership
   sessions (biathlon, ski jumping, medal finals) into the events file rather
   than taking the full schedule. Third, the control pool can sit on BOTH
   sides of the event (late January and March), avoiding the one-sided
   seasonal drift that undermined the World Cup study. One code fix required:
   `entsoe_fetch.py` hardcodes the summer +2 h CEST conversion and needs
   proper Europe/Berlin handling before it can serve a February window.

6. Move to 15-minute resolution. The European day-ahead auction (SDAC)
   switched to 15-minute products on 1 October 2025, so the entire study
   window is already quarter-hourly at the source. Two payoffs. For the event
   studies: the classic TV-pickup (kettles at half-time and full-time) is a
   minute-scale phenomenon that hourly averaging dilutes toward zero;
   quarter-hours are the first resolution where it could actually appear.
   Cheapest of all, `entsoe_fetch.py` already receives quarter-hourly German
   load and deliberately averages it to hourly, so the sharper M7 test needs
   no new data source, only the averaging removed. For the tariff model:
   check whether aWATTar's API now returns quarter-hour prices; if so, the
   cost model's EV window and the forecaster's target become 15-minute
   blocks, which is also how a real smart-charging product would trade.

7. Cross-country dose-response: do other nations' markets tell a different
   story? Germany dropped out early, but several European teams kept playing,
   which creates treatment variation the single-zone study lacks: the same
   match hours, watched intensely in one country and not in another. The
   design writes itself with existing tools: ENTSO-E carries load and
   day-ahead load forecast for every European zone under the same token,
   open-meteo covers any city, and the matching engine plus M9 event engine
   are zone-agnostic. Use the load forecast error, not price, as the signal:
   day-ahead prices are coupled across European zones, so a price effect
   smears across borders, while the forecast error is zone-local. The sharp
   test: a semifinal country's forecast error during its match hours versus
   Germany's (neutral) in the same hours, with each country's own
   weather-matched controls. Same-hours cross-zone comparison also nets out
   Europe-wide common shocks, which the single-zone design cannot.

8. Diagnostic depth for the ladder study (path one). The current outputs are
   aggregates; reviewing how the conclusion was reached requires seeing the
   fits themselves. Add per-rung diagnostic plots: predicted versus actual
   24-hour price curves overlaid for sample days; specifically each rung's
   best-fit and worst-fit day (by daily regret, and separately by price RMSE,
   since a rung can rank hours correctly while missing levels); and a
   residual-by-hour profile per season showing where each model
   systematically misses. Same transparency standard the matching engine got
   with its pairings table: make "the lookup table wins" inspectable day by
   day, not just believable in aggregate.

Older ideas, still parked:

Module separation beyond matching: aWATTar price data, ENTSO-E load data, and
event data could each be an inspectable component (the comparable-day matching
already is: `matching.py`).

Raw-data visibility: a way to browse the underlying hourly data (prices, load,
weather, forecast error) directly, not only the aggregated results.

Done since this list was first written: hour-alignment fix in the cost model,
timezone-explicit fetches (CI-safe), sample-SD t-statistics, minimum detectable
effects reported with every null, within-day difference-in-differences
robustness checks, family-wise permutation test across subsets, permutation
p-values surfaced on the results page, and the comparable-day matching engine
extracted into `matching.py` with richer market-specific features (wind,
radiation, temperature max), day-type classes with holiday exclusion, and the
exact pairings exposed in the JSONs and on the page.

## Data sources

aWATTar for day-ahead prices (free, no key, equals EPEX SPOT). open-meteo for
weather, historical archive and forecast (free, no key; temperature, cloud,
wind, shortwave radiation). ENTSO-E Transparency
Platform for load, load forecast, and generation mix (free, needs a token),
added at M6. Match schedule in wc_matches.csv, converted to German local time (CEST).
