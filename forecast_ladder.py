"""
The value-of-complexity study (ROADMAP backlog item 4, path one).

Question: how advanced does a cheap-hours forecasting algorithm need to be?
Not binary but a curve: a ladder of models from trivial to nonlinear, every
rung scored identically (hit-rate, cost, regret, euros/year) with the same
walk-forward backtest, reported per season. The deliverable is the rung where
the curve flattens: the point past which engineering stops paying for itself.

The ladder
----------
  climatology  cheapest-on-average hours over the last 28 days (rolling, so a
               winter day is judged against winter, not a full-history blur)
  persistence  yesterday's actual cheapest hours
  linear       the M5 model: daily harmonics, weekend, temperature, solar
  linear_rich  + annual harmonics, Saturday/Sunday-or-holiday day types,
               temperature squared, wind
  knn          nonlinear, dependency-free: find the 20 most similar past days
               (weather + day type, like matching.py) and predict each hour as
               their distance-weighted average price. Kernel regression.
  gbm          gradient boosting (scikit-learn), retrained weekly. OPTIONAL:
               runs only if scikit-learn is installed; the rest of the ladder
               never requires it.

Honest scope: all rungs see ACTUAL weather (a perfect weather forecast). This
flatters every weather-using rung equally, so the COMPARISON between rungs is
fair, but absolute skill is a ceiling, and the flattery grows in winter. The
deployed-realism version (archived weather forecasts) is future work.

Inputs : year_prices.csv / year_weather.csv (from year_fetch.py).
         Falls back to the 58-day wc_*.csv files as a SMOKE TEST with a loud
         warning; conclusions require the full year.
Outputs: forecast_ladder.json, forecast_ladder.png
Run    : python forecast_ladder.py
"""

import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matching import load_holidays

HERE = Path(__file__).parent
N_CHEAP = 3
WARMUP_DAYS = 28
CLIM_WINDOW = 28
KNN_K = 20
GBM_RETRAIN_DAYS = 7
EV_KWH, DAYS_PER_YEAR = 11.0, 365

try:
    from sklearn.ensemble import HistGradientBoostingRegressor
    HAVE_SKLEARN = True
except ImportError:
    HAVE_SKLEARN = False


def load():
    if (HERE / "year_prices.csv").exists():
        pf, wf, mode = "year_prices.csv", "year_weather.csv", "full-year"
    else:
        pf, wf, mode = "wc_prices.csv", "wc_weather.csv", "smoke-test"
        print("!! year_prices.csv missing: SMOKE TEST on the 58-day World Cup "
              "window. Run year_fetch.py for the real study.\n")
    price = {}
    with open(HERE / pf) as f:
        for r in csv.DictReader(f):
            price[dt.datetime.fromisoformat(r["datetime"])] = float(r["ct_per_kwh"])
    weather = {}
    with open(HERE / wf) as f:
        for r in csv.DictReader(f):
            weather[dt.datetime.fromisoformat(r["datetime"])] = (
                float(r["temp_c"]), float(r["cloud_pct"]),
                float(r["wind_kmh"]) if r.get("wind_kmh") else None,
                float(r["radiation_wm2"]) if r.get("radiation_wm2") else None)
    return price, weather, mode


def season(d):
    return {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
            6: "JJA", 7: "JJA", 8: "JJA"}.get(d.month, "SON")


def hour_features(t, w, holidays, rich):
    temp, cloud, wind, rad = w
    h = t.hour
    row = [1.0,
           math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24),
           math.sin(4 * math.pi * h / 24), math.cos(4 * math.pi * h / 24),
           temp]
    solar = rad if rad is not None else cloud
    if rad is not None:
        row.append(rad)
    else:
        midday = 1.0 if 10 <= h <= 15 else 0.0
        row += [cloud, midday * cloud]
    if not rich:
        row.append(1.0 if t.weekday() >= 5 else 0.0)
        return row
    doy = t.timetuple().tm_yday
    is_sunlike = 1.0 if (t.date() in holidays or t.weekday() == 6) else 0.0
    row += [math.sin(2 * math.pi * doy / 365), math.cos(2 * math.pi * doy / 365),
            1.0 if t.weekday() == 5 else 0.0, is_sunlike,
            temp * temp / 100.0,
            (wind if wind is not None else 0.0)]
    return row


