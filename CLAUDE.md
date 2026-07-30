# CLAUDE.md

Portfolio project (PM/PO job search, energy domain): how predictable is the
German day-ahead power market, what is a forecast worth, and can scheduled
events (World Cup 2026) move it? Read `README.md` (presentation: story,
findings, design decisions) and `ROADMAP.md` (working ledger: hypotheses with
verdicts, limitations, the Now/Next/Later roadmap, task backlog, changelog)
before changing anything.
Content lives in exactly one of the two; keep it that way.

## Commands

- `python run_all.py --skip-fetch` — full offline pipeline on existing CSVs
- `python run_all.py` — with live fetches (network)
- `python year_fetch.py && python forecast_ladder.py` — full-year ladder study
- `python intraday_fetch.py && python intraday_analysis.py` — day-ahead vs
  real-time reBAP study (R9); needs `year_prices.csv` and netztransparenz
  credentials (`IPNT_CLIENT_ID`/`IPNT_CLIENT_SECRET` in `.env`)
- `python wc_intraday.py` — World Cup match hours in the reBAP spread (R3);
  reads `intraday_prices.csv`, so run the R9 fetch first
- `python intraday_fetch.py --selftest` — validate the reBAP CSV parser and the
  stale-reference window guard, offline
- `python -m http.server 8000` — preview the pages (never open via file://)
- `N_PERM=200 python wc_permutation.py` — quick permutation smoke run

## Hard rules

- NEVER run `wc_fetch_data.py`, `entsoe_fetch.py`, or `intraday_fetch.py`
  speculatively: on network, token, or credential failure they fall back to
  SYNTHETIC data and overwrite the real CSVs. `run_all.py` contains the guard
  logic; use it.
- Data-source facts (proven by probes, do not re-litigate): ENTSO-E does NOT
  publish German intraday-auction or imbalance prices (A44/A07 just returns
  day-ahead; A85 returns no data for every DE domain). The German real-time
  price (reBAP) comes from the netztransparenz.de WebAPI instead
  (`intraday_fetch.py`, endpoint `NrvSaldo/reBAP/Qualitaetsgesichert`, OAuth2
  client-credentials, CSV "Format 9", values in UTC and EUR/MWh).
- NEVER publish an absolute reBAP-derived value for a specific date and hour
  window. `wc_results.json` commits the day-ahead price per match day and window,
  so an absolute reBAP-minus-day-ahead spread beside it lets the two committed
  files be added to reconstruct the reBAP level (measured: exact on some days,
  ~1.4 ct/kWh mean error). netztransparenz grants no reuse licence, so
  `wc_intraday.py` publishes the effect delta only, which is a difference of
  differences against unpublished control days. Pooled aggregates (hour-of-day
  profiles, seasonal ratios) are fine; dated ones are not. Rationale in NOTICE.
- `year_fetch.py` has no synthetic fallback by design; keep it that way.
- Every number cited in README.md, ROADMAP.md, and the verdict sentences in
  the HTML pages must match the committed result JSONs. After changing any
  analysis, rerun the offline pipeline and reconcile all cited numbers.
- Timezones: always convert via `ZoneInfo("Europe/Berlin")`, never naive
  `fromtimestamp()` (CI runners are UTC) and never fixed offsets (the data
  spans CEST/CET switches).
- Dependency policy: core stays requests+numpy+matplotlib. scikit-learn is
  optional (gbm rung only); scripts must degrade gracefully without it.
- `matching.py` is the single definition of "weather-comparable day"; studies
  must not grow private matching logic.
- Statistics conventions: sample SD (n-1); every null reports its minimum
  detectable effect; permutation tests are the trustworthy inference (t's are
  descriptive and optimistic due to shared control days); family-wise max-|t|
  when multiple subsets are examined.

## Architecture

Files are the interface (no DB, deliberate; see README). Fetchers write CSVs,
analyses read CSVs and write JSONs, pages read JSONs in the browser. Committed
JSONs (pages depend on them): results.json, wc_results.json,
wc_load_results.json, wc_permutation_results.json, forecast_value.json,
event_study_results.json, forecast_ladder.json, intraday_results.json,
wc_intraday_results.json. GitHub
Actions commits a fresh results.json to main daily at 14:00 UTC — `git pull
--rebase` before pushing.

Three strands: A = pipeline (M1-M3), B = event studies (M4/M6/M7/M9,
matched comparable-days + placebo tests), C = forecasting value (M5/M8/M10).
The market-quality strand (R9) sits beside them: `intraday_fetch.py` +
`intraday_analysis.py` compare the day-ahead price against the real-time reBAP
price to ask how good the market's own day-ahead forecast is. `wc_intraday.py`
(R3) reuses that reBAP layer to run the World Cup against the real-time price,
the third and last H2 test and the only one where an unanticipated shift could
survive the day-ahead auction closing. All three H2 tests are bounded nulls.
Pages share `site.css`, `bound.js`, `chart-theme.js` and `page-nav.css` /
`page-nav.js`; see "Shared front-end files".
Pages: index.html (one-pager, computes numbers live from JSONs; hand-written
verdicts have data-driven guards — preserve them), tariff.html (daily demo),
worldcup.html (event study, verdict-first), intraday.html (day-ahead vs
real-time reBAP, R9; verdict computed live from the JSON, no hardcoded numbers).

## Shared front-end files

- `site.css` is the single definition of the visual system (tokens, type
  scale, cards, notes, tables, verdict boxes). Pages carry an inline `<style>`
  for their own DATA colours only; never re-add page-level copies of the
  chrome. Design direction is "bounded null": chrome stays monochrome and only
  spends colour when a result clears its bound, so an honest null is never
  dressed up as a finding.
- `bound.js` is the signature component (`drawBound`): a caliper scale whose
  jaws are the minimum detectable effect (or placebo ceiling) and whose dot is
  the measured effect. It derives the "null"/"effect" word from the dot's
  position, so it cannot contradict the JSON it was handed. Values must always
  come from a committed result JSON.
- `chart-theme.js` sets Chart.js defaults (fonts, greys, grid). Load it in
  `<head>` right after the Chart.js tag and WITHOUT `defer`: pages build charts
  from an inline script at the end of `<body>`, which runs before any deferred
  script. Series colours stay in the pages, because they are data.
- Type: IBM Plex Sans for prose, IBM Plex Mono for every number, unit, label
  and caption. Mono marks measured or machine-derived text.
- The matplotlib figures deliberately keep the default face; pinning IBM Plex
  would need the font on every machine including the CI runner.
- Tables are scroll containers (`display:block; overflow-x:auto` in
  `site.css`); the page body must never scroll sideways. Verified at 320, 360,
  390, 480 and 768px.
- Every page carries a repo link in `<p class="repo">`, placed as a SIBLING
  after `</footer>` because the pages set `footer.textContent` from JS, which
  would wipe a child.

## The three text blocks

One form per job. A reader must be able to tell what kind of statement they
are reading from its shape alone, so these never swap jobs and no fourth kind
gets invented.

- `.summary` sits directly under a heading, one per section, and holds the
  section's takeaway and any argument about the data. Solid ink left rule.
  Where the takeaway is data-dependent it is an empty `<p id="...">` inside
  the summary that the page fills from a result JSON.
- `figcaption` sits directly under a figure and describes that figure only:
  what is plotted, axes and units, encoding, source, date range, small-n
  caveat. It does not argue; that is the summary's job.
- `.note` is a grey panel for caveats, limits, interim-data warnings and
  method asides, and carries a `data-label` eyebrow naming which it is
  ("Limitation", "Interim data", "Method", "Product implication"). Notes vary
  in job more than the other two, which is why only they are labelled.

Position reinforces form: summaries follow headings, captions follow figures,
notes stand alone.

## Chart design (all figures on the pages and in `analysis.py`)

Every chart must be readable on its own terms: a reader should be able to work
out what is plotted, in what units, from what data, without hunting through the
prose.

- **Title**: states what the chart shows.
- **Caption**: describes the figure. What is plotted, how it is encoded, source,
  range, sample caveats. It does NOT state the takeaway; that belongs in the
  section's `.summary` under the heading. (This reverses an earlier rule that
  put the takeaway in the caption. The cost is that a figure lifted out of the
  page no longer carries its own conclusion; the gain is that captions and
  arguments stopped looking like each other, which was actively confusing.)
- **Legend**: present whenever more than one series is plotted; label series
  explicitly, no reliance on color alone.
- **Axes**: both labeled, with units.
- **Source and range**: note the data source and date range (e.g. "German
  day-ahead prices, 2023-2025").
- **Small-n caveat**: state sample size or noise caveats directly on the chart
  when n is small (matches the existing weekday-effect guard).
- **Color**: consistent palette across all pages and figures.
- **Abbreviations & acronyms**: Abbreviations and acronyms shall be spelled out. Units like ct/kWh or EUR/MWh shall not be spelled out, they are considered known.

## Writing style (all prose: docs, pages, commit messages)

No em dashes. No LinkedIn marketing tone. No inflated phrasing. Findings
first, then evidence. Honest nulls are the product: never soften a "no
effect" and never strip its MDE bound.
