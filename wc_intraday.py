"""
R3: the World Cup price test in real time (day-ahead versus reBAP).

Why this exists
---------------
wc_analysis.py tests the World Cup against the DAY-AHEAD price. That price is
fixed in an auction at 12:00 the day before delivery, so it can only measure
whether traders ANTICIPATED a match effect, never whether a match caused a
real-time surprise. An unanticipated demand shift during a match shows up after
the auction closes: in the price that forms at delivery. In the German zone
that real-time price is the reBAP uniform imbalance price (see intraday_fetch.py
and the R9 study, intraday_analysis.py).

So this study asks: is the spread (reBAP minus day-ahead) systematically
different during match hours than on weather-comparable days? It reuses the
World Cup study's whole apparatus (the match-hour schedule, the matching.py
comparable-days engine, the Germany subset) but swaps the outcome variable from
the day-ahead price to the reBAP-minus-day-ahead spread.

Method
------
1. Outcome per hour = imbalance minus day-ahead, in ct/kWh (from
   intraday_prices.csv, the same file R9 uses).
2. Match day / match hours: identical to wc_analysis.py (wc_matches.csv).
3. For each match day, the k weather-comparable non-match days come from
   matching.py, exactly as in the day-ahead study.
4. Effect per match day = (median spread over its match hours) minus (median of
   the same-hours median spread across its comparable days). Median, not mean:
   reBAP is heavy-tailed and a few scarcity hours would drag an average (the
   same reason R9 leads with medians).
5. Headline effect = median of the per-day deltas. Inference is a permutation
   (placebo) test, not a t: relabel random eligible days as fake match days,
   rebuild the matched controls, recompute the median effect, and read the
   distribution-free p-value and the detectable-size bound off the null. A
   permutation test assumes nothing about the data being bell-shaped, which is
   the right choice for a fat-tailed spread. The Germany subset and a
   family-wise max|effect| correction mirror the rest of the World Cup page.
6. Every effect is reported twice: the headline matched comparison and the
   within-day contrast that nets out day-level drift. That applies to the Germany
   subset too, and matters most there, because all of Germany's match days fall in
   the tournament's first half where the drift sits. Quoting a Germany headline
   without its within-day number overstates it by a wide margin.

Coverage
--------
reBAP is published with a lag, so intraday_prices.csv can end before the
tournament does. The script reports which match days have no spread data yet
(n_match_days_total vs n_match_days_covered and the missing dates) so the page
can caveat the gap. Re-run after the next reBAP fetch to fill it in.

Honest framing
--------------
The household is billed at the day-ahead price no matter what real time does, so
none of this changes the household verdict. Any euro read is a hypothetical for
flexibility settled closer to delivery, not a household bill. Same caveat as R9.

Inputs : intraday_prices.csv, intraday_meta.json (reBAP + day-ahead, from
         intraday_fetch.py), wc_matches.csv, wc_weather.csv
Outputs: wc_intraday_results.json, wc_intraday.png
Run    : python wc_intraday.py   (or via run_all.py --skip-fetch)
"""

import csv
import datetime as dt
import json
import os
from collections import defaultdict
from pathlib import Path
from statistics import median

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matching import load_weather_daily, Matcher, K_CONTROLS
from wc_analysis import load_match_hours_by_day
from plot_utils import add_caption

HERE = Path(__file__).parent
N_PERM = int(os.environ.get("N_PERM", 2000))
SEED = 20260713
TOURNAMENT_END = dt.date(2026, 7, 19)


def load_spread():
    """{datetime: imbalance - day-ahead} in ct/kWh, Europe/Berlin local hours.

    The datetimes line up hour-for-hour with wc_prices.csv (both local naive,
    verified: shared day-ahead values agree to 0.003 ct), so the match-hour
    schedule joins directly.
    """
    spread = {}
    with open(HERE / "intraday_prices.csv") as f:
        for r in csv.DictReader(f):
            t = dt.datetime.fromisoformat(r["datetime"])
            spread[t] = float(r["imbalance_ct_per_kwh"]) - float(r["da_ct_per_kwh"])
    return spread


