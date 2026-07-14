"""
Milestone 6: ENTSO-E load data (actual and day-ahead forecast).

Why this exists
---------------
The World Cup price study (M4) can only tell us whether an effect was
anticipated by the market. The more direct question is whether actual demand
deviated from what was forecast. ENTSO-E publishes both the day-ahead load
forecast and the actual load for the German-Luxembourg zone, so the difference,
the forecast error, is the market's own prediction and its miss. That is the
input for the forecast-error version of the study (M7).

Token
-----
ENTSO-E needs a free API token. Register at https://transparency.entsoe.eu,
email transparency@entsoe.eu with subject "RESTful API access", and the token
appears in your account settings within a few working days. Then expose it:

    export ENTSOE_TOKEN=your-token-here

Never commit the token. This script reads it from the environment only.

Offline / no token
------------------
If the token is missing or the request fails, the script generates a synthetic
load series with a deliberately PLANTED demand bump on match hours (visible only
in actual, not in the forecast), so the M7 analysis can be validated to recover
it. Real data carries no planted bump.

Output: wc_load.csv  (datetime, load_actual_mw, load_forecast_mw, forecast_error_mw)
Run   : python entsoe_fetch.py
"""

import csv
import datetime as dt
import json
import math
import os
import random
from collections import defaultdict
from pathlib import Path

import requests

HERE = Path(__file__).parent

DE_LU = "10Y1001A1001A82H"          # ENTSO-E EIC code for the DE-LU bidding zone
BASE = "https://web-api.tp.entsoe.eu/api"
START_DATE = dt.date(2026, 5, 15)
END_DATE = dt.date(2026, 7, 19)
UTC_TO_CEST = 2                     # the whole study window is summer, i.e. CEST = UTC+2
SYNTH_DEMAND_BUMP_MW = 700         # planted actual-load bump on match hours (synthetic only)


def load_dotenv(path=None):
    """Minimal, dependency-free .env loader: KEY=VALUE lines into the
    environment. Does not overwrite variables already set in the shell, so an
    explicit `export` still wins. The .env file is gitignored and never
    committed."""
    path = path or (HERE / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def token():
    return os.environ.get("ENTSOE_TOKEN")


def period_bounds():
    latest = dt.date.today() - dt.timedelta(days=1)  # actual load lags only slightly
    return START_DATE, min(END_DATE, latest)


def _ln(tag):
    """Local name of an XML tag, ignoring namespace."""
    return tag.split("}")[-1]


def parse_load_xml(xml_text):
    """Parse an ENTSO-E GL_MarketDocument into {hour(CEST) -> MW}, hourly mean."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    buckets = defaultdict(list)
    for ts in root.iter():
        if _ln(ts.tag) != "TimeSeries":
            continue
        for period in ts:
            if _ln(period.tag) != "Period":
                continue
            start, res, points = None, None, []
            for child in period:
                ln = _ln(child.tag)
                if ln == "timeInterval":
                    for t in child:
                        if _ln(t.tag) == "start":
                            start = t.text
                elif ln == "resolution":
                    res = child.text
                elif ln == "Point":
                    pos = qty = None
                    for p in child:
                        if _ln(p.tag) == "position":
                            pos = int(p.text)
                        elif _ln(p.tag) == "quantity":
                            qty = float(p.text)
                    if pos is not None and qty is not None:
                        points.append((pos, qty))
            if not start:
                continue
            start_utc = dt.datetime.fromisoformat(start.replace("Z", "+00:00")).replace(tzinfo=None)
            step = 15 if res == "PT15M" else 60
            for pos, qty in points:
                t_cest = start_utc + dt.timedelta(minutes=step * (pos - 1), hours=UTC_TO_CEST)
                hour = t_cest.replace(minute=0, second=0, microsecond=0)
                buckets[hour].append(qty)
    return {h: sum(v) / len(v) for h, v in buckets.items()}


def fetch_load(process_type):
    """process_type A16 = actual, A01 = day-ahead forecast."""
    s, e = period_bounds()
    params = {
        "securityToken": token(),
        "documentType": "A65", "processType": process_type,
        "outBiddingZone_Domain": DE_LU,
        "periodStart": s.strftime("%Y%m%d") + "0000",
        "periodEnd": (e + dt.timedelta(days=1)).strftime("%Y%m%d") + "0000",
    }
    r = requests.get(BASE, params=params, timeout=120)
    r.raise_for_status()
    return parse_load_xml(r.text)


def all_hours():
    s, e = period_bounds()
    t = dt.datetime(s.year, s.month, s.day)
    end = dt.datetime(e.year, e.month, e.day) + dt.timedelta(days=1)
    while t < end:
        yield t
        t += dt.timedelta(hours=1)


def load_match_hours():
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
            for k in range(2):
                t = start + dt.timedelta(hours=k)
                hours.add((t.date(), t.hour))
    return hours


def synth():
    """Plausible load with a planted match-hour bump in actual (not in forecast)."""
    random.seed(11)
    match_hours = load_match_hours()
    actual, forecast = {}, {}
    for t in all_hours():
        weekday_factor = 1.0 if t.weekday() < 5 else 0.90
        daily = 12000 * math.sin((t.hour - 3) / 24 * 2 * math.pi)  # low at night, peaks daytime
        base = (52000 + daily) * weekday_factor
        forecast[t] = round(base + random.gauss(0, 400), 1)
        bump = SYNTH_DEMAND_BUMP_MW if (t.date(), t.hour) in match_hours else 0
        actual[t] = round(base + random.gauss(0, 400) + bump, 1)
    return actual, forecast


def main():
    load_dotenv()  # pick up ENTSOE_TOKEN from .env if present
    source = "live"
    try:
        if not token():
            raise RuntimeError("ENTSOE_TOKEN not set (shell export or .env)")
        actual = fetch_load("A16")
        forecast = fetch_load("A01")
        common = sorted(set(actual) & set(forecast))
        if len(common) < 24 * 10:
            raise RuntimeError(f"only {len(common)} overlapping hours returned")
        actual = {h: actual[h] for h in common}
        forecast = {h: forecast[h] for h in common}
    except Exception as e:
        source = f"synthetic ({type(e).__name__}: {str(e)[:80]})"
        print(f"NOTE: using synthetic load. Reason -> {source}")
        actual, forecast = synth()

    hours = sorted(set(actual) & set(forecast))
    with open(HERE / "wc_load.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "load_actual_mw", "load_forecast_mw", "forecast_error_mw"])
        for h in hours:
            err = actual[h] - forecast[h]
            w.writerow([h.isoformat(), f"{actual[h]:.1f}", f"{forecast[h]:.1f}", f"{err:.1f}"])

    with open(HERE / "wc_load_meta.json", "w") as f:
        json.dump({"data_source": source,
                   "fetched_at": dt.datetime.now().isoformat(timespec="minutes")}, f, indent=2)

    errs = [actual[h] - forecast[h] for h in hours]
    print(f"Data source: {source}")
    print(f"Wrote wc_load.csv ({len(hours)} hours), {hours[0]} .. {hours[-1]}")
    print(f"Mean forecast error: {sum(errs)/len(errs):+.0f} MW "
          f"(actual minus day-ahead forecast)")
    if source.startswith("synthetic"):
        print(f"NOTE: synthetic actual load carries a planted +{SYNTH_DEMAND_BUMP_MW} MW "
              "match-hour bump for pipeline testing.")


if __name__ == "__main__":
    main()
