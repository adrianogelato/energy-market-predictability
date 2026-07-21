"""
Milestone 7 capstone: a permutation (placebo) test.

Why
---
The forecast-error study found a marginal overnight effect (t just over 2)
while prime time, where a viewing effect would have to be, was flat. Testing
several subsets (all / prime / overnight / Germany) means one can cross t=2 by
chance. This test quantifies that in two ways:

1. Per subset: if we label random days as "match days" and rerun the whole
   comparable-days analysis many times, how often is t as extreme as the real
   one? That fraction is a distribution-free p-value for that subset alone.
2. Family-wise: because several subsets were examined and the most extreme one
   is the one anyone would report, the honest reference is the null
   distribution of max|t| ACROSS all subsets. Each permutation draw
   relabels the days once and carries every day's subset membership along, so
   all subset t's come from the same draw, and their maximum forms the
   family-wise null. This is the number that answers "we looked several times,
   how surprising is the best-looking result?"

Method
------
Keep the real set of match-hour patterns (and each day's prime/overnight
membership), attach them to randomly chosen days, rebuild the weather-matched
controls from the remaining days, and recompute the effect t's. Repeating this
many times builds the null distributions.

Note: the real t here is recomputed with the same control scheme as the
permutations (controls = all other eligible days), so it can differ marginally
from wc_load_effect.py's number, which excludes every match day from controls.

Inputs : wc_load.csv, wc_weather.csv, wc_matches.csv
Outputs: wc_permutation_results.json, wc_permutation.png
Run    : python wc_permutation.py
"""

import datetime as dt
import json
from pathlib import Path
from statistics import mean

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matching import load_weather_daily, Matcher
from plot_utils import add_caption
from wc_load_effect import (
    load_error_and_actual, load_match_hours_split, compute_effect,
)

import os

HERE = Path(__file__).parent
# override with e.g. N_PERM=200 for a quick smoke run; default is the real test
N_PERM = int(os.environ.get("N_PERM", 2000))
SEED = 20260713
SUBSETS = ("all", "prime", "overnight", "germany")