def meta_source():
    p = HERE / "intraday_meta.json"
    return json.load(open(p)).get("data_source", "unknown") if p.exists() else "unknown"


def spread_on(spread, date, hours):
    """Median spread on `date` over the given clock `hours` (skip missing)."""
    vals = [spread[dt.datetime(date.year, date.month, date.day, h)]
            for h in hours
            if dt.datetime(date.year, date.month, date.day, h) in spread]
    return median(vals) if vals else None


def per_day_deltas(spread, match_hours_by_day, matcher, control_days):
    """Per match day: (median match-hour spread) minus (median of the controls'
    same-hours median spread). Returns the detail rows and the delta list."""
    rows, deltas = [], []
    for d in sorted(match_hours_by_day):
        hours = sorted(match_hours_by_day[d])
        s_match = spread_on(spread, d, hours)
        if s_match is None:
            continue
        ctrl = [spread_on(spread, c, hours)
                for c in matcher.controls(d, control_days)]
        ctrl = [s for s in ctrl if s is not None]
        if not ctrl:
            continue
        s_ctrl = median(ctrl)
        # Only the DELTA is published, deliberately. The absolute match-hour and
        # comparable-day spreads are withheld because wc_results.json commits the
        # day-ahead price for the same date and hour window, so publishing an
        # absolute spread beside it would let the two committed files be joined to
        # reconstruct the reBAP level (verified: exact on some days, ~1.4 ct/kWh
        # mean error across the set). netztransparenz grants no reuse licence for
        # the reBAP, so this project keeps the series local (see NOTICE); a
        # joinable pair of committed files would undo that. The delta is a
        # difference of differences against unpublished control days and cannot
        # recover a level, and it is the only field the analysis or the page uses.
        rows.append({
            "date": d.isoformat(),
            "match_hours": hours,
            "delta_ct": round(s_match - s_ctrl, 2),
        })
        deltas.append(s_match - s_ctrl)
    return rows, deltas


def within_day_did(spread, match_hours_by_day, matcher, control_days,
                   exclude_by_day=None):
    """Difference-in-differences robustness, median form.

    The headline effect compares match hours ACROSS days, so any day-level drift
    between the (mostly pre-tournament) control period and the tournament period
    leaks into it: if the reBAP spread simply ran higher all summer, match days
    look elevated at every hour and the headline mis-reads that as a match
    effect. This contrast nets it out. Per day take (median match-hour spread
    minus median same-day non-match-hour spread), then subtract the same
    within-day contrast on the weather-matched controls. `exclude_by_day` widens
    which hours are dropped from the baseline (the Germany subset drops ALL match
    hours so parallel matches do not contaminate the baseline)."""
    exclude_by_day = exclude_by_day or match_hours_by_day
    deltas = []
    for d in sorted(match_hours_by_day):
        hours = sorted(match_hours_by_day[d])
        others = [h for h in range(24) if h not in exclude_by_day.get(d, set())]
        sm = spread_on(spread, d, hours)
        so = spread_on(spread, d, others)
        if sm is None or so is None:
            continue
        ctrl = []
        for c in matcher.controls(d, control_days):
            cm = spread_on(spread, c, hours)
            co = spread_on(spread, c, others)
            if cm is not None and co is not None:
                ctrl.append(cm - co)
        if not ctrl:
            continue
        deltas.append((sm - so) - median(ctrl))
    return deltas


def day_level_drift(spread, match_days, control_days):
    """Median daily spread over ALL 24 hours, match days versus control days.

    This is the diagnostic that turns "the headline might be drift" into a
    measured statement. A match occupies two to four hours, so it cannot move a
    day's 24-hour median. Whatever gap shows up here is period drift, and the
    headline estimator (which compares match hours across days) inherits it.
    """
    def daily_medians(days):
        out = []
        for d in days:
            vals = [spread[k] for k in (dt.datetime(d.year, d.month, d.day, h)
                                        for h in range(24)) if k in spread]
            if len(vals) >= 20:
                out.append(median(vals))
        return out

    m, c = daily_medians(match_days), daily_medians(control_days)
    if not m or not c:
        return None
    return {
        "match_days_median_ct": round(median(m), 2),
        "control_days_median_ct": round(median(c), 2),
        "difference_ct": round(median(m) - median(c), 2),
        "n_match_days": len(m),
        "n_control_days": len(c),
        "note": ("median spread across ALL 24 hours of a day, not just match "
                 "hours. A two-to-four-hour match cannot shift a 24-hour median, "
                 "so a non-zero difference is period drift that the headline "
                 "estimator absorbs and the within-day contrast removes."),
    }


