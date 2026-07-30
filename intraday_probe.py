"""
Diagnostic v2. Two questions the first probe left open:
  1. Is the "Auction.Type=A02" result real intraday, or just day-ahead echoed
     back because the parameter was ignored? -> compare the first prices.
  2. Imbalance (A85 / 17.1.G) returned nothing for a recent window across every
     German domain. Is that publication lag or the wrong imbalance area?
     -> retry over an OLDER window, and print the reason text in full.

Run:  python intraday_probe.py
Paste the output back. Reads only; writes nothing.
"""

import datetime as dt
import os
import re
from pathlib import Path

import requests

HERE = Path(__file__).parent
BASE = "https://web-api.tp.entsoe.eu/api"
DE_LU = "10Y1001A1001A82H"
TSOS = {"Amprion": "10YDE-RWENET---I", "50Hertz": "10YDE-VE-------2",
        "TenneT": "10YDE-EON------1", "TransnetBW": "10YDE-ENBW-----N"}


def token():
    p = HERE / ".env"
    if p.exists():
        for ln in p.read_text().splitlines():
            if ln.strip().startswith("ENTSOE_TOKEN="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("ENTSOE_TOKEN")


def get(params):
    p = dict(params); p["securityToken"] = token()
    r = requests.get(BASE, params=p, timeout=60)
    return r


def first_prices(body, n=5):
    return [float(x) for x in re.findall(r"<price\.amount>([^<]+)</price\.amount>", body)[:n]]


def summarize(label, r):
    body = r.text
    root = re.search(r"<(\w+_MarketDocument)", body)
    reason = re.search(r"<text>([^<]+)</text>", body)
    prices = len(re.findall(r"<price\.amount>", body))
    res = sorted(set(re.findall(r"<resolution>([^<]+)</resolution>", body)))
    print(f"[{label}] HTTP {r.status_code} | doc={root.group(1) if root else '?'} "
          f"| pricePts={prices} | res={res or '-'}"
          + (f" | reason={reason.group(1)[:140]}" if reason else ""))
    return body


def window(days_ago, span=1):
    end = dt.date.today() - dt.timedelta(days=days_ago)
    start = end - dt.timedelta(days=span)
    return (start.strftime("%Y%m%d") + "0000",
            (end + dt.timedelta(days=1)).strftime("%Y%m%d") + "0000", start, end)


def main():
    if not token():
        raise SystemExit("No ENTSOE_TOKEN found.")

    # --- Q1: is A02 real intraday, or day-ahead echoed? ---
    ps, pe, s, e = window(3)
    print(f"Q1: day-ahead vs Auction.Type=A02, window {s}..{e}")
    da = summarize("  DA A44", get({"documentType": "A44", "in_Domain": DE_LU,
                   "out_Domain": DE_LU, "periodStart": ps, "periodEnd": pe}))
    a02 = summarize("  A44+Auction.Type=A02", get({"documentType": "A44",
                    "auction.Type": "A02", "in_Domain": DE_LU, "out_Domain": DE_LU,
                    "periodStart": ps, "periodEnd": pe}))
    print(f"  first DA prices : {first_prices(da)}")
    print(f"  first A02 prices: {first_prices(a02)}")
    print("  => identical means A02 is just day-ahead (no intraday), different means real.\n")

    # --- Q2: imbalance lag vs domain, over progressively older windows ---
    print("Q2: imbalance A85 over older windows (lag check)")
    for days_ago in (10, 30, 60):
        ps, pe, s, e = window(days_ago, span=1)
        print(f"  window {s}..{e}:")
        summarize("    DE-LU", get({"documentType": "A85", "controlArea_Domain": DE_LU,
                  "periodStart": ps, "periodEnd": pe}))
        for name, dom in TSOS.items():
            summarize(f"    {name}", get({"documentType": "A85", "controlArea_Domain": dom,
                      "periodStart": ps, "periodEnd": pe}))


if __name__ == "__main__":
    main()
