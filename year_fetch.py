"""
Fetch a FULL YEAR of day-ahead prices and weather for the value-of-complexity
study (ROADMAP backlog item 4).

    python year_fetch.py              # default: the 365 days ending ~2 days ago
    python year_fetch.py 2025-07-01 2026-06-30

Writes year_prices.csv, year_weather.csv, year_meta.json. Deliberately
separate from wc_fetch_data.py and its files: this fetch must never touch the
World Cup study's data, and unlike the pipeline fetchers it has NO synthetic
fallback. A study about real seasonal behaviour is worthless on generated
data, so this script fails loudly instead.

Design decisions
----------------
15-minute data: since 1 Oct 2025 the day-ahead auction trades quarter-hours,
and the API may return sub-hourly entries for part of the window. First pass
of the study is hourly (the cheap-hours product question is hourly), so
sub-hourly entries are averaged into their hour. The quarter-hour version is
backlog item 6.

Timezones: the window spans a CEST->CET->CEST double switch, so timestamps are
converted per-entry via Europe/Berlin. A fixed offset would be an hour wrong
for the whole winter.

Chunking: prices are requested in ~30-day chunks to stay well inside any API
range limits, then de-duplicated.
"""

import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import requests

HERE = Path(__file__).parent
BERLIN = ZoneInfo("Europe/Berlin")
LAT, LON = 52.52, 13.40   # Berlin, same single-point proxy as the WC study


def to_ms(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=BERLIN).timestamp() * 1000)


def fetch_prices(start, end):
    """Hourly ct/kWh for [start, end], averaging any sub-hourly entries."""
    by_hour = defaultdict(list)
    chunk = dt.timedelta(days=30)
    d = start
    while d <= end:
        d2 = min(d + chunk, end + dt.timedelta(days=1))
        r = requests.get("https://api.awattar.de/v1/marketdata",
                         params={"start": to_ms(d), "end": to_ms(d2)}, timeout=60)
        r.raise_for_status()
        for e in r.json()["data"]:
            t = dt.datetime.fromtimestamp(e["start_timestamp"] / 1000,
                                          tz=BERLIN).replace(tzinfo=None)
            by_hour[t.replace(minute=0, second=0)].append(e["marketprice"] / 10.0)
        print(f"  prices {d} .. {d2}: {len(by_hour)} hours total")
        d = d2
    return {t: mean(v) for t, v in sorted(by_hour.items())}


def fetch_weather(start, end):
    """Hourly temp, cloud, wind, radiation from the open-meteo archive."""
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": LAT, "longitude": LON,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": "temperature_2m,cloud_cover,windspeed_10m,shortwave_radiation",
        "timezone": "Europe/Berlin",
    }, timeout=120)
    r.raise_for_status()
    h = r.json()["hourly"]
    out = {}
    for iso, temp, cloud, wind, rad in zip(
            h["time"], h["temperature_2m"], h["cloud_cover"],
            h["windspeed_10m"], h["shortwave_radiation"]):
        if temp is None:
            continue
        out[dt.datetime.fromisoformat(iso)] = (temp, cloud, wind, rad)
    print(f"  weather: {len(out)} hours")
    return out


def main():
    if len(sys.argv) == 3:
        start = dt.date.fromisoformat(sys.argv[1])
        end = dt.date.fromisoformat(sys.argv[2])
    else:
        end = dt.date.today() - dt.timedelta(days=2)   # archives lag ~2 days
        start = end - dt.timedelta(days=365)
    print(f"Fetching {start} .. {end} (no synthetic fallback; failures are fatal)")

    prices = fetch_prices(start, end)
    weather = fetch_weather(start, end)
    common = sorted(set(prices) & set(weather))
    if len(common) < 24 * 200:
        raise SystemExit(f"Only {len(common)} overlapping hours; that is not a year. Aborting.")

    with open(HERE / "year_prices.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "ct_per_kwh"])
        for t in common:
            w.writerow([t.isoformat(), f"{prices[t]:.3f}"])
    with open(HERE / "year_weather.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "temp_c", "cloud_pct", "wind_kmh", "radiation_wm2"])
        for t in common:
            temp, cloud, wind, rad = weather[t]
            w.writerow([t.isoformat(), temp, cloud, wind, rad])
    with open(HERE / "year_meta.json", "w") as f:
        json.dump({"window": {"start": start.isoformat(), "end": end.isoformat()},
                   "hours": len(common), "data_source": "live",
                   "fetched_at": dt.datetime.now().isoformat(timespec="minutes")},
                  f, indent=2)
    print(f"Wrote year_prices.csv / year_weather.csv ({len(common)} hours, "
          f"{len(common)//24} full-ish days) and year_meta.json")
    print("Next: python forecast_ladder.py")


if __name__ == "__main__":
    main()
