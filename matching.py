"""
The comparable-days matching engine, shared by wc_analysis.py,
wc_load_effect.py (and through it wc_permutation.py) and event_study.py.

This file IS the definition of "weather-comparable day", in one inspectable
place. The parameters below are design decisions for the German bidding zone,
not generic defaults; the reasoning for each lives in the README section
"What a weather-comparable day means".

What is matched on
------------------
Continuous features, z-scored over all days, Euclidean distance:
  temp_mean   daily mean temperature (demand level)
  temp_max    daily maximum temperature (demand shape: afternoon peaks are
              nonlinear in temperature, a hot afternoon is not a mild day)
  solar proxy daily mean shortwave radiation when the weather file carries it,
              otherwise daily mean cloud cover. Radiation is the actual driver
              of PV output; cloud is a lossy stand-in kept for older files.
  wind_mean   daily mean wind speed, when the weather file carries it. Wind
              generation moves German day-ahead prices at least as much as
              solar; two days with equal temperature and cloud but different
              wind are not price-comparable.

Categorical filter (match_day_type=True):
  day types are weekday / saturday / sunlike, where "sunlike" is Sunday OR a
  public holiday (events_holidays.csv). Saturdays and Sundays behave
  differently in load, and a holiday behaves like a Sunday, so a holiday must
  never serve as a weekday control. (Whit Monday sat in this project's window
  and would otherwise be offered as a weekday control while carrying a
  Sunday-sized ~6 ct/kWh daytime price discount.)
  Fallbacks when the same-type pool is too small: saturday and sunlike merge
  into a weekend-like pool; after that, the full pool.

Season guard (SEASON_GAP_MAX_DAYS):
  caps |calendar distance| between a day and its controls, the direct guard
  against the seasonal-drift confound documented in ROADMAP.md. On (21 days)
  since the event studies moved to the full-year files; it degrades
  gracefully: when fewer than k pool days fall inside the gap, the full pool
  is used, so a narrow one-sided window is never starved.

Every study exposes the chosen pairings (controls(..., detailed=True)) so the
matching can be eyeballed instead of trusted.
"""

import csv
import datetime as dt
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

HERE = Path(__file__).parent
K_CONTROLS = 5
SEASON_GAP_MAX_DAYS = 21   # controls must be calendar neighbours (see docstring)


def load_holidays(path=None):
    path = path or HERE / "events_holidays.csv"
    days = set()
    if not Path(path).exists():
        return days
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                days.add(dt.date.fromisoformat(r["date"].strip()))
            except (ValueError, KeyError):
                continue
    return days


def day_type(d, holidays):
    """weekday / saturday / sunlike (Sunday or public holiday)."""
    if d in holidays or d.weekday() == 6:
        return "sunlike"
    if d.weekday() == 5:
        return "saturday"
    return "weekday"


def load_weather_daily(path=None, holidays=None):
    """Return {date: feature dict}. Optional columns (wind_kmh,
    radiation_wm2) are used when present, so files fetched before those
    columns existed keep working with the reduced feature set."""
    path = path or HERE / "wc_weather.csv"
    holidays = load_holidays() if holidays is None else holidays
    acc = defaultdict(lambda: defaultdict(list))
    with open(path) as f:
        for r in csv.DictReader(f):
            d = dt.datetime.fromisoformat(r["datetime"]).date()
            acc[d]["temp"].append(float(r["temp_c"]))
            acc[d]["cloud"].append(float(r["cloud_pct"]))
            if r.get("wind_kmh"):
                acc[d]["wind"].append(float(r["wind_kmh"]))
            if r.get("radiation_wm2"):
                acc[d]["rad"].append(float(r["radiation_wm2"]))
    feats = {}
    for d, a in acc.items():
        f = {
            "temp_mean": mean(a["temp"]),
            "temp_max": max(a["temp"]),
            "cloud_mean": mean(a["cloud"]),
            "day_type": day_type(d, holidays),
        }
        if a["wind"]:
            f["wind_mean"] = mean(a["wind"])
        if a["rad"]:
            f["rad_mean"] = mean(a["rad"])
        feats[d] = f
    return feats


class Matcher:
    """K-nearest weather-comparable days over z-scored features."""

    def __init__(self, feats, k=K_CONTROLS, season_gap_max_days=SEASON_GAP_MAX_DAYS):
        self.feats = feats
        self.k = k
        self.gap = season_gap_max_days
        days = list(feats)

        def universal(col):
            return all(col in feats[d] for d in days)

        cols = ["temp_mean", "temp_max"]
        cols.append("rad_mean" if universal("rad_mean") else "cloud_mean")
        if universal("wind_mean"):
            cols.append("wind_mean")
        self.cols = cols

        self.stats = {}
        for c in cols:
            vals = [feats[d][c] for d in days]
            self.stats[c] = (mean(vals), pstdev(vals) or 1.0)
        # precompute z-vectors once; the permutation test calls distance a lot
        self._vec = {
            d: tuple((feats[d][c] - m) / s for c, (m, s) in
                     ((c, self.stats[c]) for c in cols))
            for d in days
        }

    def distance(self, a, b):
        return math.dist(self._vec[a], self._vec[b])

    def controls(self, target, pool, match_day_type=True, detailed=False):
        """The k most comparable days for `target` out of `pool`.

        match_day_type=False deliberately skips the day-type filter; the
        weekend event study needs weekday controls for weekend days.
        """
        pool = [d for d in pool if d != target and d in self._vec]
        if self.gap is not None:
            near = [d for d in pool if abs((d - target).days) <= self.gap]
            if len(near) >= self.k:
                pool = near
        if match_day_type:
            tt = self.feats[target]["day_type"]
            same = [d for d in pool if self.feats[d]["day_type"] == tt]
            if len(same) >= self.k:
                pool = same
            elif tt in ("saturday", "sunlike"):
                weekend_like = [d for d in pool
                                if self.feats[d]["day_type"] in ("saturday", "sunlike")]
                if len(weekend_like) >= self.k:
                    pool = weekend_like
        ranked = sorted(pool, key=lambda d: self.distance(target, d))[:self.k]
        if not detailed:
            return ranked
        return [
            {
                "date": d.isoformat(),
                "day_type": self.feats[d]["day_type"],
                "distance": round(self.distance(target, d), 2),
                **{c: round(self.feats[d][c], 1) for c in self.cols},
            }
            for d in ranked
        ]

    def describe(self):
        """Metadata block for result JSONs, so every output states what
        'comparable' meant when it was produced."""
        return {
            "features": self.cols,
            "k_controls": self.k,
            "day_type_classes": ["weekday", "saturday", "sunlike (Sun or public holiday)"],
            "season_gap_max_days": self.gap,
            "distance": "euclidean over z-scored features",
        }
