"""
Milestone 4, step 1: gather the raw data for the World Cup price study.

Pulls, for a configurable date range:
  - hourly day-ahead prices from aWATTar   -> wc_prices.csv
  - hourly temperature + cloud cover        -> wc_weather.csv  (open-meteo, free, no key)

Both sources are queried live. If either can't be reached (offline, or the
sandbox this was developed in), the script generates a SYNTHETIC but realistic
dataset so the whole pipeline still runs and can be tested. The synthetic
prices contain a deliberately PLANTED match-hour effect, so wc_analysis.py can
be verified to detect it. Real data has no such planted effect, of course.

Config is at the top. Run:  python wc_fetch_data.py
"""

import csv
import datetime as dt
import random
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BERLIN = ZoneInfo("Europe/Berlin")

HERE = Path(__file__).parent

# ---- Config ----------------------------------------------------------------
# Wide enough that there are plenty of non-match "control" days with similar
# summer weather. The 2026 tournament ran 2026-06-11 .. 2026-07-19.
START_DATE = dt.date(2026, 5, 15)
END_DATE = dt.date(2026, 7, 19)

# Berlin, as a starting-point local weather proxy. Note the mismatch this
# introduces: the price is a whole-bidding-zone (DE-LU) signal, while Berlin
# weather is local. A stronger version would use population-weighted or
# multi-point weather across the zone. Berlin is a deliberate first step.
LAT, LON = 52.52, 13.40

SYNTHETIC_MATCH_EFFECT_CT = 1.5   # ct/kWh bump planted on match hours (synthetic only)
# ----------------------------------------------------------------------------


def to_ms(d):
    # Midnight *Berlin* time, regardless of the machine's zone (a CI runner is UTC).
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=BERLIN).timestamp() * 1000)


def fetch_prices_awattar():
    """Live hourly prices from aWATTar for the window. Returns list of (datetime, ct_per_kwh)."""
    url = "https://api.awattar.de/v1/marketdata"
    params = {"start": to_ms(START_DATE), "end": to_ms(END_DATE + dt.timedelta(days=1))}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    rows = []
    for e in resp.json()["data"]:
        # Explicit Berlin local time; naive fromtimestamp() would be UTC on CI.
        t = dt.datetime.fromtimestamp(e["start_timestamp"] / 1000,
                                      tz=BERLIN).replace(tzinfo=None)
        rows.append((t, e["marketprice"] / 10.0))  # EUR/MWh -> ct/kWh
    return rows


