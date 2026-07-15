"""
Milestone 2: the tariff cost model — turn prices into an insight.

Question it answers:
  For one household over one day, what does electricity cost on a
  FLAT tariff vs a DYNAMIC (spot-linked) tariff, and how much do you
  save by shifting a flexible load (an EV charge) into the cheapest hours?

Honest modelling note
---------------------
A dynamic-tariff bill is NOT just the wholesale price. It is:

    price_per_kwh(hour) = wholesale_spot(hour) + FIXED_ADDER

FIXED_ADDER (grid fees + levies + tax + supplier margin) is the same every
hour, so shifting load only moves the *wholesale* part. That is why real
savings are meaningful but modest — not 10x. This model keeps that honest.

Input
-----
Reads prices.csv produced by fetch_prices.py (column: ct_per_kwh = wholesale).
If that file is missing, it generates a realistic synthetic day so the
script always runs (useful offline / for testing).

Outputs
-------
  results.json          machine-readable summary (for the future demo page)
  cost_comparison.png   bar chart of the three scenarios

Run:  python cost_model.py
"""

import csv
import datetime as dt
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_utils import add_caption

HERE = Path(__file__).parent

# ---- Assumptions you can change (all in ct/kWh unless noted) ----------------
FLAT_RATE_CT = 35.0     # typical German flat all-in tariff
FIXED_ADDER_CT = 20.0   # grid fees + levies + tax + margin, added on top of wholesale
EV_KWH = 11.0           # energy for one EV charge
EV_CHARGE_HOURS = 3     # spread over this many hours (cheapest ones when shifting)

# Baseline household load without the EV: 24 hourly values in kWh.
# Rough shape: low overnight, morning bump, evening peak. Sums to ~9 kWh/day.
BASE_LOAD = [
    0.20, 0.15, 0.15, 0.15, 0.15, 0.25,   # 00-05 night
    0.40, 0.55, 0.45, 0.35, 0.30, 0.35,   # 06-11 morning
    0.40, 0.35, 0.30, 0.30, 0.40, 0.60,   # 12-17 afternoon
    0.80, 0.75, 0.60, 0.45, 0.30, 0.20,   # 18-23 evening peak
]

# When the EV would charge WITHOUT smart control: plug in after work, evening peak.
NAIVE_EV_HOURS = [18, 19, 20]  # exactly EV_CHARGE_HOURS of them
# -----------------------------------------------------------------------------


def load_wholesale():
    """Return (labels, values): 24 hour labels ("HH:MM") and wholesale ct/kWh,
    ordered by clock hour 00:00..23:00.

    Reads prices.csv (from fetch_prices.py); synthesizes a day if it's missing.

    Ordering matters: the fetch starts at whatever hour it ran (e.g. 18:00), so
    the CSV rows are NOT hour 0..23. BASE_LOAD and NAIVE_EV_HOURS below are
    indexed by clock hour, so we must re-key each row by its actual hour. Using
    raw row order would rotate the household load against the price curve
    (an earlier version of this script had exactly that bug: the "evening" EV
    charge landed on midday prices and smart-shifting appeared to save €0).
    """
    csv_path = HERE / "prices.csv"
    if csv_path.exists():
        by_hour = {}
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                t = dt.datetime.fromisoformat(row["datetime"])
                if t.hour not in by_hour:          # first occurrence of each clock hour
                    by_hour[t.hour] = float(row["ct_per_kwh"])
        if len(by_hour) == 24:
            labels = [f"{h:02d}:00" for h in range(24)]
            return labels, [by_hour[h] for h in range(24)]
        # fall through to synthetic if we don't have all 24 clock hours

    # Synthetic fallback: a plausible day-ahead shape (ct/kWh wholesale),
    # cheap and near-zero midday (solar), expensive in the evening peak.
    labels, synth = [], []
    for h in range(24):
        # base sinusoid: evening peak around 19:00, midday dip around 13:00
        peak = 9.0 * math.sin((h - 7) / 24 * 2 * math.pi) + 8.0
        if 11 <= h <= 14:
            peak -= 6.0  # solar pushes midday down, can go negative
        labels.append(f"{h:02d}:00")
        synth.append(round(peak, 2))
    return labels, synth


def dynamic_prices(wholesale):
    """Retail dynamic price per hour = wholesale + fixed adder."""
    return [w + FIXED_ADDER_CT for w in wholesale]


def cost(load, price_per_hour):
    """Cost in EUR for an hourly load (kWh) at hourly prices (ct/kWh)."""
    ct = sum(l * p for l, p in zip(load, price_per_hour))
    return ct / 100.0  # ct -> EUR


