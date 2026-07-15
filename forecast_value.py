"""
Milestone 8: what is the forecast worth, in money?

M5 showed the cheapest-hours forecaster beats naive baselines on hit-rate and
cost per kWh. This turns that into euros per year for a concrete household, and
separates three different questions:

  1. What does acting on ANY smart timing save versus charging whenever?
  2. What does the MODEL add over simple heuristics (persistence, climatology)?
  3. How much is left on the table versus a perfect forecast?

Honest framing
--------------
The costs come from wholesale prices only. That is fine here, because the fixed
adders on a real bill (grid fees, levies, tax) are the same in every hour and
therefore cancel in the DIFFERENCE between strategies. So these euro figures are
the genuine savings from timing, independent of the tariff's fixed part. They
reflect the price distribution of the backtest window, not a full year of
weather, so read them as indicative.

Input : forecast_results.json (run forecast_cheap_hours.py first)
Output: forecast_value.json, forecast_value.png
Run   : python forecast_value.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_utils import add_caption

HERE = Path(__file__).parent
EV_KWH_PER_DAY = 11.0   # energy shifted into the cheap hours each day (one EV charge)
DAYS_PER_YEAR = 365


def main():
    p = HERE / "forecast_results.json"
    if not p.exists():
        raise SystemExit("forecast_results.json missing. Run forecast_cheap_hours.py first.")
    res = json.load(open(p))
    costs = res["avg_cost_ct_per_kwh"]   # perfect, model, climatology, persistence, all_day

    # ct/kWh -> EUR/year for the shifted energy
    def eur_year(ct):
        return ct * EV_KWH_PER_DAY * DAYS_PER_YEAR / 100.0

    cost_year = {k: round(eur_year(v), 2) for k, v in costs.items()}
    best_naive_name = min(("persistence", "climatology"), key=lambda k: costs[k])

    value = {
        "smart_timing_vs_anytime_eur_yr": round(cost_year["all_day"] - cost_year["model"], 2),
        "model_vs_best_naive_eur_yr": round(cost_year[best_naive_name] - cost_year["model"], 2),
        "best_naive_used": best_naive_name,
        "gap_model_to_perfect_eur_yr": round(cost_year["model"] - cost_year["perfect"], 2),
        "perfect_vs_anytime_ceiling_eur_yr": round(cost_year["all_day"] - cost_year["perfect"], 2),
    }

    out = {
        "data_source": res.get("data_source", "unknown"),
        "assumptions": {"ev_kwh_per_day": EV_KWH_PER_DAY, "days_per_year": DAYS_PER_YEAR,
                        "n_cheap_hours": res.get("n_cheap_hours"),
                        "backtest_days": res.get("test_days")},
        "caveat": (f"annualized at SUMMER rates: the backtest window is "
                   f"{res.get('test_days')} early-summer days with maximal solar "
                   f"spreads; winter spreads differ, so read the per-year figures "
                   f"as a summer-rate extrapolation, not a calendar-year estimate"),
        "annual_cost_eur": cost_year,
        "value": value,
    }
    with open(HERE / "forecast_value.json", "w") as f:
        json.dump(out, f, indent=2)
    plot(cost_year)
    report(out)


def plot(cost_year):
    order = ["all_day", "persistence", "climatology", "model", "perfect"]
    labels = ["Charge\nanytime", "Persistence", "Climatology", "Model", "Perfect\nforesight"]
    vals = [cost_year[k] for k in order]
    colors = ["#888", "#e0a458", "#e0a458", "#c1436d", "#4c9f70"]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, vals, color=colors)
    ax.set_ylabel(f"Annual cost of the shifted {EV_KWH_PER_DAY:.0f} kWh/day (EUR)")
    ax.set_title("Yearly cost of charging strategy, annualized at summer rates (lower is better)")
    ax.bar_label(bars, fmt="€%.0f")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    add_caption(fig, f"EUR = euros; each bar is one strategy's cost for "
                f"{EV_KWH_PER_DAY:.0f} kWh/day of EV charging, extrapolated to a "
                "year from a backtest over early-summer days with unusually wide "
                "solar-driven price swings — read these as a summer-rate "
                "estimate, not a calendar-year one. \"Perfect foresight\" is an "
                "oracle baseline that already knows the real prices. \"Model\" is "
                "the trained forecaster. \"Climatology\" predicts each hour's "
                "historical average price. \"Persistence\" predicts tomorrow "
                "will repeat today. \"Charge anytime\" ignores price entirely.")
    fig.subplots_adjust(bottom=0.30)
    fig.savefig(HERE / "forecast_value.png", dpi=120)


def report(o):
    src = o["data_source"]
    if str(src).startswith("synthetic"):
        print("!! WARNING: prices were SYNTHETIC. These euros are illustrative, not real.\n")
    v = o["value"]
    c = o["annual_cost_eur"]
    print(f"Household shifting {o['assumptions']['ev_kwh_per_day']:.0f} kWh/day into the "
          f"{o['assumptions']['n_cheap_hours']} cheapest hours (data: {src})\n")
    print(f"Annual cost of that energy:")
    for k in ("all_day", "persistence", "climatology", "model", "perfect"):
        print(f"  {k:<12} €{c[k]:>7.0f}")
    print()
    print(f"Smart timing vs charging anytime : €{v['smart_timing_vs_anytime_eur_yr']:>6.0f}/yr saved")
    print(f"Model over best naive ({v['best_naive_used']:<11}): €{v['model_vs_best_naive_eur_yr']:>6.0f}/yr")
    print(f"Gap from model to perfect        : €{v['gap_model_to_perfect_eur_yr']:>6.0f}/yr left on table")
    print(f"Ceiling (perfect vs anytime)     : €{v['perfect_vs_anytime_ceiling_eur_yr']:>6.0f}/yr")
    print(f"\nCaveat: {o['caveat']}")
    print("Wrote forecast_value.json and forecast_value.png")


if __name__ == "__main__":
    main()
