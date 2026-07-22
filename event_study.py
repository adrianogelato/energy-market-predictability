"""
Milestone 9: a generic event study, so the method is not one-off.

The World Cup analysis is really one instance of a general question: does a set
of special days behave differently from weather-comparable normal days? This
module makes that reusable for any event set, and demonstrates it on cases that
SHOULD show an effect, as a contrast to the World Cup null. If the method can
clearly detect the weekend effect, then its failure to find a World Cup effect
is a real result, not a broken tool.

What it does
------------
For a set of event days and a comparison pool of normal days, it compares a
signal (day-ahead price by default) during chosen hours on event days against
the weather-nearest normal days, reports the mean effect and t, and runs a
permutation test for an honest p-value.

Two demonstrations run by default:
  weekends  : Saturdays and Sundays vs weather-comparable weekdays (high power,
              a large real effect is expected)
  holidays  : German public holidays (events_holidays.csv) vs comparable
              weekdays

Signal note
-----------
Default signal is the day-ahead price, so this runs without an ENTSO-E token.
Weekends and holidays lower daytime demand and therefore daytime price, so the
effect shows up cleanly in price.

Data note
---------
The studies run on the full-year files (year_prices.csv / year_weather.csv,
milestone 10) when they exist: a year-wide pool gives the holiday test real
n instead of the single summer holiday, and the season guard in matching.py
keeps controls calendar neighbours. Falls back to the World Cup window files
(wc_prices.csv / wc_weather.csv) so a clone that only ran the short fetch
still works.

Inputs : year_prices.csv + year_weather.csv (fallback wc_prices.csv +
         wc_weather.csv), events_holidays.csv
Outputs: event_study_results.json
Run    : python event_study.py
"""

import csv
import datetime as dt
import json
import math
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from matching import load_weather_daily, load_holidays, Matcher, K_CONTROLS

HERE = Path(__file__).parent
DAY_HOURS = list(range(8, 20))     # 08:00-19:59, where work/rest demand differences show
N_PERM = 2000
SEED = 20260713


def data_files():
    """Year files when present (wider pool, real holiday n), else the WC window."""
    if (HERE / "year_prices.csv").exists() and (HERE / "year_weather.csv").exists():
        return HERE / "year_prices.csv", HERE / "year_weather.csv"
    return HERE / "wc_prices.csv", HERE / "wc_weather.csv"


def load_price(path):
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            out[dt.datetime.fromisoformat(r["datetime"])] = float(r["ct_per_kwh"])
    return out


def day_signal(price, date, hours):
    vals = [price[dt.datetime(date.year, date.month, date.day, h)]
            for h in hours
            if dt.datetime(date.year, date.month, date.day, h) in price]
    return mean(vals) if vals else None


def effect(event_days, pool_days, price, matcher, hours):
    """Mean signal delta (event minus weather-nearest pool days) and its t.

    Uses match_day_type=False: comparing weekends (or holidays) against a
    weekday pool is the point of these studies, so the day-type filter that
    protects the World Cup analyses must be off here.
    """
    deltas = []
    for d in event_days:
        se = day_signal(price, d, hours)
        if se is None:
            continue
        ctrls = matcher.controls(d, pool_days, match_day_type=False)
        cs = [day_signal(price, c, hours) for c in ctrls]
        cs = [x for x in cs if x is not None]
        if not cs:
            continue
        deltas.append(se - mean(cs))
    n = len(deltas)
    if n == 0:
        return None
    md = mean(deltas)
    # Sample SD (n-1): n observed per-day deltas, not a population.
    sd = (stdev(deltas) if n > 1 else 0.0) or 0.0
    t = (md / (sd / math.sqrt(n))) if sd > 0 and n > 1 else float("nan")
    # Minimum detectable effect (80% power, two-sided alpha=0.05).
    mde = (2.8 * sd / math.sqrt(n)) if (n > 1 and sd > 0) else None
    return {"n": n, "mean_delta_ct": round(md, 2), "std": round(sd, 2),
            "t_stat": None if math.isnan(t) else round(t, 2),
            "mde_ct_80pct_power": None if mde is None else round(mde, 2)}


