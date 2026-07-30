"""
R9: how good is the market's own day-ahead forecast? Day-ahead vs real time.

The project treats the day-ahead price as ground truth, which it is for the
household bill (a dynamic tariff settles at the day-ahead auction). But that
price is the outcome of an auction that clears on FORECAST demand and forecast
wind and solar, so it embodies the market's own day-ahead forecast. This study
measures how well that forecast holds up by comparing the day-ahead price
against the price that forms at real time: the German uniform imbalance price
(reBAP), the settlement price for schedule deviations.

(The first plan also compared against the intraday auction, but ENTSO-E does not
publish German intraday-auction or imbalance prices, and reBAP comes from
netztransparenz.de instead of ENTSO-E; see intraday_fetch.py. So R9 is now
day-ahead versus the real-time imbalance price, a single, zone-local signal.)

What it reports
---------------
1. Spread distribution, imbalance minus day-ahead, overall and by season, with
   BOTH mean/std and median/IQR because the imbalance price is fat-tailed and a
   mean alone would be dragged by a few scarcity hours (the tail is the signal,
   not noise to trim).
2. Systematic bias by hour of day: where the day-ahead price is consistently
   above or below the real-time price (e.g. it may under-price the evening ramp).
3. Volatility ratio: how much more variable the real-time price is than the
   day-ahead price, per season.
4. Rank stability of the cheapest three hours: how often the three cheapest
   day-ahead hours are still the three cheapest at real-time prices, and the
   extra cost of acting on the day-ahead ranking but valued at real time.

Honest framing
--------------
The household is billed at the day-ahead price no matter what real time does, so
none of this can change the household verdict. The euro figure is a hypothetical
for flexibility settled closer to delivery, not a household bill. Stated in the
output and on the page.

Inputs : intraday_prices.csv, intraday_meta.json (from intraday_fetch.py)
Outputs: intraday_results.json, intraday_analysis.png
Run    : python intraday_analysis.py
"""

import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
N_CHEAP = 3               # the EV-charge window used throughout the project
DAILY_KWH = 11.0          # same daily EV charge as cost_model.py, for the euro framing
SEASONS = {12: "winter", 1: "winter", 2: "winter",
           3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer",
           9: "autumn", 10: "autumn", 11: "autumn"}
SEASON_ORDER = ["winter", "spring", "summer", "autumn"]
# meteorological-season codes, matching ladder.html's convention
SEASON_CODE = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
               6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}


def load_rows():
    rows = []
    with open(HERE / "intraday_prices.csv") as f:
        for r in csv.DictReader(f):
            rows.append((dt.datetime.fromisoformat(r["datetime"]),
                         float(r["da_ct_per_kwh"]),
                         float(r["imbalance_ct_per_kwh"])))
    rows.sort()
    return rows


def meta():
    p = HERE / "intraday_meta.json"
    return json.load(open(p)) if p.exists() else {"data_source": "unknown"}


def dist(x):
    """Robust + classical summary of an array, in ct/kWh."""
    x = np.asarray(x, dtype=float)
    return {"mean": round(float(x.mean()), 3),
            "median": round(float(np.median(x)), 3),
            "std": round(float(x.std(ddof=1)), 3),
            "iqr": round(float(np.percentile(x, 75) - np.percentile(x, 25)), 3),
            "p05": round(float(np.percentile(x, 5)), 3),
            "p95": round(float(np.percentile(x, 95)), 3)}