def calendar_split(rows):
    """Per-day headline effects grouped by calendar month.

    If the effect is caused by matches it should not care which month a match
    falls in, and if anything it should be larger in the knockout stage. If it
    is caused by drift it tracks the calendar. This makes that check visible
    instead of leaving it to a reader with the raw data.
    """
    by_month = defaultdict(list)
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        by_month[f"{d.year}-{d.month:02d}"].append(r["delta_ct"])
    return [{"month": k, "n_match_days": len(v),
             "median_effect_ct": round(float(median(v)), 2)}
            for k, v in sorted(by_month.items())]


def effect_block(deltas):
    """Median effect and IQR of the per-day deltas (ct/kWh)."""
    if not deltas:
        return {"n_match_days": 0, "median_effect_ct": None,
                "interpretation": "no covered match days in this subset"}
    a = np.asarray(deltas, dtype=float)
    return {
        "n_match_days": len(deltas),
        "median_effect_ct": round(float(np.median(a)), 2),
        "iqr_ct": round(float(np.percentile(a, 75) - np.percentile(a, 25)), 2),
    }


def permutation(spread, subset_hours_by_day, eligible, matcher, real_effect,
                deltas_fn=None):
    """Distribution-free p-value for the median effect, plus a detectable-size
    bound. Relabels len(subset) random eligible days as fake match days
    (carrying the match-hour patterns), rebuilds controls from the rest, and
    recomputes the median effect many times. `deltas_fn(fake, control)` selects
    the estimator (headline per-day deltas by default, or the within-day DiD)."""
    if deltas_fn is None:
        deltas_fn = lambda fake, control: per_day_deltas(
            spread, fake, matcher, control)[1]
    real_days = sorted(subset_hours_by_day)
    k = len(real_days)
    if k == 0 or real_effect is None:
        return None
    patterns = [sorted(subset_hours_by_day[d]) for d in real_days]
    rng = np.random.default_rng(SEED)
    null = []
    for _ in range(N_PERM):
        idx = rng.choice(len(eligible), size=k, replace=False)
        fake = {eligible[i]: set(pat) for i, pat in zip(idx, patterns)}
        control = [d for d in eligible if d not in fake]
        deltas = deltas_fn(fake, control)
        null.append(float(np.median(deltas)) if deltas else 0.0)
    null = np.array(null)
    return {
        "n_permutations": N_PERM,
        "p_value_two_sided": round(float((np.sum(np.abs(null) >= abs(real_effect)) + 1)
                                          / (N_PERM + 1)), 3),
        "null_effect_p95_ct": round(float(np.percentile(np.abs(null), 95)), 2),
        "null": null,
    }


def coverage_clause(missing):
    """Data-driven coverage caveat. Hardcoding the number of uncovered days went
    stale the moment a later reBAP fetch filled some of them in."""
    if not missing:
        return " The tournament is fully covered."
    if len(missing) == 1:
        return f" One match day ({missing[0]}) is still uncovered."
    return f" {len(missing)} match days are still uncovered ({', '.join(missing)})."


