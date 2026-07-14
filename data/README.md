# Source data

Raw reference files kept for provenance. Nothing in the pipeline reads them;
the scripts read the cleaned `wc_matches.csv` in the repository root.

`wc_schedule_source.txt` and `wc_schedule_source.csv` are the raw 2026 FIFA
World Cup match schedule (match number, date, kickoff in ET and stadium-local
time, fixture, group, venue, city) as published by roadtrips.com. They are the
source from which `wc_matches.csv` was built: kickoffs were converted from ET
to German local time (CEST, +6 h) and knockout fixtures were filled in as
results became known.

Web source of world cup schedule: https://www.roadtrips.com/world-cup/2026-world-cup-packages/schedule/