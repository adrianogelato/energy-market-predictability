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
from plot_utils import add_caption

HERE = Path(__file__).parent


def load_prices():
    out = {}
    with open(HERE / "wc_prices.csv") as f:
        for r in csv.DictReader(f):
            out[dt.datetime.fromisoformat(r["datetime"])] = float(r["ct_per_kwh"])
    return out


def load_match_hours_by_day():
    """Return ({date: set(hours)}, {date: set(hours)} for Germany's matches,
    {date: {hour: n_matches}}) from wc_matches.csv.

    The Germany subset exists because a single well-followed team is the
    best-powered single event in the data; membership is read from the label
    column. The per-hour match count feeds the hourly chart on worldcup.html.
    """
    by_day = defaultdict(set)
    germany_by_day = defaultdict(set)
    count_by_day = defaultdict(lambda: defaultdict(int))
    with open(HERE / "wc_matches.csv") as f:
        for r in csv.DictReader(f):
            raw = (r.get("kickoff_cet") or "").strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                start = dt.datetime.fromisoformat(raw)
            except ValueError:
                continue
            is_germany = "germany" in (r.get("label") or "").lower()
            for k in range(2):  # a match spans ~2 clock hours
                t = start + dt.timedelta(hours=k)
                by_day[t.date()].add(t.hour)
                count_by_day[t.date()][t.hour] += 1
                if is_germany:
                    germany_by_day[t.date()].add(t.hour)
    return by_day, germany_by_day, count_by_day


def price_on(prices, date, hours):
    """Mean price on `date` over the given clock `hours` (skip missing)."""
    vals = [prices[dt.datetime(date.year, date.month, date.day, h)]
            for h in hours
            if dt.datetime(date.year, date.month, date.day, h) in prices]
    return mean(vals) if vals else None


def per_day_effects(prices, match_hours_by_day, matcher, control_days, feats):
    """Per-day match-hour effect for one subset of match days/hours."""
    per_day = []
    for d in sorted(d for d in match_hours_by_day if d in feats):
        hours = sorted(match_hours_by_day[d])
        p_match = price_on(prices, d, hours)
        if p_match is None:
            continue
        ctrl_prices = [price_on(prices, c, hours)
                       for c in matcher.controls(d, control_days)]
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
    return per_day


def stats_block(deltas):
    """Mean, sd, t and minimum detectable effect for a list of per-day deltas."""
    n = len(deltas)
    if n == 0:
        return {"n_match_days": 0, "mean_delta_ct_per_kwh": None, "t_stat": None,
                "interpretation": "no match days in this subset"}
    mean_delta = mean(deltas)
    # Sample SD (n-1): these are n observed per-day deltas, not a population.
    sd = (stdev(deltas) if n > 1 else 0.0) or 0.0
    t_stat = (mean_delta / (sd / math.sqrt(n))) if sd > 0 and n > 1 else float("nan")
    # Minimum detectable effect at 80% power, two-sided alpha=0.05:
    # (z_0.975 + z_0.80) * SE ~= 2.8 * sd / sqrt(n). A null result only rules
    # out effects at least this large; smaller ones would be invisible here.
    mde = (2.8 * sd / math.sqrt(n)) if (n > 1 and sd > 0) else None
    return {
        "n_match_days": n,
        "mean_delta_ct_per_kwh": round(mean_delta, 2),
        "std_ct": round(sd, 2),
        "t_stat": None if math.isnan(t_stat) else round(t_stat, 2),
        "mde_ct_80pct_power": None if mde is None else round(mde, 2),
        "interpretation": interpret(mean_delta, t_stat, n, sd),
    }


