"""
Fetch the real-time price layer for R9: the German uniform imbalance price
(reBAP), aligned to the same delivery hours as the day-ahead series
(year_prices.csv).

Why reBAP, and why not ENTSO-E
------------------------------
R9 asks how good the market's own day-ahead forecast is, by comparing the
day-ahead price against a price that forms closer to delivery. The first plan
used the intraday auction and the imbalance price from ENTSO-E. A probe
(intraday_probe.py) proved ENTSO-E carries NEITHER for Germany: the intraday
"A07" query just returns day-ahead, and every imbalance (A85) query returns
"no matching data" for every control-area domain and every window. The German
imbalance price is published by the four TSOs on netztransparenz.de instead.
So this fetcher gets the day-ahead price from the existing year file and the
reBAP from the netztransparenz WebAPI.

reBAP is the uniform balancing-energy price across the German control areas: the
real-time settlement price for schedule deviations. It is a SETTLEMENT price,
not a tradeable quote, and can be negative. Read it as "what real-time scarcity
cost", not as a household price. The household is billed at day-ahead regardless,
so nothing here changes the household verdict; the comparison is for flexibility
settled closer to delivery (and it is the zone-local signal R3 will reuse).

Credentials
-----------
The netztransparenz WebAPI uses OAuth2 client credentials. Register for the
"WebAPIReader" role (https://extranet.netztransparenz.de), create a client in the
WebAPI-Portal (https://api-portal.netztransparenz.de/), and put the pair in .env:

    IPNT_CLIENT_ID=...
    IPNT_CLIENT_SECRET=...

Without them (or on any failure) the script writes a SYNTHETIC layer with a
planted, recoverable structure so the pipeline runs and the analysis validates
offline. Real data carries none of it.

Endpoint
--------
Token at identity.netztransparenz.de/users/connect/token, data under
ds.netztransparenz.de/api/v1/data/{data}/{product}/{from}/{to} as CSV. The reBAP
{data}/{product} segment (NrvSaldo/reBAP/Qualitaetsgesichert, CSV "Format 9") is
from the official docs; the parser is defensive (sniffs the delimiter, handles
the German decimal comma, finds columns by header keyword).

Official documentation:
  WebAPI overview : https://www.netztransparenz.de/en/Web-API
  WebAPI FAQ      : https://www.netztransparenz.de/en/FAQ/FAQ-WebAPI
  Full docs (v1.14, endpoint table + Format 9 + rate limits):
    https://www.netztransparenz.de/xspproxy/api/staticfiles/ntp-relaunch/dokumente/web-api/dokumentation-webserviceapi-netztransparenz_v1.14.pdf
  Swagger         : https://api-portal.netztransparenz.de/public-swagger-ui
  reBAP data page : https://www.netztransparenz.de/en/Balancing-Capacity/Imbalance-price/Uniform-imbalance-price-reBAP

Data handling: netztransparenz publishes no explicit reuse licence for the
reBAP, so intraday_prices.csv (which holds the raw series) is gitignored and
never committed; only the derived intraday_results.json is.

Rate limit: at most 2 requests/s per IP (repeated breaches block the IP for 2
hours). _rate_limited_get() warns before approaching the cap and backs off on
429; see RATE_LIMIT_PER_SEC below.

Timezone / resolution
---------------------
reBAP is quarter-hourly. Timestamps are handled in Europe/Berlin via ZoneInfo
and averaged into their delivery hour to line up with the hourly day-ahead file
(the quarter-hour version is ROADMAP R7). EUR/MWh is converted to ct/kWh (/10).

Output: intraday_prices.csv (datetime, da_ct_per_kwh, imbalance_ct_per_kwh) and
        intraday_meta.json.
Run   : python intraday_fetch.py            # full year aligned to year_prices.csv
        python intraday_fetch.py 2025-07-01 2026-06-30
        python intraday_fetch.py --since     # incremental: fetch only the new tail
        python intraday_fetch.py --since 2026-06-01   # incremental from a given date
        python intraday_fetch.py --selftest  # validate the CSV parser offline
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import requests

HERE = Path(__file__).parent
BERLIN = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")

TOKEN_URL = "https://identity.netztransparenz.de/users/connect/token"
API = "https://ds.netztransparenz.de/api/v1"
# Endpoint from the official WebAPI documentation (v1.14), table of endpoints:
#   "reBAP unterdeckt/ueberdeckt": GET api/v1/data/NrvSaldo/reBAP/Qualitaetsgesichert
# Returns CSV "Format 9". Only the quality-assured series exists (no operational
# one), published a few days delayed, so a trailing-year fetch may miss the last
# few days and the analysis tolerates partial overlap. Do NOT read a short tail as
# that publication lag by default: the window is bounded by year_prices.csv, so a
# stale day-ahead file produces the same symptom. window_from reports which it is.
REBAP_ENDPOINT = "NrvSaldo/reBAP/Qualitaetsgesichert"

MIN_OVERLAP_HOURS = 24 * 60             # a year fetch returning less is treated as failed
EUR_MWH_TO_CT_KWH = 1 / 10.0
# The day-ahead file bounds this study's window twice over: its last day becomes
# the reBAP request's end date, and the output is the day-ahead/reBAP
# intersection. So a stale year_prices.csv silently truncates the window while
# the fetch still reports success. year_fetch.py's own default already stops ~2
# days short of today (archive lag), so anything beyond that plus slack means the
# reference file needs refreshing, not that reBAP is missing.
STALE_REFERENCE_DAYS = 4
# --since re-fetches this many days before the last stored row, so late-published
# quality-assured values (reBAP lags a few days) get filled in on the next run.
OVERLAP_REFETCH_DAYS = 5
# netztransparenz WAF: at most 2 requests/s per source IP; repeated breaches
# block the IP for 2 hours. We stay well under with base spacing AND a proactive
# limiter that warns before it would exceed the cap.
RATE_LIMIT_PER_SEC = 2
REQUEST_SPACING_S = 0.6
_recent_requests = []                   # monotonic timestamps within the trailing 1s


# --- credentials / .env -----------------------------------------------------

def load_dotenv(path=None):
    path = path or (HERE / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def creds():
    return os.environ.get("IPNT_CLIENT_ID"), os.environ.get("IPNT_CLIENT_SECRET")


def get_token():
    cid, sec = creds()
    if not cid or not sec:
        raise RuntimeError("IPNT_CLIENT_ID / IPNT_CLIENT_SECRET not set (shell or .env)")
    r = requests.post(TOKEN_URL, data={"grant_type": "client_credentials",
                                       "client_id": cid, "client_secret": sec}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


# --- day-ahead reference ----------------------------------------------------

def load_day_ahead():
    path = HERE / "year_prices.csv"
    if not path.exists():
        raise SystemExit(
            "year_prices.csv not found. Run 'python year_fetch.py' first; the "
            "reBAP layer is compared against that day-ahead series.")
    da = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            da[dt.datetime.fromisoformat(r["datetime"])] = float(r["ct_per_kwh"])
    return da


def window_from(da, dates, today=None):
    """Window from an explicit [START, END] pair, else the full year_prices range.

    Returns (start, end, reference). `reference` records how far behind today the
    day-ahead file ends and whether that counts as stale, so the condition is
    visible on stdout AND auditable afterwards in intraday_meta.json. Without it
    a six-day-old year_prices.csv reads as a clean "live" fetch that happens to
    stop early, which is how the missing 14-19 July 2026 reBAP days were first
    misread as a publication delay.

    The truncation itself is not a bug: the spread needs both series, so the
    reBAP window cannot usefully run past the day-ahead extent. Asking for it
    silently is the bug.
    """
    today = today or dt.date.today()
    days = sorted({t.date() for t in da})
    da_end = days[-1]
    behind = (today - da_end).days
    reference = {
        "da_start": days[0].isoformat(),
        "da_end": da_end.isoformat(),
        "days_behind_today": behind,
        "stale": behind > STALE_REFERENCE_DAYS,
    }

    if len(dates) == 2:
        start, end = dt.date.fromisoformat(dates[0]), dt.date.fromisoformat(dates[1])
        reference["requested_end"] = end.isoformat()
        if end > da_end:
            reference["trimmed_to_da_end"] = True
            print(f"NOTE: requested end {end} runs past the day-ahead series "
                  f"({da_end}). Everything after {da_end} will be dropped by the "
                  f"day-ahead/reBAP intersection, so those days cannot enter the "
                  f"study until year_prices.csv is extended.")
        return start, end, reference

    if reference["stale"]:
        print(f"WARNING: year_prices.csv ends {da_end}, {behind} days before today "
              f"({today}). That end date becomes this fetch's end date, so reBAP "
              f"after {da_end} is never requested and cannot appear in the output, "
              f"however recently it was published.")
        print(f"         To extend without sliding the window's start: "
              f"python year_fetch.py {days[0].isoformat()} "
              f"{(today - dt.timedelta(days=2)).isoformat()}")
        print(f"         Then re-run: python intraday_fetch.py --since auto")
    return days[0], da_end, reference


def load_existing_imb():
    """{datetime -> imbalance ct/kWh} from an existing intraday_prices.csv, for
    the incremental (--since) merge. Empty if the file is absent."""
    path = HERE / "intraday_prices.csv"
    if not path.exists():
        return {}
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                out[dt.datetime.fromisoformat(r["datetime"])] = float(r["imbalance_ct_per_kwh"])
            except (KeyError, ValueError):
                continue
    return out


def existing_is_synthetic():
    """True if the on-disk intraday layer was written from synthetic data, so
    --since must not append real data onto it."""
    path = HERE / "intraday_meta.json"
    if not path.exists():
        return False
    try:
        return str(json.load(open(path)).get("data_source", "")).startswith("synthetic")
    except Exception:
        return False


# --- reBAP CSV parsing (defensive) ------------------------------------------

def _to_float_de(s):
    s = (s or "").strip().replace('"', "")
    if not s:
        return None
    # German CSVs use ',' as decimal and sometimes '.' as thousands separator.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_col(header, keys, exclude=()):
    for i, h in enumerate(header):
        if any(x in h for x in exclude):
            continue
        if any(k in h for k in keys):
            return i
    return None


def parse_rebap_csv(text):
    """Parse a netztransparenz reBAP CSV (documented "Format 9") into
    {delivery_hour(Europe/Berlin) -> ct/kWh}.

    Format 9 header:
      Datum;Zeitzone;von;bis;Datenkategorie;Datentyp;Einheit;reBAP unterdeckt;reBAP ueberdeckt
    with rows like:
      10.06.2023;UTC;13:00;13:15;reBAP;Qualitätsgesichert;EUR/MWh;103,97;103,97

    Key points handled: ';' delimiter, German decimal comma, timestamps in UTC
    (converted to Europe/Berlin), value in EUR/MWh (converted to ct/kWh). Since
    Nov 2023 reBAP is a single price, so "unterdeckt" and "ueberdeckt" are equal;
    the "unterdeckt" column is used. Sub-hourly (15-minute) values are averaged
    into their delivery hour. Column lookup is by header keyword so a minor
    header change does not break it.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}
    delim = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    header = [h.strip().lower() for h in rows[0]]

    i_date = _find_col(header, ["datum", "date", "tag"])
    # "von" is the interval start; exclude the "Zeitzone" column (contains "zeit").
    i_time = _find_col(header, ["von", "from", "start", "uhrzeit"], exclude=["zone"])
    i_zone = _find_col(header, ["zeitzone", "zone"])
    # prefer the "unterdeckt" reBAP column, else any reBAP/AEP price column.
    i_val = _find_col(header, ["rebap unterdeckt", "unterdeckt"]) \
        or _find_col(header, ["rebap", "aep", "ausgleichsenergie"])
    if i_date is None or i_val is None:
        raise RuntimeError(f"reBAP CSV: could not locate columns in header {rows[0]}")

    buckets = defaultdict(list)
    for row in rows[1:]:
        need = max(x for x in (i_date, i_time, i_val) if x is not None)
        if len(row) <= need:
            continue
        try:
            d = dt.datetime.strptime(row[i_date].strip(), "%d.%m.%Y").date()
        except ValueError:
            try:
                d = dt.date.fromisoformat(row[i_date].strip())
            except ValueError:
                continue
        tp = (row[i_time].strip() if i_time is not None else "00:00").split("-")[0].strip()
        hh, mm = (int(tp.split(":")[0]), int(tp.split(":")[1])) if ":" in tp else (0, 0)
        v = _to_float_de(row[i_val])
        if v is None:
            continue
        zone = (row[i_zone].strip().upper() if i_zone is not None and len(row) > i_zone else "UTC")
        naive = dt.datetime(d.year, d.month, d.day, hh, mm)
        # timestamps are published in UTC; convert to Berlin wall-clock, then bucket.
        aware = naive.replace(tzinfo=UTC if zone == "UTC" else BERLIN)
        t_berlin = aware.astimezone(BERLIN).replace(tzinfo=None)
        hour = t_berlin.replace(minute=0, second=0, microsecond=0)
        buckets[hour].append(v * EUR_MWH_TO_CT_KWH)
    return {h: mean(v) for h, v in buckets.items()}


