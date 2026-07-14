"""
Milestone 1: pull real day-ahead electricity prices and look at them.

Data source: aWATTar (German dynamic tariff). Free, no API key.
The aWATTar hourly price = EPEX SPOT day-ahead wholesale price.
Endpoint: https://api.awattar.de/v1/marketdata

What this script does:
  1. Fetches the available hourly market prices.
  2. Converts EUR/MWh -> ct/kWh (the unit your bill uses).
  3. Saves them to prices.csv.
  4. Plots the hourly curve to prices.png so you SEE the volatility.

Run:  python fetch_prices.py
"""

import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import matplotlib
matplotlib.use("Agg")  # no display needed, just save a file
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
API = "https://api.awattar.de/v1/marketdata"


def fetch():
    """Return the raw list of hourly price entries from aWATTar."""
    resp = requests.get(API, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]  # list of {start_timestamp, end_timestamp, marketprice, unit}


def to_rows(data):
    """Turn raw entries into clean (datetime, eur_per_mwh, ct_per_kwh) rows."""
    rows = []
    berlin = ZoneInfo("Europe/Berlin")
    for entry in data:
        # Timestamps are epoch milliseconds. Convert explicitly to German local
        # time: naive fromtimestamp() would use the *machine's* zone, which is
        # UTC on the GitHub Actions runner and would shift every hour label.
        start = dt.datetime.fromtimestamp(entry["start_timestamp"] / 1000,
                                          tz=berlin).replace(tzinfo=None)
        eur_per_mwh = entry["marketprice"]          # aWATTar gives EUR/MWh
        ct_per_kwh = eur_per_mwh / 10.0             # /1000 -> EUR/kWh, *100 -> ct/kWh
        rows.append((start, eur_per_mwh, ct_per_kwh))
    return rows


def save_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "eur_per_mwh", "ct_per_kwh"])
        for start, eur, ct in rows:
            w.writerow([start.isoformat(), f"{eur:.2f}", f"{ct:.3f}"])


def plot(rows, path):
    times = [r[0] for r in rows]
    ct = [r[2] for r in rows]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(times, ct, marker="o", ms=3, lw=1.2)
    ax.axhline(0, color="red", lw=0.8, ls="--")  # negative-price line
    ax.set_title("Day-ahead electricity price (aWATTar / EPEX SPOT)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (ct/kWh, wholesale only)")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)


def main():
    data = fetch()
    rows = to_rows(data)

    save_csv(rows, HERE / "prices.csv")
    plot(rows, HERE / "prices.png")

    prices = [r[2] for r in rows]
    print(f"Fetched {len(rows)} hourly prices")
    print(f"  from {rows[0][0]}  to {rows[-1][0]}")
    print(f"  cheapest: {min(prices):.2f} ct/kWh")
    print(f"  priciest: {max(prices):.2f} ct/kWh")
    print(f"  spread:   {max(prices) - min(prices):.2f} ct/kWh")
    print("Saved prices.csv and prices.png")


if __name__ == "__main__":
    main()