def permutation_p(event_days, pool_days, price, matcher, hours, real_t, rng):
    """Placebo: draw fake events from the pool, compare their t to the real one."""
    if real_t is None:
        return None
    k = len(event_days)
    pool = list(pool_days)
    null = []
    for _ in range(N_PERM):
        idx = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
        fake = [pool[i] for i in idx]
        rest = [d for d in pool if d not in set(fake)]
        e = effect(fake, rest, price, matcher, hours)
        null.append(abs(e["t_stat"]) if e and e["t_stat"] is not None else 0.0)
    null = np.array(null)
    # +1 correction: the smallest reportable p is 1/(N_PERM+1), never 0.
    return float((np.sum(null >= abs(real_t)) + 1) / (N_PERM + 1))


def run_study(name, event_days, pool_days, price, matcher, hours, rng):
    e = effect(event_days, pool_days, price, matcher, hours)
    if e is None:
        return {"name": name, "n": 0, "note": "no event days with data in window"}
    p = permutation_p(event_days, pool_days, price, matcher, hours, e["t_stat"], rng)
    out = {"name": name, **e, "permutation_p": None if p is None else round(p, 4)}
    # A permutation p can never be exactly 0; the floor is 1/(N_PERM+1). Ship a
    # display string so no report ever claims "p = 0.0".
    if p is not None:
        floor = 1 / (N_PERM + 1)
        out["permutation_p_str"] = (f"< {floor:.4f}" if p <= floor else f"{p:.4f}")
    return out


def main():
    price_file, weather_file = data_files()
    price = load_price(price_file)
    feats = load_weather_daily(weather_file)
    days = sorted(feats)
    price_days = {t.date() for t in price}
    eligible = [d for d in days if d in price_days]

    matcher = Matcher(feats)
    rng = np.random.default_rng(SEED)

    # "weekday" pool via day_type, which excludes public holidays: a holiday
    # Monday behaves like a Sunday and must not serve as a weekday control
    # (Whit Monday falls inside this data window).
    weekdays = [d for d in eligible if feats[d]["day_type"] == "weekday"]
    weekends = [d for d in eligible if d.weekday() >= 5]
    holidays = sorted(load_holidays() & set(eligible))

    studies = [
        run_study("weekend_vs_weekday", weekends, weekdays, price, matcher, DAY_HOURS, rng),
        run_study("holiday_vs_weekday", holidays, weekdays, price, matcher, DAY_HOURS, rng),
    ]

    results = {
        "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
        "signal": "day-ahead price (ct/kWh)",
        "hours": f"{DAY_HOURS[0]:02d}:00-{DAY_HOURS[-1]:02d}:59",
        "data_files": [price_file.name, weather_file.name],
        "window": {"start": min(eligible).isoformat(),
                   "end": max(eligible).isoformat()},
        "n_permutations": N_PERM,
        "matching": {**matcher.describe(),
                     "note": ("day-type filter disabled for these studies: "
                              "weekend/holiday days are deliberately matched "
                              "against weekday controls; holidays are excluded "
                              "from the weekday pool")},
        "studies": studies,
    }
    with open(HERE / "event_study_results.json", "w") as f:
        json.dump(results, f, indent=2)
    report(results)


def report(res):
    print(f"Event study | signal: {res['signal']} | hours {res['hours']}\n")
    print(f"{'event set':<22}{'n':>4}{'effect ct/kWh':>15}{'t':>8}{'perm p':>10}")
    for s in res["studies"]:
        if s.get("n", 0) == 0:
            print(f"{s['name']:<22}{0:>4}   {s.get('note','')}")
            continue
        t = "n/a" if s["t_stat"] is None else f"{s['t_stat']:.2f}"
        pp = s.get("permutation_p_str") or "n/a"
        tail = "  (n too small; widen the fetch window)" if s["t_stat"] is None else ""
        print(f"{s['name']:<22}{s['n']:>4}{s['mean_delta_ct']:>+15.2f}{t:>8}{pp:>10}{tail}")
    print("\nInterpretation: a large, significant weekend effect confirms the method "
          "detects real events, which is what makes the World Cup null trustworthy.")
    print("Wrote event_study_results.json")


if __name__ == "__main__":
    main()
