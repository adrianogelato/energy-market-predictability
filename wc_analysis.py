"""
Milestone 4, step 2: the World Cup price study.

Hypothesis
----------
Do electricity prices behave differently during World Cup match hours than they
would on a comparable day, once you control for weather?

Method (comparable-days / matched controls)
-------------------------------------------
1. A "match day" is any date with at least one match (from wc_matches.csv).
   Its "match hours" are the clock hours a match was live (CEST).
2. Weather drives price (via solar, wind, and demand), so we must not compare
   match days to arbitrary days. For each match day we find the K most
   weather-comparable NON-match days. What "comparable" means is defined once,
   in matching.py: temperature mean and max, a solar proxy (radiation when
   available, else cloud), wind when available, all z-scored; same day-type
   (weekday / Saturday / Sunday-or-holiday) preferred. The chosen pairings are
   written into the results JSON so they can be inspected.
3. We compare the average price during that day's match hours against the
   average price during the SAME clock hours on its comparable control days.
   The difference is the estimated match effect for that day.
4. We aggregate the per-day differences: mean, spread, and a simple t-statistic.

This isolates the match effect from weather, which is the whole point. It is an
observational estimate, not proof of causation.

Inputs : wc_prices.csv, wc_weather.csv, wc_matches.csv  (run wc_fetch_data.py first)
Outputs: wc_results.json, wc_analysis.png
Run    : python wc_analysis.py
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


def load_prices():
    out = {}
    with open(HERE / "wc_prices.csv") as f:
        for r in csv.DictReader(f):
            out[dt.datetime.fromisoformat(r["datetime"])] = float(r["ct_per_kwh"])
    return out


def load_match_hours_by_day():
    """Return {date: set(hours)} from wc_matches.csv."""
    by_day = defaultdict(set)
    with open(HERE / "wc_matches.csv") as f:
        for r in csv.DictReader(f):
            raw = (r.get("kickoff_cet") or "").strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                start = dt.datetime.fromisoformat(raw)
            except ValueError:
                continue
            for k in range(2):  # a match spans ~2 clock hours
                t = start + dt.timedelta(hours=k)
                by_day[t.date()].add(t.hour)
    return by_day


def price_on(prices, date, hours):
    """Mean price on `date` over the given clock `hours` (skip missing)."""
    vals = [prices[dt.datetime(date.year, date.month, date.day, h)]
            for h in hours
            if dt.datetime(date.year, date.month, date.day, h) in prices]
    return mean(vals) if vals else None


def main():
    prices = load_prices()
    feats = load_weather_daily()
    match_hours_by_day = load_match_hours_by_day()

    match_days = sorted(d for d in match_hours_by_day if d in feats)
    control_days = [d for d in feats if d not in match_hours_by_day]

    if not match_days:
        raise SystemExit("No match days found. Fill in wc_matches.csv first.")
    if len(control_days) < K_CONTROLS:
        raise SystemExit("Not enough non-match control days in the window.")

    matcher = Matcher(feats)

    # Per-day effect: match-hour price minus comparable-day match-hour price
    per_day, pairings = [], []
    for d in match_days:
        hours = sorted(match_hours_by_day[d])
        p_match = price_on(prices, d, hours)
        if p_match is None:
            continue
        controls = matcher.controls(d, control_days)
        pairings.append({
            "date": d.isoformat(),
            "day_type": feats[d]["day_type"],
            "controls": matcher.controls(d, control_days, detailed=True),
        })
        ctrl_prices = [price_on(prices, c, hours) for c in controls]
        ctrl_prices = [p for p in ctrl_prices if p is not None]
        if not ctrl_prices:
            continue
        p_ctrl = mean(ctrl_prices)
        per_day.append({
            "date": d.isoformat(),
            "match_hours": hours,
            "price_match_ct": round(p_match, 2),
            "price_comparable_ct": round(p_ctrl, 2),
            "delta_ct": round(p_match - p_ctrl, 2),
        })

    deltas = [x["delta_ct"] for x in per_day]
    n = len(deltas)
    mean_delta = mean(deltas)
    # Sample SD (n-1): these are n observed per-day deltas, not a population.
    sd = (stdev(deltas) if n > 1 else 0.0) or 0.0
    t_stat = (mean_delta / (sd / math.sqrt(n))) if sd > 0 and n > 1 else float("nan")
    # Minimum detectable effect at 80% power, two-sided alpha=0.05:
    # (z_0.975 + z_0.80) * SE ~= 2.8 * sd / sqrt(n). A null result only rules
    # out effects at least this large; smaller ones would be invisible here.
    mde = (2.8 * sd / math.sqrt(n)) if (n > 1 and sd > 0) else None

    # Robustness: within-day difference-in-differences, which nets out the
    # day-level seasonal drift the main estimate inherits (controls are mostly
    # pre-tournament, match days are mid-June to mid-July).
    did = within_day_did(prices, match_days, match_hours_by_day, matcher,
                         control_days)

    # Hourly profile overlay: avg price by clock hour on match days vs their controls
    match_prof, ctrl_prof = [], []
    for h in range(24):
        m_vals = [prices[dt.datetime(d.year, d.month, d.day, h)]
                  for d in match_days
                  if dt.datetime(d.year, d.month, d.day, h) in prices]
        # controls: pool all comparable days used
        c_vals = []
        for d in match_days:
            for c in matcher.controls(d, control_days):
                key = dt.datetime(c.year, c.month, c.day, h)
                if key in prices:
                    c_vals.append(prices[key])
        match_prof.append(round(mean(m_vals), 2) if m_vals else None)
        ctrl_prof.append(round(mean(c_vals), 2) if c_vals else None)

    match_hour_flags = [int(any(h in match_hours_by_day[d] for d in match_days))
                        for h in range(24)]
    # Share of match days on which each hour actually was a match hour. The
    # binary flags shade 14 of 24 hours and overstate exposure; the share is
    # what the charts should scale by.
    match_hour_share = [round(mean(1.0 if h in match_hours_by_day[d] else 0.0
                                   for d in match_days), 2)
                        for h in range(24)]

    meta_path = HERE / "wc_meta.json"
    data_source = "unknown"
    if meta_path.exists():
        data_source = json.load(open(meta_path)).get("data_source", "unknown")

    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "data_source": data_source,
        "window": {"start": min(feats).isoformat(), "end": max(feats).isoformat()},
        "n_match_days": n,
        "n_control_pool": len(control_days),
        "k_controls_per_day": K_CONTROLS,
        "matching": matcher.describe(),
        "effect": {
            "mean_delta_ct_per_kwh": round(mean_delta, 2),
            "std_ct": round(sd, 2),
            "t_stat": None if math.isnan(t_stat) else round(t_stat, 2),
            "mde_ct_80pct_power": None if mde is None else round(mde, 2),
            "t_caveat": ("per-day deltas share control days (pool smaller than "
                         "the match-day count), so they are positively correlated "
                         "and this t is optimistic"),
            "interpretation": interpret(mean_delta, t_stat, n, sd),
        },
        "robustness_within_day": did,
        "hourly_profile": {
            "hours": list(range(24)),
            "match_days_avg": match_prof,
            "comparable_days_avg": ctrl_prof,
            "match_hour_flags": match_hour_flags,
            "match_hour_share": match_hour_share,
        },
        "per_day": per_day,
        "pairings": pairings,
    }
    with open(HERE / "wc_results.json", "w") as f:
        json.dump(results, f, indent=2)

    plot(results)
    print(f"Match days analysed: {n} | control pool: {len(control_days)} days")
    print(f"Mean match-hour effect: {mean_delta:+.2f} ct/kWh "
          f"(sd {sd:.2f}, t={results['effect']['t_stat']}, "
          f"MDE~{results['effect']['mde_ct_80pct_power']} ct/kWh)")
    if did:
        print(f"Within-day DiD robustness: {did['mean_delta_ct']:+.2f} ct/kWh "
              f"(t={did['t_stat']}) — this contrast nets out seasonal drift")
    print(f"-> {results['effect']['interpretation']}")
    print("Wrote wc_results.json and wc_analysis.png")


def interpret(mean_delta, t_stat, n=None, sd=None):
    mde = (2.8 * sd / math.sqrt(n)) if (n and n > 1 and sd) else None
    if math.isnan(t_stat) or abs(t_stat) < 2:
        bound = (f" With n={n} days, only effects of about {mde:.1f} ct/kWh or "
                 f"larger were detectable (80% power), so this rules out a "
                 f"large effect, not any effect.") if mde else ""
        return ("No statistically clear effect: match hours look like "
                "weather-comparable days. A null result is still a real finding."
                + bound)
    direction = "higher" if mean_delta > 0 else "lower"
    return (f"Prices during match hours run {abs(mean_delta):.2f} ct/kWh {direction} "
            f"than weather-comparable days (t={t_stat:.1f}). Suggestive at best: "
            f"the per-day deltas share control days, so this t is optimistic.")


def within_day_did(prices, match_days, match_hours_by_day, matcher, control_days):
    """Difference-in-differences robustness check.

    The main estimate compares match hours ACROSS days, so any day-level drift
    between the (mostly pre-tournament) control period and the tournament
    period leaks into it. This contrast nets that out: per day, take
    (match-hour mean minus same-day non-match-hour mean), then compare that
    within-day contrast between each match day and its weather-matched controls.
    """
    deltas = []
    for d in match_days:
        hours = sorted(match_hours_by_day[d])
        others = [h for h in range(24) if h not in match_hours_by_day[d]]
        pm = price_on(prices, d, hours)
        po = price_on(prices, d, others)
        if pm is None or po is None:
            continue
        ctrl = []
        for c in matcher.controls(d, control_days):
            cm = price_on(prices, c, hours)
            co = price_on(prices, c, others)
            if cm is not None and co is not None:
                ctrl.append(cm - co)
        if not ctrl:
            continue
        deltas.append((pm - po) - mean(ctrl))
    n = len(deltas)
    if n < 2:
        return None
    md = mean(deltas)
    sd = stdev(deltas) or 0.0
    t = (md / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    return {
        "n": n,
        "mean_delta_ct": round(md, 2),
        "std_ct": round(sd, 2),
        "t_stat": None if math.isnan(t) else round(t, 2),
        "note": ("within-day contrast (match hours minus same-day non-match "
                 "hours), match day vs weather-matched controls; nets out the "
                 "day-level seasonal drift the main estimate inherits"),
    }


def plot(res):
    hp = res["hourly_profile"]
    hours = hp["hours"]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(hours, hp["match_days_avg"], marker="o", ms=3, label="Match days", color="#c1436d")
    ax.plot(hours, hp["comparable_days_avg"], marker="o", ms=3,
            label="Weather-comparable days", color="#4c9f70")
    shares = hp.get("match_hour_share") or hp["match_hour_flags"]
    for h, share in zip(hours, shares):
        if share:
            ax.axvspan(h - 0.5, h + 0.5, color="#c1436d", alpha=0.30 * share)
    ax.set_title(f"Avg price by hour: match days vs comparable days "
                 f"(effect {res['effect']['mean_delta_ct_per_kwh']:+.2f} ct/kWh in match hours)")
    ax.set_xlabel("Hour of day (CEST)  |  shading = share of match days with a match that hour")
    ax.set_ylabel("Price (ct/kWh)")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "wc_analysis.png", dpi=120)


if __name__ == "__main__":
    main()