def day_vector(day, hours_of, weather, holidays):
    """Daily summary vector for the knn rung (mirrors matching.py's features)."""
    ws = [weather[t] for t in hours_of[day]]
    temp = [w[0] for w in ws]
    solar = [(w[3] if w[3] is not None else -w[1]) for w in ws]  # rad, or -cloud
    wind = [w[2] for w in ws if w[2] is not None]
    dtype = 2.0 if (day in holidays or day.weekday() == 6) else (
        1.0 if day.weekday() == 5 else 0.0)
    return [sum(temp) / len(temp), max(temp), sum(solar) / len(solar),
            (sum(wind) / len(wind)) if wind else 0.0, dtype]


def main():
    price, weather, mode = load()
    holidays = load_holidays()
    by_day = defaultdict(list)
    for t in price:
        if t in weather:
            by_day[t.date()].append(t)
    days = sorted(d for d, ts in by_day.items() if len(ts) == 24)
    hours_of = {d: sorted(by_day[d]) for d in days}
    if len(days) <= WARMUP_DAYS + 5:
        raise SystemExit("Not enough full days.")

    def prices_of(d):
        return {t.hour: price[t] for t in hours_of[d]}

    def cheapest(pbh):
        return set(sorted(pbh, key=lambda h: pbh[h])[:N_CHEAP])

    # z-stats for knn day vectors (over all days; distances only rank)
    vecs = {d: day_vector(d, hours_of, weather, holidays) for d in days}
    arr = np.array([vecs[d] for d in days])
    mu, sd = arr.mean(axis=0), arr.std(axis=0)
    sd[sd == 0] = 1.0
    zvec = {d: (np.array(vecs[d]) - mu) / sd for d in days}

    rungs = ["climatology", "persistence", "linear", "linear_rich", "knn"]
    if HAVE_SKLEARN:
        rungs.append("gbm")
    else:
        print("(scikit-learn not installed: skipping the gbm rung; "
              "pip install scikit-learn to include it)\n")

    gbm, gbm_age = None, 10**9
    records = []
    for i in range(WARMUP_DAYS, len(days)):
        test, train = days[i], days[:i]
        actual = prices_of(test)
        actual_cheap = cheapest(actual)
        picks = {}

        clim_days = train[-CLIM_WINDOW:]
        picks["climatology"] = cheapest({
            h: float(np.mean([prices_of(d)[h] for d in clim_days])) for h in range(24)})
        picks["persistence"] = cheapest(prices_of(train[-1]))

        for name, rich in (("linear", False), ("linear_rich", True)):
            X = [hour_features(t, weather[t], holidays, rich)
                 for d in train for t in hours_of[d]]
            y = [price[t] for d in train for t in hours_of[d]]
            beta, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
            pred = {t.hour: float(np.dot(
                hour_features(t, weather[t], holidays, rich), beta))
                for t in hours_of[test]}
            picks[name] = cheapest(pred)

        dists = np.array([np.linalg.norm(zvec[test] - zvec[d]) for d in train])
        idx = np.argsort(dists)[:KNN_K]
        wts = 1.0 / (dists[idx] + 0.1)
        pred = {h: float(np.average([prices_of(train[j])[h] for j in idx],
                                    weights=wts)) for h in range(24)}
        picks["knn"] = cheapest(pred)

        if HAVE_SKLEARN:
            if gbm_age >= GBM_RETRAIN_DAYS:
                X = np.array([hour_features(t, weather[t], holidays, True) + [t.hour]
                              for d in train for t in hours_of[d]])
                y = np.array([price[t] for d in train for t in hours_of[d]])
                gbm = HistGradientBoostingRegressor(random_state=0).fit(X, y)
                gbm_age = 0
            gbm_age += 1
            Xt = np.array([hour_features(t, weather[t], holidays, True) + [t.hour]
                           for t in hours_of[test]])
            pred = dict(zip([t.hour for t in hours_of[test]],
                            [float(v) for v in gbm.predict(Xt)]))
            picks["gbm"] = cheapest(pred)

        rec = {"date": test.isoformat(), "season": season(test),
               "perfect_cost": float(np.mean([actual[h] for h in actual_cheap])),
               "all_day_cost": float(np.mean(list(actual.values())))}
        for name in rungs:
            rec[name] = {
                "hit": len(picks[name] & actual_cheap) / N_CHEAP,
                "cost": float(np.mean([actual[h] for h in picks[name]])),
            }
        records.append(rec)

    def agg(recs):
        out = {"n_days": len(recs),
               "perfect_cost": round(float(np.mean([r["perfect_cost"] for r in recs])), 3),
               "all_day_cost": round(float(np.mean([r["all_day_cost"] for r in recs])), 3),
               "rungs": {}}
        for name in rungs:
            cost = float(np.mean([r[name]["cost"] for r in recs]))
            out["rungs"][name] = {
                "hit_rate": round(float(np.mean([r[name]["hit"] for r in recs])), 3),
                "avg_cost_ct": round(cost, 3),
                "regret_ct": round(cost - out["perfect_cost"], 3),
                "eur_yr_saved_vs_anytime": round(
                    (out["all_day_cost"] - cost) * EV_KWH * DAYS_PER_YEAR / 100, 2),
            }
        return out

    seasons_present = sorted({r["season"] for r in records})
    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "mode": mode,
        "config": {"n_cheap_hours": N_CHEAP, "warmup_days": WARMUP_DAYS,
                   "climatology_window_days": CLIM_WINDOW, "knn_k": KNN_K,
                   "gbm_included": HAVE_SKLEARN,
                   "gbm_retrain_every_days": GBM_RETRAIN_DAYS,
                   "weather_input": "actuals (perfect-forecast ceiling; fair "
                                    "between rungs, flattering in absolute terms)"},
        "ladder_order": rungs,
        "overall": agg(records),
        "by_season": {s: agg([r for r in records if r["season"] == s])
                      for s in seasons_present},
    }
    with open(HERE / "forecast_ladder.json", "w") as f:
        json.dump(results, f, indent=2)
    plot(results)
    report(results)