def main():
    prices = load_prices()
    feats = load_weather_daily()
    match_hours_by_day, germany_by_day, count_by_day = load_match_hours_by_day()

    match_days = sorted(d for d in match_hours_by_day if d in feats)
    control_days = [d for d in feats if d not in match_hours_by_day]

    if not match_days:
        raise SystemExit("No match days found. Fill in wc_matches.csv first.")
    if len(control_days) < K_CONTROLS:
        raise SystemExit("Not enough non-match control days in the window.")

    matcher = Matcher(feats)

    # Per-day effect: match-hour price minus comparable-day match-hour price
    per_day = per_day_effects(prices, match_hours_by_day, matcher,
                              control_days, feats)
    pairings = [{
        "date": d.isoformat(),
        "day_type": feats[d]["day_type"],
        "controls": matcher.controls(d, control_days, detailed=True),
    } for d in match_days]

    effect = stats_block([x["delta_ct"] for x in per_day])
    n = effect["n_match_days"]

    # Robustness: within-day difference-in-differences, which nets out the
    # day-level seasonal drift the main estimate inherits (controls are mostly
    # pre-tournament, match days are mid-June to mid-July).
    did = within_day_did(prices, match_days, match_hours_by_day, matcher,
                         control_days)

    # Germany subset: the single best-followed team in this market. Baseline
    # hours for its DiD exclude ALL match hours of the day, so parallel
    # matches don't contaminate the within-day contrast.
    germany_days = sorted(d for d in germany_by_day if d in feats)
    germany_per_day = per_day_effects(prices, germany_by_day, matcher,
                                      control_days, feats)
    germany = stats_block([x["delta_ct"] for x in germany_per_day])
    germany_did = within_day_did(prices, germany_days, germany_by_day, matcher,
                                 control_days,
                                 exclude_by_day=match_hours_by_day)

    # Hourly profile overlay: avg price by clock hour on match days vs their
    # controls, plus the min-max range across match days and the number of
    # matches live in each clock hour (both for the worldcup.html chart).
    match_prof, ctrl_prof, match_min, match_max = [], [], [], []
    match_count = [sum(count_by_day[d].get(h, 0) for d in match_days)
                   for h in range(24)]
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
        match_min.append(round(min(m_vals), 2) if m_vals else None)
        match_max.append(round(max(m_vals), 2) if m_vals else None)

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
            **effect,
            "t_caveat": ("per-day deltas share control days (pool smaller than "
                         "the match-day count), so they are positively correlated "
                         "and this t is optimistic"),
        },
        "robustness_within_day": did,
        "germany": {
            "effect": germany,
            "robustness_within_day": germany_did,
            "per_day": germany_per_day,
            "note": ("matches with Germany playing, from the label column of "
                     "wc_matches.csv; the single best-followed team, so the "
                     "best-powered single event despite the small n"),
        },
        "hourly_profile": {
            "hours": list(range(24)),
            "match_days_avg": match_prof,
            "match_days_min": match_min,
            "match_days_max": match_max,
            "match_count": match_count,
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
    print(f"Mean match-hour effect: {effect['mean_delta_ct_per_kwh']:+.2f} ct/kWh "
          f"(sd {effect['std_ct']:.2f}, t={effect['t_stat']}, "
          f"MDE~{effect['mde_ct_80pct_power']} ct/kWh)")
    if did:
        print(f"Within-day DiD robustness: {did['mean_delta_ct']:+.2f} ct/kWh "
              f"(t={did['t_stat']}), this contrast nets out seasonal drift")
    if germany["n_match_days"]:
        print(f"Germany subset ({germany['n_match_days']} match days): "
              f"{germany['mean_delta_ct_per_kwh']:+.2f} ct/kWh "
              f"(t={germany['t_stat']}, MDE~{germany['mde_ct_80pct_power']} ct/kWh)")
    print(f"-> {effect['interpretation']}")
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


def within_day_did(prices, match_days, match_hours_by_day, matcher, control_days,
                   exclude_by_day=None):
    """Difference-in-differences robustness check.

    The main estimate compares match hours ACROSS days, so any day-level drift
    between the (mostly pre-tournament) control period and the tournament
    period leaks into it. This contrast nets that out: per day, take
    (match-hour mean minus same-day non-match-hour mean), then compare that
    within-day contrast between each match day and its weather-matched controls.
    `exclude_by_day` widens which hours are dropped from the baseline (used by
    the Germany subset so parallel matches don't contaminate it).
    """
    exclude_by_day = exclude_by_day or match_hours_by_day
    deltas = []
    for d in match_days:
        hours = sorted(match_hours_by_day[d])
        others = [h for h in range(24)
                  if h not in exclude_by_day.get(d, set())]
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
    add_caption(fig, "Wholesale day-ahead prices. "
                "CEST = Central European Summer Time. "
                "\"Weather-comparable days\" are non-match days matched on "
                "temperature, solar, wind and day type (see matching.py), used "
                "as the counterfactual for what prices would have looked like "
                "without a match. Pink shading marks hours that were live-match "
                "hours on some match days; darker = a larger share of match "
                "days had a match that hour.")
    fig.subplots_adjust(bottom=0.26)
    fig.savefig(HERE / "wc_analysis.png", dpi=120)


if __name__ == "__main__":
    main()
