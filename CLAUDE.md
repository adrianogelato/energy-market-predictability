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
- `python -m http.server 8000` — preview the pages (never open via file://)
- `N_PERM=200 python wc_permutation.py` — quick permutation smoke run

## Hard rules

- NEVER run `wc_fetch_data.py` or `entsoe_fetch.py` speculatively: on network
  or token failure they fall back to SYNTHETIC data and overwrite the real
  CSVs. `run_all.py` contains the guard logic; use it.
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
event_study_results.json, forecast_ladder.json. GitHub Actions commits a fresh
results.json to main daily at 14:00 UTC — `git pull --rebase` before pushing.

Three strands: A = pipeline (M1-M3), B = event studies (M4/M6/M7/M9,
matched comparable-days + placebo tests), C = forecasting value (M5/M8/M10).
Pages: index.html (one-pager, computes numbers live from JSONs; hand-written
verdicts have data-driven guards — preserve them), tariff.html (daily demo),
worldcup.html (event study, verdict-first).

## Chart design (all figures on the pages and in `analysis.py`)

Every chart must be self-explanatory in isolation, readable without the
surrounding prose.

- **Title**: states what the chart shows.
- **Caption**: states the takeaway, so the finding is clear without reading
  the body text.
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