def plot(res):
    rungs = res["ladder_order"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = range(len(rungs))
    ax.plot(x, [res["overall"]["rungs"][r]["regret_ct"] for r in rungs],
            marker="o", lw=2.5, color="#1c1c1c", label=f"overall ({res['overall']['n_days']}d)")
    palette = {"DJF": "#4c72b0", "MAM": "#4c9f70", "JJA": "#e0a458", "SON": "#c1436d"}
    for s, a in res["by_season"].items():
        ax.plot(x, [a["rungs"][r]["regret_ct"] for r in rungs], marker="o",
                lw=1.2, alpha=.8, color=palette.get(s, "#888"),
                label=f"{s} ({a['n_days']}d)")
    ax.set_xticks(list(x), rungs)
    ax.set_ylabel("Regret vs perfect foresight (ct/kWh; lower = better)")
    ax.set_title("Value of forecasting complexity: where does the curve flatten?"
                 + ("  [SMOKE TEST]" if res["mode"] != "full-year" else ""))
    ax.grid(True, alpha=.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "forecast_ladder.png", dpi=120)


def report(res):
    if res["mode"] != "full-year":
        print("!! SMOKE TEST on the short window; conclusions need year_fetch.py.\n")
    o = res["overall"]
    print(f"Value-of-complexity ladder | {o['n_days']} test days | "
          f"perfect {o['perfect_cost']:.2f} ct, anytime {o['all_day_cost']:.2f} ct\n")
    print(f"{'rung':<14}{'hit-rate':>9}{'regret ct':>11}{'€/yr saved':>12}")
    for r in res["ladder_order"]:
        a = o["rungs"][r]
        print(f"{r:<14}{a['hit_rate']:>9.2f}{a['regret_ct']:>11.2f}"
              f"{a['eur_yr_saved_vs_anytime']:>12.0f}")
    print("\nPer season (regret ct/kWh):")
    print(f"{'rung':<14}" + "".join(f"{s:>8}" for s in res["by_season"]))
    for r in res["ladder_order"]:
        print(f"{r:<14}" + "".join(
            f"{res['by_season'][s]['rungs'][r]['regret_ct']:>8.2f}"
            for s in res["by_season"]))
    print("\nWrote forecast_ladder.json and forecast_ladder.png")


if __name__ == "__main__":
    main()
