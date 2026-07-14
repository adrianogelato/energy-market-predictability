"""
Milestone 5: the cheapest-hours forecaster (the building block).

Question (hypothesis H1 in ROADMAP.md)
--------------------------------------
Can we predict tomorrow's N cheapest hours from weather and the calendar, well
enough to beat naive guessing? If not, nothing downstream (event effects,
flexibility value) is measurable.

What it does
------------
For each test day, it trains a small linear model on all earlier days
(expanding-window walk-forward, the honest way to backtest a time series),
predicts the price of each hour, and picks the N lowest as the predicted cheap
hours. It then scores that against reality and against two baselines.

Baselines it must beat
----------------------
  persistence : tomorrow's cheap hours = yesterday's actual cheap hours
  climatology : the hours that are cheapest on average in the training data

Metrics
-------
  hit-rate  : share of the N predicted hours that are truly in the N cheapest
  cost      : what you actually pay charging in the chosen hours (real prices)
  regret    : cost minus the perfect-foresight cost (0 = perfect)

Honest simplification
---------------------
The backtest uses actual weather as a stand-in for a perfect weather forecast.
This measures the ceiling: how much the *price* signal is learnable from weather.
A deployed version would feed open-meteo's forecast instead, and score slightly
worse. This is stated so the number is not oversold.

Inputs : wc_prices.csv, wc_weather.csv  (run wc_fetch_data.py first)
Outputs: forecast_results.json, forecast_backtest.png
Run    : python forecast_cheap_hours.py
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

HERE = Path(__file__).parent
N_CHEAP = 3          # how many cheap hours we care about (the EV-charge window)
INIT_TRAIN_DAYS = 21  # warm-up before the first prediction


def load():
    price = {}
    with open(HERE / "wc_prices.csv") as f:
        for r in csv.DictReader(f):
            price[dt.datetime.fromisoformat(r["datetime"])] = float(r["ct_per_kwh"])
    weather = {}
    with open(HERE / "wc_weather.csv") as f:
        for r in csv.DictReader(f):
            rad = float(r["radiation_wm2"]) if r.get("radiation_wm2") else None
            weather[dt.datetime.fromisoformat(r["datetime"])] = (
                float(r["temp_c"]), float(r["cloud_pct"]), rad)
    return price, weather


def features(t, temp, cloud, rad=None):
    """Feature row for one hour. Harmonics capture the daily shape.

    Solar enters as shortwave radiation when the weather file carries it
    (the same upgrade the matching engine got): radiation is the actual PV
    driver and already encodes the daylight curve, so it replaces both the
    cloud term and the hand-built cloud-at-midday interaction. On older
    weather files the cloud + midday proxy is used, so results stay
    reproducible either way.
    """
    h = t.hour
    is_weekend = 1.0 if t.weekday() >= 5 else 0.0
    base = [
        1.0,
        math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24),
        math.sin(4 * math.pi * h / 24), math.cos(4 * math.pi * h / 24),
        is_weekend,
        temp,
    ]
    if rad is not None:
        base.append(rad)      # W/m^2; more radiation -> more PV -> lower price
    else:
        midday = 1.0 if 10 <= h <= 15 else 0.0
        base += [cloud, midday * cloud]  # cloud matters most when blocking midday solar
    return base


def day_hours(price, weather):
    """Return sorted list of days that have all 24 hours in both series."""
    by_day = defaultdict(list)
    for t in price:
        if t in weather:
            by_day[t.date()].append(t)
    return sorted(d for d, hrs in by_day.items() if len(hrs) == 24)


def cheapest(prices_by_hour, n):
    """Indices (hours 0..23) of the n cheapest, given a dict hour->price."""
    return set(sorted(range(24), key=lambda h: prices_by_hour[h])[:n])


def main():
    price, weather = load()
    days = day_hours(price, weather)
    if len(days) <= INIT_TRAIN_DAYS + 2:
        raise SystemExit("Not enough full days to backtest.")

    def prices_of(day):
        return {h: price[dt.datetime(day.year, day.month, day.day, h)] for h in range(24)}

    records = []
    for i in range(INIT_TRAIN_DAYS, len(days)):
        test_day = days[i]
        train_days = days[:i]

        # Fit linear model on all earlier hours
        X, y = [], []
        for d in train_days:
            for h in range(24):
                t = dt.datetime(d.year, d.month, d.day, h)
                temp, cloud, rad = weather[t]
                X.append(features(t, temp, cloud, rad))
                y.append(price[t])
        beta, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)

        # Predict the test day
        pred = {}
        for h in range(24):
            t = dt.datetime(test_day.year, test_day.month, test_day.day, h)
            temp, cloud, rad = weather[t]
            pred[h] = float(np.dot(features(t, temp, cloud, rad), beta))

        actual = prices_of(test_day)
        model_hours = cheapest(pred, N_CHEAP)
        actual_hours = cheapest(actual, N_CHEAP)
        persist_hours = cheapest(prices_of(days[i - 1]), N_CHEAP)

        # climatology: cheapest hours by mean price over training days
        mean_by_hour = {h: np.mean([prices_of(d)[h] for d in train_days]) for h in range(24)}
        clim_hours = cheapest(mean_by_hour, N_CHEAP)

        def cost(hours):
            return float(np.mean([actual[h] for h in hours]))

        def hit(hours):
            return len(hours & actual_hours) / N_CHEAP

        records.append({
            "date": test_day.isoformat(),
            "hit": {"model": hit(model_hours), "persistence": hit(persist_hours),
                    "climatology": hit(clim_hours)},
            "cost": {"perfect": cost(actual_hours), "model": cost(model_hours),
                     "persistence": cost(persist_hours), "climatology": cost(clim_hours),
                     "all_day": float(np.mean(list(actual.values())))},
        })

    # Aggregate
    def avg(path, key):
        return round(float(np.mean([r[path][key] for r in records])), 3)

    summary = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "data_source": _data_source(),
        "n_cheap_hours": N_CHEAP,
        "test_days": len(records),
        "hit_rate": {k: avg("hit", k) for k in ("model", "persistence", "climatology")},
        "avg_cost_ct_per_kwh": {k: avg("cost", k) for k in
                                ("perfect", "model", "climatology", "persistence", "all_day")},
    }
    summary["avg_regret_ct_per_kwh"] = {
        k: round(summary["avg_cost_ct_per_kwh"][k] - summary["avg_cost_ct_per_kwh"]["perfect"], 3)
        for k in ("model", "climatology", "persistence", "all_day")
    }
    summary["per_day"] = records

    with open(HERE / "forecast_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    plot(summary)
    report(summary)


def _data_source():
    p = HERE / "wc_meta.json"
    return json.load(open(p)).get("data_source", "unknown") if p.exists() else "unknown"


def plot(s):
    order = ["perfect", "model", "climatology", "persistence", "all_day"]
    labels = ["Perfect\nforesight", "Model", "Climatology", "Persistence", "Charge\nanytime"]
    vals = [s["avg_cost_ct_per_kwh"][k] for k in order]
    colors = ["#4c9f70", "#c1436d", "#e0a458", "#e0a458", "#888888"]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, vals, color=colors)
    ax.axhline(s["avg_cost_ct_per_kwh"]["perfect"], color="#4c9f70", ls="--", lw=.8)
    ax.set_ylabel(f"Avg price paid for {s['n_cheap_hours']} charging hours (ct/kWh)")
    ax.set_title("Cheapest-hours forecast vs baselines (lower is better)")
    ax.bar_label(bars, fmt="%.1f")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(HERE / "forecast_backtest.png", dpi=120)


def report(s):
    print(f"Backtest over {s['test_days']} days | data: {s['data_source']}")
    print(f"Predicting the {s['n_cheap_hours']} cheapest hours of each day.\n")
    print(f"{'strategy':<14}{'hit-rate':>10}{'avg cost':>11}{'regret':>9}")
    for k in ("model", "climatology", "persistence"):
        hr = s["hit_rate"][k]
        print(f"{k:<14}{hr:>10.2f}{s['avg_cost_ct_per_kwh'][k]:>11.2f}"
              f"{s['avg_regret_ct_per_kwh'][k]:>9.2f}")
    print(f"{'perfect':<14}{1.0:>10.2f}{s['avg_cost_ct_per_kwh']['perfect']:>11.2f}{0.0:>9.2f}")
    print(f"{'charge anytime':<14}{'-':>10}{s['avg_cost_ct_per_kwh']['all_day']:>11.2f}"
          f"{s['avg_regret_ct_per_kwh']['all_day']:>9.2f}")
    best = max(("model", "climatology", "persistence"), key=lambda k: s["hit_rate"][k])
    print(f"\nBest hit-rate: {best}. Model regret vs perfect: "
          f"{s['avg_regret_ct_per_kwh']['model']:.2f} ct/kWh.")
    print("Wrote forecast_results.json and forecast_backtest.png")


if __name__ == "__main__":
    main()