def fetch_weather_openmeteo():
    """Live hourly weather. Returns dict datetime -> (temp, cloud, wind, radiation).

    Wind and shortwave radiation exist for the matching engine (matching.py):
    wind generation moves German prices at least as much as solar, and
    radiation is the actual PV driver that cloud cover only proxies. Weather
    files fetched before these columns existed still work; the matcher just
    falls back to the reduced feature set.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LAT, "longitude": LON,
        "start_date": START_DATE.isoformat(), "end_date": END_DATE.isoformat(),
        "hourly": "temperature_2m,cloud_cover,windspeed_10m,shortwave_radiation",
        "timezone": "Europe/Berlin",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    h = resp.json()["hourly"]
    out = {}
    for iso, temp, cloud, wind, rad in zip(
            h["time"], h["temperature_2m"], h["cloud_cover"],
            h["windspeed_10m"], h["shortwave_radiation"]):
        out[dt.datetime.fromisoformat(iso)] = (temp, cloud, wind, rad)
    return out


def load_match_hours():
    """Set of (date, hour) in German local time (CEST) that had a live match, from wc_matches.csv (if present)."""
    path = HERE / "wc_matches.csv"
    hours = set()
    if not path.exists():
        return hours
    with open(path) as f:
        for row in csv.DictReader(f):
            raw = (row.get("kickoff_cet") or "").strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                start = dt.datetime.fromisoformat(raw)
            except ValueError:
                continue
            # a match occupies roughly two clock hours
            for k in range(2):
                t = start + dt.timedelta(hours=k)
                hours.add((t.date(), t.hour))
    return hours


def all_hours():
    d = dt.datetime(START_DATE.year, START_DATE.month, START_DATE.day)
    end = dt.datetime(END_DATE.year, END_DATE.month, END_DATE.day) + dt.timedelta(days=1)
    while d < end:
        yield d
        d += dt.timedelta(hours=1)


def synth_weather():
    """Plausible late-spring/summer weather per hour (incl. wind, radiation)."""
    import math
    random.seed(42)
    out = {}
    for t in all_hours():
        doy = t.timetuple().tm_yday
        seasonal = 12 + 8 * ((doy - 100) / 100.0)             # warms toward mid-summer
        daily = 6 * -1 * math.cos((t.hour - 15) / 24 * 2 * 3.14159)
        temp = round(seasonal + daily + random.uniform(-2, 2), 1)
        cloud = max(0, min(100, int(random.gauss(45, 30))))
        wind = round(max(0.0, random.gauss(14, 7)), 1)        # km/h
        # daylight bell curve, damped by cloud
        sun = max(0.0, math.sin((t.hour - 5) / 15 * math.pi)) if 5 <= t.hour <= 20 else 0.0
        rad = round(850 * sun * (1 - 0.7 * cloud / 100), 0)   # W/m^2
        out[t] = (temp, cloud, wind, rad)
    return out


def synth_prices(weather, match_hours):
    """Plausible prices, driven by weather, with a planted match-hour effect."""
    import math
    random.seed(7)
    rows = []
    for t in all_hours():
        temp, cloud, wind, rad = weather[t]
        # daily shape: midday solar dip, evening peak
        shape = 9 * math.sin((t.hour - 7) / 24 * 2 * math.pi) + 8
        if 11 <= t.hour <= 14:
            shape -= 5
        # more cloud -> less solar -> higher price; hotter -> a bit more
        # demand; more wind -> more supply -> lower price
        weather_push = cloud * 0.04 + max(0, temp - 20) * 0.15 - wind * 0.08
        noise = random.uniform(-1.5, 1.5)
        price = shape + weather_push + noise
        if (t.date(), t.hour) in match_hours:
            price += SYNTHETIC_MATCH_EFFECT_CT   # <-- planted signal
        rows.append((t, round(price, 2)))
    return rows


def save(rows_prices, weather):
    with open(HERE / "wc_prices.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "ct_per_kwh"])
        for t, p in rows_prices:
            w.writerow([t.isoformat(), f"{p:.2f}"])
    with open(HERE / "wc_weather.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "temp_c", "cloud_pct", "wind_kmh", "radiation_wm2"])
        for t in all_hours():
            temp, cloud, wind, rad = weather[t]
            w.writerow([t.isoformat(), temp, cloud, wind, rad])


def main():
    global END_DATE
    # You cannot fetch data that has not happened yet. Weather archives also lag
    # by a couple of days. So clamp the window end to a few days ago. As the
    # tournament progresses, more of it becomes fetchable.
    latest_available = dt.date.today() - dt.timedelta(days=2)
    if END_DATE > latest_available:
        print(f"NOTE: window end {END_DATE} is beyond available data; "
              f"clamping to {latest_available} (today is {dt.date.today()}).")
        END_DATE = latest_available

    source = "live"
    try:
        weather = fetch_weather_openmeteo()
        prices = fetch_prices_awattar()
        # align: keep only hours present in both
        wset = set(weather)
        prices = [(t, p) for t, p in prices if t in wset]
        if len(prices) < 24 * 10:
            raise RuntimeError(f"only {len(prices)} overlapping hours returned")
    except Exception as e:
        detail = str(e)[:200]
        source = f"synthetic (live fetch failed: {type(e).__name__})"
        print(f"WARNING: live fetch failed -> {type(e).__name__}: {detail}")
        print("Falling back to synthetic data. Check the window and your connection.")
        weather = synth_weather()
        prices = synth_prices(weather, load_match_hours())

    save(prices, weather)
    with open(HERE / "wc_meta.json", "w") as f:
        import json
        json.dump({"data_source": source,
                   "fetched_at": dt.datetime.now().isoformat(timespec="minutes")}, f, indent=2)
    print(f"Data source: {source}")
    print(f"Window: {START_DATE} .. {END_DATE}")
    print(f"Wrote wc_prices.csv ({len(prices)} hours) and wc_weather.csv")
    if source.startswith("synthetic"):
        print(f"NOTE: synthetic prices carry a planted +{SYNTHETIC_MATCH_EFFECT_CT} ct/kWh "
              "match-hour effect for pipeline testing.")


if __name__ == "__main__":
    main()