def regret_concentration(regrets):
    """How unevenly the annual regret is earned across days.

    A single mean hides whether a number is a steady daily margin or a handful of
    extreme days, and those are different products: the first is a margin, the
    second is a readiness requirement. This emits the concentration curve (days
    ranked worst first, cumulative share of the annual total) plus the quantiles,
    so the page can show the shape rather than assert it.
    """
    if len(regrets) < 20:
        return None
    r = np.sort(np.asarray(regrets, dtype=float))[::-1]      # worst day first
    total = r.sum()
    if total <= 0:
        return None
    cum = np.cumsum(r) / total
    curve = []
    for pct in range(0, 101, 5):
        if pct == 0:
            curve.append({"day_share_pct": 0, "regret_share_pct": 0.0})
            continue
        idx = max(1, int(round(len(r) * pct / 100))) - 1
        curve.append({"day_share_pct": pct,
                      "regret_share_pct": round(float(100 * cum[idx]), 1)})
    return {
        "n_days": len(r),
        "curve": curve,
        "quantiles_ct": {q: round(float(np.percentile(regrets, q)), 3)
                         for q in (50, 75, 90, 95, 99)},
        "max_ct": round(float(r[0]), 3),
        "note": ("days ranked worst first; regret_share_pct is the cumulative "
                 "share of the year's total regret carried by that share of "
                 "days. A straight diagonal would mean every day contributes "
                 "equally."),
    }


def main():
    rows = load_rows()
    m = meta()
    t = np.array([r[0] for r in rows])
    da = np.array([r[1] for r in rows])
    imb = np.array([r[2] for r in rows])
    spread = imb - da

    overall = {
        "spread": dist(spread),
        "da_std": round(float(da.std(ddof=1)), 3),
        "imb_std": round(float(imb.std(ddof=1)), 3),
        "vol_ratio_imb": round(float(imb.std(ddof=1) / da.std(ddof=1)), 3),
        "corr_da_imb": round(float(np.corrcoef(da, imb)[0, 1]), 4),
    }

    # --- systematic bias by hour of day, per season (so the page can filter) ---
    # Median rather than mean on purpose: the imbalance price is heavy-tailed, so
    # a few extreme scarcity hours would dominate an average of a given hour; the
    # median reports the typical hour. Both are stored so the mean is available.
    hours = np.array([x.hour for x in t])
    dates = np.array([x.date() for x in t])
    season_code = np.array([SEASON_CODE[x.month] for x in t])

    def hour_block(mask):
        n_days = len(set(dates[mask].tolist()))
        out = []
        for h in range(24):
            hm = mask & (hours == h)
            if hm.sum() == 0:
                out.append({"hour": h, "median": None, "mean": None})
            else:
                out.append({"hour": h,
                            "median": round(float(np.median(spread[hm])), 3),
                            "mean": round(float(spread[hm].mean()), 3)})
        return {"n_days": n_days, "hours": out}

    by_hour = {"full": hour_block(np.ones(len(t), dtype=bool))}
    for code in ("DJF", "MAM", "JJA", "SON"):
        by_hour[code] = hour_block(season_code == code)

    # --- by season ---
    seas = np.array([SEASONS[x.month] for x in t])
    by_season = []
    for s in SEASON_ORDER:
        mask = seas == s
        if mask.sum() == 0:
            continue
        by_season.append({
            "season": s, "n_hours": int(mask.sum()),
            "spread_mean": round(float(spread[mask].mean()), 3),
            "spread_median": round(float(np.median(spread[mask])), 3),
            "vol_ratio_imb": round(float(imb[mask].std(ddof=1) / da[mask].std(ddof=1)), 3),
        })

    # --- rank stability of the cheapest N hours ---
    by_day = defaultdict(list)
    for x, d_, i_ in rows:
        by_day[x.date()].append((x.hour, d_, i_))
    overlaps, jaccards, regrets = [], [], []
    overlap_hist = [0] * (N_CHEAP + 1)
    for day, items in by_day.items():
        if len(items) < 20:                 # skip incomplete days (DST edges, gaps)
            continue
        items.sort()
        da_hours = {z[0] for z in sorted(items, key=lambda z: z[1])[:N_CHEAP]}
        imb_hours = {z[0] for z in sorted(items, key=lambda z: z[2])[:N_CHEAP]}
        ov = len(da_hours & imb_hours)
        overlaps.append(ov)
        overlap_hist[ov] += 1
        jaccards.append(ov / len(da_hours | imb_hours))
        imb_by_hour = {z[0]: z[2] for z in items}
        cost_da_pick = np.mean([imb_by_hour[h] for h in da_hours])
        cost_imb_pick = np.mean([imb_by_hour[h] for h in imb_hours])
        regrets.append(cost_da_pick - cost_imb_pick)
    n_days = len(overlaps)
    mean_regret = float(np.mean(regrets)) if regrets else 0.0
    # Mean AND median, because they answer different questions and the series is
    # fat-tailed. The annual euro figure is a SUM over days, and a sum is
    # n x mean by definition, so the mean is the right input for it: an aggregator
    # holding the position every day realises the mean, tail days included. The
    # median describes a typical day and is the honest answer to "what does this
    # look like on an ordinary Tuesday". Reporting only one of them misleads:
    # only the mean overstates the typical day, only the median understates the
    # year. The concentration share below says how unevenly the total is earned.
    med_regret = float(np.median(regrets)) if regrets else 0.0
    top_share = None
    if len(regrets) >= 20:
        r_sorted = np.sort(np.asarray(regrets, dtype=float))
        k = max(1, int(len(r_sorted) * 0.05))
        total = r_sorted.sum()
        if total > 0:
            top_share = round(float(100 * r_sorted[-k:].sum() / total), 1)
    rank_stability = {
        "n_days": n_days,
        "mean_overlap_of_3": round(float(np.mean(overlaps)), 3) if overlaps else None,
        "pct_full_overlap": round(100 * overlap_hist[N_CHEAP] / n_days, 1) if n_days else None,
        "mean_jaccard": round(float(np.mean(jaccards)), 3) if jaccards else None,
        "overlap_distribution": {str(k): overlap_hist[k] for k in range(N_CHEAP + 1)},
        "settlement_regret_ct_per_kwh": round(mean_regret, 4),
        "settlement_regret_eur_per_yr": round(mean_regret * DAILY_KWH * 365 / 100, 2),
        "settlement_regret_median_ct_per_kwh": round(med_regret, 4),
        "settlement_regret_median_day_eur_per_yr": round(med_regret * DAILY_KWH * 365 / 100, 2),
        "regret_share_from_top_5pct_days": top_share,
        "daily_kwh": DAILY_KWH,
        "regret_concentration": regret_concentration(regrets),
    }

    verdict = build_verdict(overall, rank_stability)
    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "data_source": m.get("data_source", "unknown"),
        "window": m.get("window"),
        "hours": len(rows),
        "n_cheap_hours": N_CHEAP,
        "signals": m.get("signals"),
        "overall": overall,
        "by_hour": by_hour,
        "by_season": by_season,
        "rank_stability": rank_stability,
        "verdict": verdict,
    }
    with open(HERE / "intraday_results.json", "w") as f:
        json.dump(results, f, indent=2)

    make_png(by_hour, by_season, rank_stability, m)
    report(results)