def _rate_limited_get(url, headers, timeout=120, _attempt=1):
    """GET that keeps under the netztransparenz rate limit. It warns BEFORE it
    would exceed the 2-requests-per-second cap and pauses to stay legal, and if
    the server still answers 429 (Too Many Requests) it warns loudly and backs
    off, because repeated breaches block the source IP for two hours."""
    now = time.monotonic()
    while _recent_requests and now - _recent_requests[0] > 1.0:
        _recent_requests.pop(0)
    if len(_recent_requests) >= RATE_LIMIT_PER_SEC:
        wait = 1.0 - (now - _recent_requests[0]) + 0.05
        print(f"  ! nearing the netztransparenz rate limit "
              f"({RATE_LIMIT_PER_SEC} requests/s per IP); pausing {max(wait,0):.2f}s to stay "
              f"under it (repeated breaches block the IP for 2 hours)")
        time.sleep(max(wait, 0.0))
    else:
        time.sleep(REQUEST_SPACING_S)   # gentle base spacing even when under the cap
    _recent_requests.append(time.monotonic())
    r = requests.get(url, headers=headers, timeout=timeout)
    if r.status_code == 429 and _attempt <= 3:
        back = 5 * _attempt
        print(f"  !! netztransparenz returned 429 Too Many Requests (rate limit hit). "
              f"Backing off {back}s and retrying (attempt {_attempt}/3). If this keeps "
              f"happening, the IP may already be blocked for 2 hours; wait and rerun.")
        time.sleep(back)
        return _rate_limited_get(url, headers, timeout, _attempt + 1)
    return r