def interpret(eff, perm, did=None, perm_did=None, missing=None,
              g_eff=None, g_did=None, perm_g=None, perm_g_did=None):
    if not eff or eff.get("median_effect_ct") is None:
        return "No covered match days yet; re-run after the next reBAP fetch."
    e = eff["median_effect_ct"]
    if perm is None:
        return f"Median match-hour spread effect {e:+.2f} ct/kWh (no inference)."
    p = perm["p_value_two_sided"]
    bound = perm["null_effect_p95_ct"]
    if p > 0.05:
        # The bound here is the placebo null's 95th percentile, not the 80%-power
        # MDE the other two studies report, so it is worded as a chance ceiling
        # and matches the estimator chart's legend rather than their phrasing.
        return (f"The median reBAP-minus-day-ahead spread in match hours runs "
                f"{e:+.2f} ct/kWh versus comparable days, but a placebo test puts "
                f"that at p={p:.2f}, so chance produces a shift this large "
                f"routinely. Only effects above about {bound:.2f} ct/kWh would "
                f"have cleared what chance produces. No detectable real-time "
                f"effect.")
    # Headline clears the bar. The trustworthy read is the within-day contrast,
    # because the controls are mostly pre-tournament and the spread drifts.
    direction = "above" if e > 0 else "below"
    lead = (f"In the raw matched comparison, match-hour real-time prices settle "
            f"{abs(e):.2f} ct/kWh {direction} day-ahead versus comparable days "
            f"(placebo p={p:.2f}), i.e. the auction under-priced these hours.")
    # The Germany subset is the number a reader will quote, so its own drift check
    # is stated in the same breath rather than left in the JSON to be found.
    g_clause = ""
    ge = g_eff.get("median_effect_ct") if g_eff else None
    gp = perm_g["p_value_two_sided"] if perm_g else None
    gd = g_did.get("median_effect_ct") if g_did else None
    gdp = perm_g_did["p_value_two_sided"] if perm_g_did else None
    if ge is not None and gd is not None and gdp is not None:
        if gdp > 0.05:
            g_clause = (f" The Germany subset looks larger still ({ge:+.2f} ct/kWh"
                        + (f", p={gp:.2f}" if gp is not None else "")
                        + f"), but it is the most drift-exposed figure here: all its "
                        f"match days sit in the tournament's first half. Under the "
                        f"same within-day contrast it collapses to {gd:+.2f} ct/kWh "
                        f"at p={gdp:.2f}. It is not evidence of an effect.")
        else:
            g_clause = (f" The Germany subset ({ge:+.2f} ct/kWh) also survives the "
                        f"within-day contrast at {gd:+.2f} ct/kWh, p={gdp:.2f}, on "
                        f"{g_eff.get('n_match_days')} days.")

    dm = did.get("median_effect_ct") if did else None
    dp = perm_did["p_value_two_sided"] if perm_did else None
    cov = coverage_clause(missing)
    if dm is not None and dp is not None:
        if dp > 0.05:
            return (lead + f" But the drift-robust within-day contrast (match hours "
                    f"minus the same day's other hours, versus controls) shrinks it "
                    f"to {dm:+.2f} ct/kWh at p={dp:.2f}. Most of the headline is a "
                    f"general rise in the spread across the tournament window rather "
                    f"than a match-hour effect. No real-time effect survives that "
                    f"correction." + g_clause + cov)
        return (lead + f" It survives the drift-robust within-day contrast "
                f"({dm:+.2f} ct/kWh, p={dp:.2f})." + g_clause + cov)
    return (lead + " Check the within-day difference-in-differences contrast "
            "before over-reading it." + cov)