def main():
    err, actual = load_error_and_actual()
    feats = load_weather_daily()
    splits = load_match_hours_split()
    err_days = {t.date() for t in err}

    eligible = sorted(d for d in feats if d in err_days)
    if len(eligible) < 20:
        raise SystemExit("Not enough eligible days.")
    matcher = Matcher(feats)
    mean_load = mean(actual.values())
    rng = np.random.default_rng(SEED)

    def effect_t(mhbd):
        control = [d for d in eligible if d not in mhbd]
        _, e = compute_effect(mhbd, err, err_days, matcher, control, mean_load)
        return e["t_stat"], e["mean_delta_mw"]

    # Real per-subset effects, with the same control scheme as the permutations.
    real = {}
    for name in SUBSETS:
        days = sorted(d for d in splits[name] if d in feats and d in err_days)
        t, delta = effect_t({d: splits[name][d] for d in days})
        real[name] = {"days": days, "t": 0.0 if t is None else t, "delta": delta}

    # Joint permutations: relabel the full match-day set once per draw, carry
    # subset membership along, and record all three t's plus their max|t|.
    all_days = real["all"]["days"]
    k = len(all_days)
    null_t = {name: [] for name in SUBSETS}
    null_max = []
    for _ in range(N_PERM):
        idx = rng.choice(len(eligible), size=k, replace=False)
        day_map = {orig: eligible[i] for orig, i in zip(all_days, idx)}
        draw_ts = {}
        for name in SUBSETS:
            fake = {day_map[d]: splits[name][d] for d in real[name]["days"]}
            t, _ = effect_t(fake)
            draw_ts[name] = 0.0 if t is None else t
            null_t[name].append(draw_ts[name])
        null_max.append(max(abs(v) for v in draw_ts.values()))

    out = {}
    for name in SUBSETS:
        nt = np.array(null_t[name])
        rt = real[name]["t"]
        out[name] = {
            "n_match_days": len(real[name]["days"]),
            "real_t": round(rt, 2),
            "real_delta_mw": real[name]["delta"],
            "p_value_two_sided": round(float((np.sum(np.abs(nt) >= abs(rt)) + 1) / (N_PERM + 1)), 3),
            "p_value_one_sided": round(float((np.sum(nt >= rt) + 1) / (N_PERM + 1)), 3),
            "null_t_95pct": round(float(np.percentile(np.abs(nt), 95)), 2),
        }

    null_max = np.array(null_max)
    real_max = max(abs(real[name]["t"]) for name in SUBSETS)
    family = {
        "real_max_abs_t": round(real_max, 2),
        "p_value": round(float((np.sum(null_max >= real_max) + 1) / (N_PERM + 1)), 3),
        "null_max_t_95pct": round(float(np.percentile(null_max, 95)), 2),
        "note": (f"null of max|t| across the {len(SUBSETS)} subsets from joint "
                 "draws; this is the correct reference when the most extreme of "
                 "several examined subsets is the one being reported"),
    }

    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "data_source": _load_source(),
        "n_permutations": N_PERM,
        "matching": matcher.describe(),
        "subsets": out,
        "family_wise": family,
    }
    with open(HERE / "wc_permutation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    plot(np.array(null_t["overnight"]), null_max, out["overnight"], family)
    report(results)


def _load_source():
    p = HERE / "wc_load_meta.json"
    return json.load(open(p)).get("data_source", "unknown") if p.exists() else "unknown"


def plot(null_overnight, null_max, ov, family):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    ax = axes[0]
    ax.hist(null_overnight, bins=40, color="#9bb", edgecolor="white")
    rt = ov["real_t"] or 0
    ax.axvline(rt, color="#c1436d", lw=2, label=f"real overnight t = {rt}")
    ax.axvline(-rt, color="#c1436d", lw=1, ls="--", alpha=0.5)
    ax.set_title(f"Placebo null: overnight t  (p two-sided = {ov['p_value_two_sided']})")
    ax.set_xlabel("t from random 'match' days")
    ax.set_ylabel("count")
    ax.legend()

    ax = axes[1]
    ax.hist(null_max, bins=40, color="#c9b", edgecolor="white")
    ax.axvline(family["real_max_abs_t"], color="#c1436d", lw=2,
               label=f"real max|t| = {family['real_max_abs_t']}")
    ax.set_title(f"Family-wise null: max|t| over {len(SUBSETS)} subsets  (p = {family['p_value']})")
    ax.set_xlabel("max|t| from random 'match' days")
    ax.legend()
    fig.tight_layout()
    add_caption(fig, "A placebo (permutation) test: relabel random days as "
                "\"match days\" thousands of times and recompute the effect, "
                "building a null distribution of what pure chance produces. "
                "t = a t-statistic, the estimated effect divided by its "
                "sampling noise; the pink line is the real observed value "
                "against that null. p = the share of random reruns that look "
                "at least as extreme as the real result — small p means the "
                "real effect is unlikely to be chance. Left: the overnight-kickoff "
                "subset only. Right: \"family-wise\" takes the largest |t| across "
                f"{len(SUBSETS)} subsets per random draw, correcting for having "
                "examined several subsets and reported the most extreme one.")
    fig.subplots_adjust(bottom=0.30)
    fig.savefig(HERE / "wc_permutation.png", dpi=120)


def report(s):
    if str(s["data_source"]).startswith("synthetic"):
        print("!! WARNING: load data is SYNTHETIC. p-values reflect the planted effect.\n")
    print(f"Permutation test, {s['n_permutations']} draws | data: {s['data_source']}\n")
    print(f"{'subset':<12}{'real t':>8}{'p (2-sided)':>13}{'p (1-sided)':>13}")
    for name in SUBSETS:
        e = s["subsets"][name]
        print(f"{name:<12}{str(e['real_t']):>8}{e['p_value_two_sided']:>13}{e['p_value_one_sided']:>13}")
    fam = s["family_wise"]
    print(f"\nFamily-wise (max|t| over the {len(SUBSETS)} subsets): "
          f"real={fam['real_max_abs_t']}, p={fam['p_value']}")
    ov = s["subsets"]["overnight"]
    worst_p = max(ov["p_value_two_sided"], fam["p_value"])
    verdict = ("NOT surprising: consistent with chance" if worst_p > 0.05
               else "survives the placebo test")
    print(f"Overnight effect -> {verdict} "
          f"(subset p={ov['p_value_two_sided']}, family-wise p={fam['p_value']}).")
    print("Wrote wc_permutation_results.json and wc_permutation.png")


if __name__ == "__main__":
    main()