def _rebap_url_forms(d1, d2):
    """The date-passing convention is not 100% pinned by the docs, so try the
    documented datetime-path form first, then date-only path, then query params.
    Whichever returns usable CSV is reused for the remaining chunks."""
    base = f"{API}/data/{REBAP_ENDPOINT}"
    return [
        f"{base}/{d1}T00:00:00/{d2}T23:59:59",
        f"{base}/{d1}/{d2}",
        f"{base}?dateFrom={d1}T00:00:00&dateTo={d2}T23:59:59",
    ]


def fetch_rebap(token, start, end):
    """Fetch reBAP in monthly chunks (staying under the rate limit) and merge."""
    out = {}
    headers = {"Authorization": f"Bearer {token}"}
    form_idx = None
    d = start
    while d <= end:
        d2 = min(dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
                 - dt.timedelta(days=1), end)
        forms = _rebap_url_forms(d.isoformat(), d2.isoformat())
        candidates = [forms[form_idx]] if form_idx is not None else forms
        got, used = None, None
        for i, url in enumerate(candidates):
            r = _rate_limited_get(url, headers)
            if r.status_code == 200 and "rebap" in r.text[:400].lower():
                got = parse_rebap_csv(r.text)
                used = form_idx if form_idx is not None else i
                break
        if got is None:
            raise RuntimeError(
                f"reBAP fetch for {d}..{d2} returned no usable CSV from any URL "
                f"form (last status {r.status_code}). Check the endpoint/date format.")
        form_idx = used
        out.update(got)
        print(f"  reBAP {d}..{d2}: {len(out)} hours total")
        d = d2 + dt.timedelta(days=1)
    return out