def main():
    spread = load_spread()
    feats = load_weather_daily()
    match_hours_by_day, germany_by_day, count_by_day = load_match_hours_by_day()

    covered = {t.date() for t in spread}
    all_match_days = sorted(d for d in match_hours_by_day if d in feats)
    # A match day is analysable only if the reBAP file actually covers it.
    match_days = [d for d in all_match_days if d in covered]
    missing = [d.isoformat() for d in all_match_days if d not in covered]
    control_days = [d for d in feats if d not in match_hours_by_day and d in covered]

    if not match_days:
        raise SystemExit("No covered match days: intraday_prices.csv does not "
                         "overlap the tournament. Fetch reBAP first.")
    if len(control_days) < K_CONTROLS:
        raise SystemExit("Not enough covered non-match control days.")

    matcher = Matcher(feats)

    covered_hours = {d: match_hours_by_day[d] for d in match_days}
    rows, deltas = per_day_deltas(spread, covered_hours, matcher, control_days)
    effect = effect_block(deltas)

    germany_covered = {d: germany_by_day[d] for d in sorted(germany_by_day)
                       if d in feats and d in covered}
    g_rows, g_deltas = per_day_deltas(spread, germany_covered, matcher, control_days)
    germany = effect_block(g_deltas)

    # Robustness: within-day diff-in-diff, which nets out any day-level drift in
    # the spread between the (mostly pre-tournament) controls and the tournament.
    did_deltas = within_day_did(spread, covered_hours, matcher, control_days)
    did = effect_block(did_deltas)

    # The Germany subset needs the SAME drift check, and needs it more than the
    # pooled estimate does: every Germany match day falls in the first half of
    # the tournament, which is exactly where the day-level drift sits, so its
    # headline number is the most drift-exposed figure in the study. The baseline
    # excludes ALL match hours (not just Germany's) so that hours occupied by
    # other teams' parallel matches cannot contaminate the same-day comparison.
    g_did_deltas = within_day_did(spread, germany_covered, matcher, control_days,
                                  exclude_by_day=match_hours_by_day)
    g_did = effect_block(g_did_deltas)

    eligible = sorted(set(match_days) | set(control_days))
    perm_all = permutation(spread, covered_hours, eligible, matcher,
                           effect.get("median_effect_ct"))
    perm_did = permutation(
        spread, covered_hours, eligible, matcher, did.get("median_effect_ct"),
        deltas_fn=lambda fake, control: within_day_did(spread, fake, matcher, control))
    perm_g = permutation(spread, germany_covered, eligible, matcher,
                         germany.get("median_effect_ct")) if g_deltas else None
    perm_g_did = permutation(
        spread, germany_covered, eligible, matcher, g_did.get("median_effect_ct"),
        deltas_fn=lambda fake, control: within_day_did(
            spread, fake, matcher, control, exclude_by_day=match_hours_by_day)
    ) if g_did_deltas else None

    # Family-wise: the largest |effect| across the two examined subsets, judged
    # against the null of the same maximum. Uses the two subsets' joint null
    # only loosely (each has its own draws), so it is reported as a guard, not a
    # precise joint test; with two subsets the correction is small.
    #
    # Reported on BOTH estimators. The headline family-wise is the more extreme of
    # two drift-exposed numbers, so on its own it is the wrong guard to quote: the
    # drift-robust family-wise is the one that decides whether anything survives.
    def family_block(pa, pg, ea, eg, note):
        if not (pa and pg) or ea is None or eg is None:
            return None
        real_max = max(abs(ea), abs(eg))
        joint_null = np.maximum(np.abs(pa["null"]), np.abs(pg["null"]))
        return {
            "real_max_abs_effect_ct": round(real_max, 2),
            "p_value": round(float((np.sum(joint_null >= real_max) + 1) / (N_PERM + 1)), 3),
            "note": note,
        }

    family = family_block(
        perm_all, perm_g, effect.get("median_effect_ct"),
        germany.get("median_effect_ct"),
        "max|median effect| across the all-matches and Germany subsets against "
        "the joint null; guards against reporting the more extreme of the two. "
        "Headline estimator, so still drift-exposed: read family_wise_within_day.")
    family_did = family_block(
        perm_did, perm_g_did, did.get("median_effect_ct"),
        g_did.get("median_effect_ct"),
        "same guard on the drift-robust within-day contrast; this is the "
        "family-wise number to quote.")

    # Hourly profile: the chart. Median spread by clock hour, match-day match
    # hours vs pooled comparable-day hours, plus exposure weighting.
    match_spread_h, ctrl_spread_h, match_count = [], [], []
    for h in range(24):
        m_vals = [spread[dt.datetime(d.year, d.month, d.day, h)]
                  for d in match_days
                  if dt.datetime(d.year, d.month, d.day, h) in spread]
        c_vals = []
        for d in match_days:
            for c in matcher.controls(d, control_days):
                key = dt.datetime(c.year, c.month, c.day, h)
                if key in spread:
                    c_vals.append(spread[key])
        match_spread_h.append(round(float(np.median(m_vals)), 2) if m_vals else None)
        ctrl_spread_h.append(round(float(np.median(c_vals)), 2) if c_vals else None)
        match_count.append(sum(count_by_day[d].get(h, 0) for d in match_days))

    match_hour_share = [round(float(np.mean([1.0 if h in match_hours_by_day[d] else 0.0
                                             for d in match_days])), 2)
                        for h in range(24)]

    window = {"start": min(covered).isoformat(), "end": max(covered).isoformat()}
    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "data_source": meta_source(),
        "outcome": "imbalance (reBAP) minus day-ahead, ct/kWh",
        "window": window,
        "n_match_days_total": len(all_match_days),
        "n_match_days_covered": len(match_days),
        "match_days_missing_rebap": missing,
        "coverage_complete": not missing and max(covered) >= TOURNAMENT_END,
        "n_control_pool": len(control_days),
        "k_controls_per_day": K_CONTROLS,
        "matching": matcher.describe(),
        "effect": {
            **effect,
            "permutation": {k: v for k, v in (perm_all or {}).items() if k != "null"} or None,
            "interpretation": interpret(effect, perm_all, did, perm_did,
                                       missing=missing, g_eff=germany, g_did=g_did,
                                       perm_g=perm_g, perm_g_did=perm_g_did),
        },
        "robustness_within_day": {
            **did,
            "permutation": {k: v for k, v in (perm_did or {}).items() if k != "null"} or None,
            "note": ("within-day contrast (match hours minus same-day non-match "
                     "hours), match day vs weather-matched controls; nets out the "
                     "day-level drift the headline estimate inherits. If it "
                     "collapses toward zero, the headline was period drift, not "
                     "matches."),
        },
        "germany": {
            "effect": {
                **germany,
                "permutation": {k: v for k, v in (perm_g or {}).items() if k != "null"} or None,
            },
            "robustness_within_day": {
                **g_did,
                "permutation": {k: v for k, v in (perm_g_did or {}).items() if k != "null"} or None,
                "note": ("same within-day contrast as the pooled estimate, baseline "
                         "excluding all match hours. Germany's match days all fall in "
                         "the drift-heavy first half of the tournament, so the headline "
                         "Germany figure must not be read without this."),
            },
            "note": ("matches with Germany playing (label column of "
                     "wc_matches.csv); best-followed team, smallest sample"),
        },
        "family_wise": family,
        "family_wise_within_day": family_did,
        "day_level_drift": day_level_drift(spread, match_days, control_days),
        "calendar_split": calendar_split(rows),
        "hourly_profile": {
            "hours": list(range(24)),
            "match_days_spread_median": match_spread_h,
            "comparable_days_spread_median": ctrl_spread_h,
            "match_count": match_count,
            "match_hour_share": match_hour_share,
        },
        "per_day": rows,
        "framing": ("Real-time (reBAP) versus day-ahead. The household is billed "
                    "at day-ahead regardless, so this cannot move the household "
                    "verdict; it speaks to flexibility settled closer to delivery."),
    }
    with open(HERE / "wc_intraday_results.json", "w") as f:
        json.dump(results, f, indent=2)

    plot(results)
    report(results)


