"""
Milestone 7: the forecast-error version of the World Cup study.

The direct question
-------------------
M4 asked whether prices differed during match hours (was the effect anticipated).
This asks the cleaner question: did actual demand deviate from what was
forecast? The variable is the day-ahead load forecast error (actual minus
forecast, in MW). A positive spike during match hours means real demand ran
above the forecast, which is the market being surprised by the event.

Method
------
The same comparable-days design as M4. Each match day is paired with the five
most weather-comparable non-match days (nearest daily temperature and cloud
cover, preferring the same weekday-type), and the forecast error during that
day's match hours is compared with the same clock hours on the comparable days.

Evening vs overnight split
--------------------------
Because the 2026 tournament is in North America, many matches kick off after
midnight CEST, when almost nobody in Germany is watching. Averaging those in
washes out any real TV effect. So the analysis is run three ways: all matches,
only prime-time kickoffs (18:00-23:59 CEST), and only overnight ones
(00:00-06:59 CEST). If there is an effect anywhere, it should be in prime time.

Inputs : wc_load.csv (from entsoe_fetch.py), wc_weather.csv, wc_matches.csv
Outputs: wc_load_results.json, wc_load_effect.png
Run    : python wc_load_effect.py
"""

import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matching import load_weather_daily, Matcher, K_CONTROLS

HERE = Path(__file__).parent
PRIME_HOURS = set(range(18, 24))       # 18:00-23:59 CEST kickoffs
OVERNIGHT_HOURS = set(range(0, 7))     # 00:00-06:59 CEST kickoffs


def load_error_and_actual():
    err, actual = {}, {}
    with open(HERE / "wc_load.csv") as f:
        for r in csv.DictReader(f):
            t = dt.datetime.fromisoformat(r["datetime"])
            err[t] = float(r["forecast_error_mw"])
            actual[t] = float(r["load_actual_mw"])
    return err, actual


def load_match_hours_split():
    """Return {'all','prime','overnight'} -> {date: set(hours)}, bucketed by kickoff hour."""
    out = {"all": defaultdict(set), "prime": defaultdict(set), "overnight": defaultdict(set)}
    with open(HERE / "wc_matches.csv") as f:
        for r in csv.DictReader(f):
            raw = (r.get("kickoff_cet") or "").strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                start = dt.datetime.fromisoformat(raw)
            except ValueError:
                continue
            kh = start.hour
            bucket = "prime" if kh in PRIME_HOURS else ("overnight" if kh in OVERNIGHT_HOURS else None)
            for k in range(2):
                t = start + dt.timedelta(hours=k)
                out["all"][t.date()].add(t.hour)
                if bucket:
                    out[bucket][t.date()].add(t.hour)
    return out


def series_on(series, date, hours):
    vals = [series[dt.datetime(date.year, date.month, date.day, h)]
            for h in hours
            if dt.datetime(date.year, date.month, date.day, h) in series]
    return mean(vals) if vals else None


def interpret(mean_delta, t_stat, n=None, sd=None):
    mde = (2.8 * sd / math.sqrt(n)) if (n and n > 1 and sd) else None
    if t_stat is None or math.isnan(t_stat) or abs(t_stat) < 2:
        bound = (f"; only deviations of about {mde:.0f} MW or more were "
                 f"detectable at 80% power, so this rules out a large effect, "
                 f"not any effect") if mde else ""
        return ("no statistically clear deviation from comparable days "
                "(a null result is a real finding" + bound + ")")
    direction = "above" if mean_delta > 0 else "below"
    return (f"demand ran {abs(mean_delta):.0f} MW {direction} the forecast "
            f"beyond comparable days (t={t_stat:.1f}); do not read anything "
            f"into this before checking the permutation test (wc_permutation.py)")