# --- synthetic fallback -----------------------------------------------------

def synth(da, start, end):
    """Build a plausible reBAP layer FROM the real day-ahead prices, with a
    PLANTED, recoverable structure so intraday_analysis.py validates offline:
      - a mild systematic hour-of-day bias (real-time runs above day-ahead in the
        evening ramp, below around the midday solar peak), the kind of bias R9
        detects, and
      - a heavy-tailed real-time shock, so imbalance variance is visibly larger
        than day-ahead (the fat tail R9 reports with robust statistics).
    Real reBAP carries none of this; a flat spread on real data is a finding.
    """
    random.seed(23)
    imb = {}
    for t, p in da.items():
        if not (start <= t.date() <= end):
            continue
        h = t.hour
        bias = 0.9 if 17 <= h <= 21 else (-0.6 if 11 <= h <= 14 else 0.0)
        shock = random.gauss(0, 1.2) + (random.gauss(0, 8.0) if random.random() < 0.06 else 0.0)
        imb[t] = round(p + bias + shock, 3)
    return imb


# --- main -------------------------------------------------------------------

def main(args):
    load_dotenv()
    da = load_day_ahead()
    start, end, reference = window_from(da, args.dates)
    da = {t: p for t, p in da.items() if start <= t.date() <= end}
    print(f"Reference day-ahead window: {start} .. {end} ({len(da)} hours)")

    # Decide whether this is an incremental (--since) run. It only applies when
    # a REAL intraday_prices.csv already exists; otherwise fall back to a full
    # fetch so we never append onto missing or synthetic data.
    incremental = args.since is not None
    existing = load_existing_imb() if incremental else {}
    if incremental and not existing:
        print("--since: no existing intraday_prices.csv to extend; doing a full fetch.")
        incremental = False
    elif incremental and existing_is_synthetic():
        print("--since: existing intraday_prices.csv is SYNTHETIC; refusing to append "
              "real data onto test data. Doing a full fetch instead.")
        existing, incremental = {}, False

    if incremental:
        if args.since == "auto":
            last = max(t.date() for t in existing)
            fetch_start = max(start, last - dt.timedelta(days=OVERLAP_REFETCH_DAYS))
        else:
            fetch_start = max(start, dt.date.fromisoformat(args.since))
        print(f"Incremental reBAP fetch: {fetch_start} .. {end} "
              f"(re-fetching a {OVERLAP_REFETCH_DAYS}-day overlap for late-published values); "
              f"{len(existing)} hours already on disk")
        try:
            token = get_token()
            new = fetch_rebap(token, fetch_start, end)
        except Exception as e:
            sys.exit(f"\nIncremental fetch failed ({type(e).__name__}: {str(e)[:120]}).\n"
                     f"intraday_prices.csv left UNCHANGED (no synthetic clobber in --since mode).")
        imb = dict(existing)
        imb.update(new)             # newly fetched values win on the overlap
        source = f"live (incremental since {fetch_start.isoformat()})"
        print(f"Merged: {len(new)} fetched, {len(imb)} total hours on disk")
    else:
        source = "live"
        try:
            token = get_token()
            imb = fetch_rebap(token, start, end)
            overlap = set(da) & set(imb)
            if len(overlap) < MIN_OVERLAP_HOURS:
                raise RuntimeError(
                    f"only {len(overlap)} hours overlap day-ahead/reBAP (need >= "
                    f"{MIN_OVERLAP_HOURS}); check REBAP_ENDPOINT and the window")
        except Exception as e:
            source = f"synthetic ({type(e).__name__}: {str(e)[:80]})"
            print(f"NOTE: using synthetic reBAP layer. Reason -> {source}")
            imb = synth(da, start, end)

    hours = sorted(set(da) & set(imb))
    with open(HERE / "intraday_prices.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "da_ct_per_kwh", "imbalance_ct_per_kwh"])
        for h in hours:
            w.writerow([h.isoformat(), f"{da[h]:.3f}", f"{imb[h]:.3f}"])

    with open(HERE / "intraday_meta.json", "w") as f:
        json.dump({"data_source": source,
                   "window": {"start": start.isoformat(), "end": end.isoformat()},
                   "hours": len(hours),
                   "signals": {"da": "day-ahead auction (year_prices.csv, aWATTar/EPEX)",
                               "imbalance": "reBAP uniform imbalance price (netztransparenz.de)"},
                   # How far behind today the bounding day-ahead file ran at fetch
                   # time. A truncated window is only interpretable with this.
                   "reference": reference,
                   "fetched_at": dt.datetime.now().isoformat(timespec="minutes")},
                  f, indent=2)

    spreads = [imb[h] - da[h] for h in hours]
    print(f"\nData source: {source}")
    print(f"Wrote intraday_prices.csv ({len(hours)} hours), {hours[0]} .. {hours[-1]}")
    print(f"Mean reBAP-minus-day-ahead spread: {mean(spreads):+.3f} ct/kWh")
    if source.startswith("synthetic"):
        print("NOTE: synthetic layer carries a PLANTED hour-of-day spread and a "
              "fat-tailed shock for pipeline testing. Real reBAP carries neither.")
    if reference["stale"]:
        print(f"REMINDER: this window stops at {reference['da_end']} because "
              f"year_prices.csv does, not because reBAP ends there. Refresh the "
              f"day-ahead reference and re-run before treating the tail as missing data.")
    print("Next: python intraday_analysis.py")


def selftest():
    """Validate the Format 9 parser against the exact sample from the WebAPI
    documentation (v1.14), so the parsing/units/timezone logic is checked
    without any network access."""
    sample = (
        "Datum;Zeitzone;von;bis;Datenkategorie;Datentyp;Einheit;reBAP unterdeckt;reBAP ueberdeckt\n"
        "10.06.2023;UTC;13:00;13:15;reBAP;Qualitätsgesichert;EUR/MWh;103,97;103,97\n"
        "10.06.2023;UTC;13:15;13:30;reBAP;Qualitätsgesichert;EUR/MWh;104,06;104,06\n"
        "10.06.2023;UTC;13:30;13:45;reBAP;Qualitätsgesichert;EUR/MWh;104,57;104,57\n"
    )
    got = parse_rebap_csv(sample)
    # 13:00-13:45 UTC on 2023-06-10 is 15:00 Berlin (CEST, summer). Three 15-min
    # values fall in Berlin hour 15:00; mean(103.97,104.06,104.57)/10 ct/kWh.
    key = dt.datetime(2023, 6, 10, 15, 0)
    assert key in got, f"expected Berlin hour {key}, got {list(got)}"
    expect = mean([103.97, 104.06, 104.57]) / 10
    assert abs(got[key] - expect) < 1e-6, f"value {got[key]} != {expect}"
    print(f"selftest OK: {key} -> {got[key]:.4f} ct/kWh "
          f"(UTC->Berlin, EUR/MWh->ct/kWh, 15-min averaged)")

    # window_from's staleness detection, the guard against a stale day-ahead file
    # silently truncating the study window.
    da = {dt.datetime(2026, 7, d, h): 10.0
          for d in (10, 11, 12) for h in range(24)}
    today = dt.date(2026, 7, 30)
    start, end, ref = window_from(da, [], today=today)
    assert (start, end) == (dt.date(2026, 7, 10), dt.date(2026, 7, 12)), (start, end)
    assert ref["days_behind_today"] == 18 and ref["stale"], ref
    # A fresh reference (inside the archive lag) must not warn.
    fresh = {dt.datetime(2026, 7, 28, h): 10.0 for h in range(24)}
    _, _, ref_fresh = window_from(fresh, [], today=today)
    assert ref_fresh["days_behind_today"] == 2 and not ref_fresh["stale"], ref_fresh
    # An explicit end past the day-ahead extent is flagged as trimmed.
    _, _, ref_req = window_from(da, ["2026-07-10", "2026-07-19"], today=today)
    assert ref_req.get("trimmed_to_da_end") and ref_req["requested_end"] == "2026-07-19", ref_req
    print("selftest OK: window_from staleness guard (stale / fresh / trimmed)")


def parse_args():
    ap = argparse.ArgumentParser(
        description="Fetch the reBAP (real-time) price and align it to the "
                    "day-ahead series for the R9 study.")
    ap.add_argument("dates", nargs="*", metavar="DATE",
                    help="optional START END (YYYY-MM-DD); default: the full "
                         "year_prices.csv range")
    ap.add_argument("--since", nargs="?", const="auto", default=None, metavar="YYYY-MM-DD",
                    help="incremental: fetch only reBAP newer than what is already "
                         "in intraday_prices.csv (or since the given date) and merge, "
                         "instead of re-backfilling the whole year. Never overwrites "
                         "real data with synthetic; leaves the file untouched on failure.")
    ap.add_argument("--selftest", action="store_true",
                    help="validate the CSV parser against the documented sample; no network")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.selftest:
        selftest()
    else:
        main(args)