def plot(res):
    hp = res["hourly_profile"]
    hours = hp["hours"]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.axhline(0, color="#999", lw=1)
    ax.plot(hours, hp["match_days_spread_median"], marker="o", ms=3,
            label="Match days", color="#c1436d")
    ax.plot(hours, hp["comparable_days_spread_median"], marker="o", ms=3,
            label="Weather-comparable days", color="#4c9f70")
    for h, share in zip(hours, hp["match_hour_share"]):
        if share:
            ax.axvspan(h - 0.5, h + 0.5, color="#c1436d", alpha=0.30 * share)
    eff = res["effect"]
    perm = eff.get("permutation")
    ptxt = f", placebo p={perm['p_value_two_sided']}" if perm else ""
    ax.set_title(f"Real-time minus day-ahead spread by hour: match days vs "
                 f"comparable days (match-hour effect "
                 f"{eff['median_effect_ct']:+.2f} ct/kWh{ptxt})")
    ax.set_xlabel("Hour of day (CEST)  |  shading = share of match days with a "
                  "match that hour")
    ax.set_ylabel("Median (reBAP minus day-ahead), ct/kWh")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    cov = (f"reBAP covers {res['n_match_days_covered']} of "
           f"{res['n_match_days_total']} match days; "
           + (f"missing {', '.join(res['match_days_missing_rebap'])}. "
              if res["match_days_missing_rebap"] else "full tournament. "))
    add_caption(fig, cov +
                "reBAP = the German uniform imbalance price, the settlement price "
                "for schedule deviations, published by netztransparenz.de; the "
                "real-time price against the day-ahead auction price. CEST = "
                "Central European Summer Time. Positive = real time settled above "
                "day-ahead, i.e. the auction under-priced the hour. Median, not "
                "mean, because the imbalance price is heavy-tailed. "
                "\"Weather-comparable days\" are non-match days matched on "
                "temperature, solar, wind and day type (matching.py). Household "
                "bills settle at day-ahead regardless; this speaks to flexibility "
                "settled closer to delivery.")
    fig.subplots_adjust(bottom=0.30)
    fig.savefig(HERE / "wc_intraday.png", dpi=120)