def compute_effect(match_hours_by_day, err, err_days, matcher, control_days, mean_load):
    """Run the comparable-days effect for one subset of match hours."""
    feats = matcher.feats
    match_days = sorted(d for d in match_hours_by_day if d in feats and d in err_days)
    per_day = []
    for d in match_days:
        hours = sorted(match_hours_by_day[d])
        e_match = series_on(err, d, hours)
        if e_match is None:
            continue
        ctrl = [series_on(err, c, hours) for c in matcher.controls(d, control_days)]
        ctrl = [x for x in ctrl if x is not None]
        if not ctrl:
            continue
        per_day.append({
            "date": d.isoformat(), "match_hours": hours,
            "error_match_mw": round(e_match, 1),
            "error_comparable_mw": round(mean(ctrl), 1),
            "delta_mw": round(e_match - mean(ctrl), 1),
        })
    deltas = [x["delta_mw"] for x in per_day]
    n = len(deltas)
    if n == 0:
        return per_day, {"n_match_days": 0, "mean_delta_mw": None, "t_stat": None,
                         "interpretation": "no match days in this subset"}
    md = mean(deltas)
    # Sample SD (n-1), not population SD: these are n observed per-day deltas.
    sd = (stdev(deltas) if n > 1 else 0.0) or 0.0
    t = (md / (sd / math.sqrt(n))) if sd > 0 and n > 1 else float("nan")
    # Minimum detectable effect (80% power, two-sided alpha=0.05).
    mde = (2.8 * sd / math.sqrt(n)) if (n > 1 and sd > 0) else None
    return per_day, {
        "n_match_days": n,
        "mean_delta_mw": round(md, 1),
        "mean_delta_pct_of_load": round(100 * md / mean_load, 2),
        "std_mw": round(sd, 1),
        "t_stat": None if math.isnan(t) else round(t, 2),
        "mde_mw_80pct_power": None if mde is None else round(mde, 0),
        "interpretation": interpret(md, t, n, sd),
    }


def within_day_did(match_hours_by_day, all_by_day, err, err_days, matcher,
                   control_days):
    """Difference-in-differences robustness check for one subset.

    The main estimate compares match hours ACROSS days, so day-level drift
    between the (mostly pre-tournament) control period and the tournament
    period leaks in -- and the forecast-error series visibly drifts between
    the two periods. This contrast nets it out: per day, take (match-hour
    error minus same-day non-match-hour error), then compare that contrast
    between each match day and its weather-matched controls. The baseline
    hours exclude ALL match hours of that day (any subset), so overnight
    matches don't contaminate a prime-time baseline.
    """
    deltas = []
    for d in sorted(match_hours_by_day):
        if d not in matcher.feats or d not in err_days:
            continue
        hours = sorted(match_hours_by_day[d])
        excluded = all_by_day.get(d, set())
        others = [h for h in range(24) if h not in excluded]
        em = series_on(err, d, hours)
        eo = series_on(err, d, others)
        if em is None or eo is None:
            continue
        ctrl = []
        for c in matcher.controls(d, control_days):
            cm = series_on(err, c, hours)
            co = series_on(err, c, others)
            if cm is not None and co is not None:
                ctrl.append(cm - co)
        if not ctrl:
            continue
        deltas.append((em - eo) - mean(ctrl))
    n = len(deltas)
    if n < 2:
        return None
    md = mean(deltas)
    sd = stdev(deltas) or 0.0
    t = (md / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    return {
        "n": n,
        "mean_delta_mw": round(md, 1),
        "std_mw": round(sd, 1),
        "t_stat": None if math.isnan(t) else round(t, 2),
        "note": ("within-day contrast (match hours minus same-day non-match "
                 "hours), match day vs weather-matched controls; nets out "
                 "day-level drift in the forecast-error series"),
    }


def main():
    err, actual = load_error_and_actual()
    feats = load_weather_daily()
    splits = load_match_hours_split()

    err_days = {t.date() for t in err}
    all_by_day = splits["all"]
    control_days = [d for d in feats if d not in all_by_day and d in err_days]
    if not any(d in feats and d in err_days for d in all_by_day):
        raise SystemExit("No match days with load data. Run entsoe_fetch.py first.")
    if len(control_days) < K_CONTROLS:
        raise SystemExit("Not enough non-match control days with load data.")

    matcher = Matcher(feats)
    mean_load = mean(actual.values())

    subsets, per_day_all, did = {}, [], {}
    for name in ("all", "prime", "overnight"):
        per_day, effect = compute_effect(splits[name], err, err_days, matcher,
                                         control_days, mean_load)
        subsets[name] = effect
        did[name] = within_day_did(splits[name], all_by_day, err, err_days,
                                   matcher, control_days)
        if name == "all":
            per_day_all = per_day

    pairings = [{
        "date": d.isoformat(),
        "day_type": feats[d]["day_type"],
        "controls": matcher.controls(d, control_days, detailed=True),
    } for d in sorted(all_by_day) if d in feats and d in err_days]

    # hourly profile (from all match days) for the chart
    all_match_days = sorted(d for d in all_by_day if d in feats and d in err_days)
    match_prof, ctrl_prof = [], []
    for h in range(24):
        m = [err[dt.datetime(d.year, d.month, d.day, h)]
             for d in all_match_days if dt.datetime(d.year, d.month, d.day, h) in err]
        c = []
        for d in all_match_days:
            for cd in matcher.controls(d, control_days):
                key = dt.datetime(cd.year, cd.month, cd.day, h)
                if key in err:
                    c.append(err[key])
        match_prof.append(round(mean(m), 1) if m else None)
        ctrl_prof.append(round(mean(c), 1) if c else None)
    flags = [int(any(h in all_by_day[d] for d in all_match_days)) for h in range(24)]
    share = [round(mean(1.0 if h in all_by_day[d] else 0.0 for d in all_match_days), 2)
             for h in range(24)]

    meta_path = HERE / "wc_load_meta.json"
    data_source = "unknown"
    if meta_path.exists():
        data_source = json.load(open(meta_path)).get("data_source", "unknown")

    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "data_source": data_source,
        "n_control_pool": len(control_days),
        "k_controls_per_day": K_CONTROLS,
        "matching": matcher.describe(),
        "mean_load_mw": round(mean_load, 0),
        "effect": subsets["all"],          # backward-compatible top-level (all matches)
        "subsets": subsets,                # all / prime / overnight
        "robustness_within_day": did,      # per-subset difference-in-differences
        "hourly_profile": {
            "hours": list(range(24)),
            "match_days_error_mw": match_prof,
            "comparable_days_error_mw": ctrl_prof,
            "match_hour_flags": flags,
            "match_hour_share": share,
        },
        "per_day": per_day_all,
        "pairings": pairings,
    }
    with open(HERE / "wc_load_results.json", "w") as f:
        json.dump(results, f, indent=2)
    plot(results)
    report(results)


