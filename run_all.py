"""
Run the whole pipeline in dependency order, so there is exactly one command
to remember:

    python run_all.py                 # full run: fetch fresh data, then analyse
    python run_all.py --skip-fetch    # no network: re-analyse the existing CSVs

Order and dependencies
----------------------
1. fetch_prices.py           network   -> prices.csv
2. cost_model.py             offline   <- prices.csv          -> results.json
3. wc_fetch_data.py          network   -> wc_prices.csv, wc_weather.csv
4. entsoe_fetch.py           network*  -> wc_load.csv         (*needs ENTSOE_TOKEN)
5. wc_analysis.py            offline   <- wc_prices/weather   -> wc_results.json
6. forecast_cheap_hours.py   offline   <- wc_prices/weather   -> forecast_results.json
7. forecast_value.py         offline   <- forecast_results    -> forecast_value.json
8. event_study.py            offline   <- wc_prices/weather   -> event_study_results.json
9. wc_load_effect.py         offline   <- wc_load.csv         -> wc_load_results.json
10. wc_permutation.py        offline   <- wc_load.csv         -> wc_permutation_results.json

Safety logic worth knowing
--------------------------
The fetchers fall back to SYNTHETIC data when the network or token fails, and
that would overwrite real CSVs with test data. So this runner (a) checks the
data_source after each fetch and warns loudly if it went synthetic, and
(b) skips entsoe_fetch.py entirely when no ENTSOE_TOKEN is set but a real
wc_load.csv already exists, rather than clobbering it.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def ensure_project_python():
    """Restart under the project's .venv if we were started with another python.

    Catches the classic failure: running this file with the system python
    (an editor's Run button, or a bare python3), which doesn't have the
    dependencies installed. If we're not inside any virtualenv but the
    project's .venv exists, re-exec with it; otherwise fail with a hint
    instead of a raw ModuleNotFoundError.
    """
    if sys.prefix != sys.base_prefix:
        return  # already inside a virtualenv
    for cand in (HERE / ".venv/bin/python3", HERE / ".venv/bin/python",
                 HERE / ".venv/Scripts/python.exe"):
        if cand.exists():
            print(f"(not in the project venv; switching to {cand})")
            try:
                os.execv(str(cand), [str(cand), str(Path(__file__).resolve()),
                                     *sys.argv[1:]])
            except OSError:
                break  # unusable venv (e.g. built on another OS); fall through
    try:
        import requests, numpy, matplotlib  # noqa: F401
    except ImportError as e:
        sys.exit(f"Missing dependency: {e.name}. Run 'bash setup.sh' once to "
                 f"create the .venv, then 'python run_all.py' again (it will "
                 f"find the venv by itself).")


def run(script):
    line = f"=== python {script} "
    print("\n" + line + "=" * max(0, 62 - len(line)))
    r = subprocess.run([sys.executable, str(HERE / script)])
    if r.returncode != 0:
        sys.exit(f"\n{script} failed (exit {r.returncode}); stopping here.")


def meta_source(meta_file):
    p = HERE / meta_file
    if not p.exists():
        return "unknown"
    return json.load(open(p)).get("data_source", "unknown")


def warn_if_synthetic(meta_file, what):
    src = str(meta_source(meta_file))
    if src.startswith("synthetic"):
        print(f"\n!! WARNING: {what} came back SYNTHETIC ({src}).")
        print("!! The fetch failed and the fallback overwrote the CSV with test data.")
        print("!! Fix the network/token and re-run before trusting any results.")


def have_entsoe_token():
    if os.environ.get("ENTSOE_TOKEN"):
        return True
    env = HERE / ".env"
    if env.exists():
        for ln in env.read_text().splitlines():
            if ln.strip().startswith("ENTSOE_TOKEN=") and ln.split("=", 1)[1].strip():
                return True
    return False


def main():
    ensure_project_python()
    ap = argparse.ArgumentParser(description="Run the full pipeline in order.")
    ap.add_argument("--skip-fetch", action="store_true",
                    help="no network: run all analyses on the existing CSVs")
    args = ap.parse_args()

    if not args.skip_fetch:
        run("fetch_prices.py")
        run("wc_fetch_data.py")
        warn_if_synthetic("wc_meta.json", "the price/weather window")
        if have_entsoe_token():
            run("entsoe_fetch.py")
            warn_if_synthetic("wc_load_meta.json", "the ENTSO-E load data")
        elif (HERE / "wc_load.csv").exists():
            print("\nNo ENTSOE_TOKEN set: keeping the existing wc_load.csv "
                  "(running the fetch without a token would replace it with "
                  "synthetic data).")
        else:
            print("\nNo ENTSOE_TOKEN set and no wc_load.csv: the load-based "
                  "studies (wc_load_effect, wc_permutation) will be skipped.")

    run("cost_model.py")
    run("wc_analysis.py")
    run("forecast_cheap_hours.py")
    run("forecast_value.py")
    run("event_study.py")

    if (HERE / "wc_load.csv").exists():
        run("wc_load_effect.py")
        run("wc_permutation.py")
    else:
        print("\n(wc_load.csv missing: skipped wc_load_effect.py and "
              "wc_permutation.py. Set ENTSOE_TOKEN and re-run to include them.)")

    print("\nDone. Preview the pages with:  python -m http.server 8000")


if __name__ == "__main__":
    main()