def report(res):
    src = res["data_source"]
    if str(src).startswith("synthetic"):
        print(f"!! WARNING: reBAP data is SYNTHETIC ({src}). Numbers are a "
              f"pipeline test, not a result.\n")
    e = res["effect"]
    print(f"R3 World Cup real-time test | data: {src}")
    print(f"Coverage: {res['n_match_days_covered']}/{res['n_match_days_total']} "
          f"match days"
          + (f" (missing {', '.join(res['match_days_missing_rebap'])})"
             if res["match_days_missing_rebap"] else " (full tournament)"))
    perm = e.get("permutation")
    print(f"Median match-hour spread effect: {e['median_effect_ct']:+.2f} ct/kWh"
          + (f" | placebo p={perm['p_value_two_sided']} | detectable above "
             f"~{perm['null_effect_p95_ct']} ct/kWh" if perm else ""))
    did = res["robustness_within_day"]
    if did.get("median_effect_ct") is not None:
        dp = did.get("permutation")
        print(f"Within-day diff-in-diff (nets out drift): "
              f"{did['median_effect_ct']:+.2f} ct/kWh"
              + (f" | placebo p={dp['p_value_two_sided']}" if dp else ""))
    g = res["germany"]["effect"]
    if g.get("median_effect_ct") is not None:
        gp = g.get("permutation")
        print(f"Germany subset ({g['n_match_days']} days): "
              f"{g['median_effect_ct']:+.2f} ct/kWh"
              + (f" | placebo p={gp['p_value_two_sided']}" if gp else "")
              + "   <- headline, drift-exposed")
    gd = res["germany"].get("robustness_within_day") or {}
    if gd.get("median_effect_ct") is not None:
        gdp = gd.get("permutation")
        print(f"Germany within-day diff-in-diff: {gd['median_effect_ct']:+.2f} ct/kWh"
              + (f" | placebo p={gdp['p_value_two_sided']}" if gdp else "")
              + "   <- the one to read")
    if res["family_wise"]:
        print(f"Family-wise, headline (max|effect| over 2 subsets): "
              f"real={res['family_wise']['real_max_abs_effect_ct']}, "
              f"p={res['family_wise']['p_value']}")
    if res.get("family_wise_within_day"):
        print(f"Family-wise, drift-robust: "
              f"real={res['family_wise_within_day']['real_max_abs_effect_ct']}, "
              f"p={res['family_wise_within_day']['p_value']}")
    print(f"-> {e['interpretation']}")
    print("Wrote wc_intraday_results.json and wc_intraday.png")


if __name__ == "__main__":
    main()