def plot(res):
    hp = res["hourly_profile"]
    hours = hp["hours"]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(hours, hp["match_days_error_mw"], marker="o", ms=3, color="#c1436d", label="Match days")
    ax.plot(hours, hp["comparable_days_error_mw"], marker="o", ms=3, color="#4c9f70",
            label="Weather-comparable days")
    ax.axhline(0, color="#888", lw=0.8)
    shares = hp.get("match_hour_share") or hp["match_hour_flags"]
    for h, f in zip(hours, shares):
        if f:
            ax.axvspan(h - 0.5, h + 0.5, color="#c1436d", alpha=0.30 * f)
    e = res["subsets"]["all"]
    ax.set_title(f"Load forecast error by hour (all matches {e['mean_delta_mw']:+.0f} MW, "
                 f"prime {res['subsets']['prime']['mean_delta_mw']:+.0f} MW)")
    ax.set_xlabel("Hour of day (CEST)  |  shading = share of match days with a match that hour")
    ax.set_ylabel("Actual minus forecast (MW)")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "wc_load_effect.png", dpi=120)


def report(s):
    if str(s.get("data_source", "")).startswith("synthetic"):
        print("!! WARNING: load data is SYNTHETIC (planted bump). These numbers are a "
              "pipeline test, not a real result. Run entsoe_fetch.py with a valid token.\n")
    print(f"Control pool: {s['n_control_pool']} days | mean load: {s['mean_load_mw']:.0f} MW\n")
    print(f"{'subset':<12}{'n days':>7}{'effect MW':>11}{'% load':>9}{'t':>7}")
    for name in ("all", "prime", "overnight"):
        e = s["subsets"][name]
        if e["mean_delta_mw"] is None:
            print(f"{name:<12}{e['n_match_days']:>7}{'--':>11}")
            continue
        print(f"{name:<12}{e['n_match_days']:>7}{e['mean_delta_mw']:>+11.0f}"
              f"{e['mean_delta_pct_of_load']:>+9.2f}{e['t_stat']:>7}")
    print()
    did = s.get("robustness_within_day") or {}
    for name in ("all", "prime", "overnight"):
        r = did.get(name)
        if r:
            print(f"DiD robustness ({name}): {r['mean_delta_mw']:+.0f} MW (t={r['t_stat']})")
    p = s["subsets"]["prime"]
    print(f"\nPrime-time reading: {p['interpretation']}")
    print("Wrote wc_load_results.json and wc_load_effect.png")


if __name__ == "__main__":
    main()