def cheapest_hours(wholesale, n):
    """Indices of the n cheapest hours."""
    return sorted(range(24), key=lambda h: wholesale[h])[:n]


def add_ev(load, hours):
    """Return a copy of load with the EV charge spread evenly over `hours`."""
    out = list(load)
    per_hour = EV_KWH / len(hours)
    for h in hours:
        out[h] += per_hour
    return out


def main():
    labels, wholesale = load_wholesale()
    dyn = dynamic_prices(wholesale)

    # Three scenarios, all including the EV charge:
    load_naive = add_ev(BASE_LOAD, NAIVE_EV_HOURS)                 # EV in evening peak
    smart_hours = cheapest_hours(wholesale, EV_CHARGE_HOURS)
    load_smart = add_ev(BASE_LOAD, smart_hours)                   # EV in cheapest hours

    flat_naive = cost(load_naive, [FLAT_RATE_CT] * 24)            # flat tariff, no benefit from timing
    dyn_naive = cost(load_naive, dyn)                            # dynamic, but dumb charging
    dyn_smart = cost(load_smart, dyn)                            # dynamic + shifted charging

    total_kwh = sum(load_naive)
    savings_vs_flat = flat_naive - dyn_smart
    savings_from_shift = dyn_naive - dyn_smart

    summary = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "assumptions": {
            "flat_rate_ct_per_kwh": FLAT_RATE_CT,
            "fixed_adder_ct_per_kwh": FIXED_ADDER_CT,
            "ev_kwh": EV_KWH,
            "ev_charge_hours": EV_CHARGE_HOURS,
            "total_daily_kwh": round(total_kwh, 2),
        },
        "hour_labels": labels,
        "wholesale_ct_per_kwh": [round(w, 2) for w in wholesale],
        "dynamic_price_ct_per_kwh": [round(d, 2) for d in dyn],
        "cheapest_hours": smart_hours,
        "naive_ev_hours": NAIVE_EV_HOURS,
        "cost_eur": {
            "flat_tariff": round(flat_naive, 2),
            "dynamic_naive_charging": round(dyn_naive, 2),
            "dynamic_smart_charging": round(dyn_smart, 2),
        },
        "savings_eur": {
            "dynamic_smart_vs_flat_per_day": round(savings_vs_flat, 2),
            "dynamic_smart_vs_flat_per_year": round(savings_vs_flat * 365, 0),
            "from_shifting_ev_per_day": round(savings_from_shift, 2),
        },
    }

    with open(HERE / "results.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Bar chart
    labels = ["Flat\ntariff", "Dynamic\n(dumb charging)", "Dynamic\n(smart charging)"]
    values = [flat_naive, dyn_naive, dyn_smart]
    colors = ["#888888", "#e0a458", "#4c9f70"]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel("Cost for one day (EUR)")
    ax.set_title(f"One household, {total_kwh:.1f} kWh incl. {EV_KWH:.0f} kWh EV charge")
    ax.bar_label(bars, fmt="€%.2f")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    add_caption(fig, "Modelled cost for one household's electricity on one day "
                f"({total_kwh:.1f} kWh total, including an {EV_KWH:.0f} kWh EV "
                "charge), not a real bill. \"Flat tariff\" = one fixed ct/kWh "
                "price all day. \"Dynamic tariff\" tracks the day-ahead "
                "wholesale price hour by hour. \"Dumb charging\" plugs the EV "
                "in at a fixed time regardless of price; \"smart charging\" "
                "shifts that charge into the cheapest hours of the day.")
    fig.subplots_adjust(bottom=0.26)
    fig.savefig(HERE / "cost_comparison.png", dpi=120)

    # Console readout
    print(f"Daily consumption: {total_kwh:.1f} kWh (incl. {EV_KWH:.0f} kWh EV)")
    print(f"Cheapest hours today: {smart_hours}  (EV charged here when smart)")
    print("-" * 48)
    print(f"Flat tariff:               €{flat_naive:5.2f}")
    print(f"Dynamic, dumb charging:    €{dyn_naive:5.2f}")
    print(f"Dynamic, smart charging:   €{dyn_smart:5.2f}")
    print("-" * 48)
    print(f"Saving vs flat (smart):    €{savings_vs_flat:5.2f}/day  ~€{savings_vs_flat*365:.0f}/year")
    print(f"Saving just from shifting: €{savings_from_shift:5.2f}/day")
    print("\nSaved results.json and cost_comparison.png")


if __name__ == "__main__":
    main()