def build_verdict(overall, rank):
    sp = overall["spread"]
    good = abs(sp["median"]) < 0.5 and rank["pct_full_overlap"] is not None \
        and rank["pct_full_overlap"] >= 60
    lead = ("Day-ahead is a good proxy for the real-time price at household-relevant hours"
            if good else
            "Day-ahead and real time diverge enough to matter for delivery-close flexibility")
    return (f"{lead}: the real-time imbalance price sits a median "
            f"{sp['median']:+.2f} ct/kWh from day-ahead (IQR {sp['iqr']:.2f}, and a fat "
            f"tail from p05 {sp['p05']} to p95 {sp['p95']}), the three cheapest day-ahead "
            f"hours are still the three cheapest at real time on "
            f"{rank['pct_full_overlap']}% of days, and acting on the day-ahead ranking but "
            f"valuing it at real time would cost {rank['settlement_regret_ct_per_kwh']:+.3f} "
            f"ct/kWh (about {rank['settlement_regret_eur_per_yr']:+.0f} EUR/yr at "
            f"{rank['daily_kwh']:.0f} kWh/day). The household is billed at day-ahead "
            f"regardless, so this euro figure is a flexibility hypothetical, not a bill.")


def make_png(by_hour, by_season, rank, m):
    fig, ax = plt.subplots(1, 3, figsize=(16, 5))
    synth = str(m.get("data_source", "")).startswith("synthetic")
    src = "SYNTHETIC planted data" if synth else "netztransparenz (reBAP) + day-ahead"
    win = m.get("window", {})
    rng = f"{win.get('start','?')} .. {win.get('end','?')}"

    full = by_hour["full"]["hours"]
    n_full = by_hour["full"]["n_days"]
    hh = [b["hour"] for b in full]
    med = [b["median"] for b in full]
    ax[0].bar(hh, med, color=["#3377aa" if (m or 0) >= 0 else "#d6633c" for m in med])
    ax[0].axhline(0, color="#444", lw=0.8)
    ax[0].set_title(f"Day-ahead's systematic bias by hour, full year\n"
                    f"(real-time reBAP minus day-ahead, median over n={n_full} days)")
    ax[0].set_xlabel("hour of day (Europe/Berlin)")
    ax[0].set_ylabel("spread, ct/kWh (+ = day-ahead too cheap)")
    ax[0].set_xticks(range(0, 24, 3))

    ss = [b["season"] for b in by_season]
    x = np.arange(len(ss))
    ax[1].bar(x, [b["vol_ratio_imb"] for b in by_season], 0.6, color="#d6633c")
    ax[1].axhline(1, color="#444", lw=0.8, ls="--")
    ax[1].set_title("Real-time price volatility vs day-ahead, by season\n(ratio > 1 = more variable than day-ahead)")
    ax[1].set_xlabel("season")
    ax[1].set_ylabel("standard deviation ratio vs day-ahead")
    ax[1].set_xticks(x); ax[1].set_xticklabels(ss)

    od = rank["overlap_distribution"]
    ks = sorted(od, key=int)
    ax[2].bar(ks, [od[k] for k in ks], color="#59c", alpha=0.85)
    ax[2].set_title(f"Cheapest-3 ranking: day-ahead vs real time\n"
                    f"{rank['pct_full_overlap']}% of days keep all 3 hours (n={rank['n_days']} days)")
    ax[2].set_xlabel("number of the 3 cheapest hours shared")
    ax[2].set_ylabel("days")

    fig.suptitle(f"Day-ahead vs real-time reBAP (R9) | source: {src} | {rng}", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(HERE / "intraday_analysis.png", dpi=110)
    plt.close(fig)


def report(res):
    o = res["overall"]; r = res["rank_stability"]
    print(f"\nDay-ahead vs real-time reBAP (R9) | source: {res['data_source']}")
    print(f"Window {res['window']} | {res['hours']} hours\n")
    print(f"  reBAP-minus-day-ahead spread: mean {o['spread']['mean']:+.3f}, "
          f"median {o['spread']['median']:+.3f}, IQR {o['spread']['iqr']:.3f} ct/kWh "
          f"(fat tail: p05 {o['spread']['p05']}, p95 {o['spread']['p95']})")
    print(f"  real-time volatility vs day-ahead: x{o['vol_ratio_imb']}")
    print(f"  cheapest-3 ranking survives day-ahead->real-time on {r['pct_full_overlap']}% of "
          f"{r['n_days']} days (mean overlap {r['mean_overlap_of_3']}/3)")
    print(f"  settlement regret: mean {r['settlement_regret_ct_per_kwh']:+.3f} ct/kWh "
          f"(~{r['settlement_regret_eur_per_yr']:+.0f} EUR/yr, the annual total, "
          f"flexibility hypothetical)")
    print(f"                     median day {r['settlement_regret_median_ct_per_kwh']:+.3f} "
          f"ct/kWh"
          + (f"; top 5% of days carry {r['regret_share_from_top_5pct_days']:.0f}% of the total"
             if r.get("regret_share_from_top_5pct_days") is not None else ""))
    print(f"\n  Verdict: {res['verdict']}")
    print("\nWrote intraday_results.json and intraday_analysis.png")
    if str(res["data_source"]).startswith("synthetic"):
        print("NOTE: SYNTHETIC input. These numbers reflect the planted spread, "
              "not the real market. Fetch with netztransparenz credentials before trusting them.")


if __name__ == "__main__":
    main()
