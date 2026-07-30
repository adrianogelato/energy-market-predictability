"""
Diagnostic: authenticate to the netztransparenz.de WebAPI and find the exact
reBAP (German uniform imbalance price) data endpoint and its CSV format.

Why this exists
---------------
ENTSO-E does not carry the German intraday-auction or imbalance price (the probe
in intraday_probe.py proved it: every A85 query returns "no matching data"). The
reBAP is published by the four German TSOs on netztransparenz.de instead. Its
WebAPI needs OAuth2 client credentials, and the exact data-category / product
path is only listed in the portal's Swagger. This script authenticates with your
credentials, confirms the connection (/health), then tries the likely reBAP
endpoints and prints the CSV header plus a few rows of whatever responds, so the
real fetcher can be built against the actual format instead of a guess.

Setup (one time)
----------------
1. Register on netztransparenz.de for the "WebAPIReader" role (Extranet).
2. In the WebAPI-Portal, create a client -> you get a Client-ID and Client-Secret.
   Portal: https://api-portal.netztransparenz.de/   Extranet: https://extranet.netztransparenz.de
3. Put them in .env (gitignored), next to the ENTSO-E token:
       IPNT_CLIENT_ID=...
       IPNT_CLIENT_SECRET=...

Run:  python netztransparenz_probe.py
Then paste the output back. Reads only; writes nothing.
"""

import datetime as dt
import os
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
TOKEN_URL = "https://identity.netztransparenz.de/users/connect/token"
API = "https://ds.netztransparenz.de/api/v1"


def load_dotenv(path=None):
    path = path or (HERE / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_token():
    cid = os.environ.get("IPNT_CLIENT_ID")
    sec = os.environ.get("IPNT_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Set IPNT_CLIENT_ID and IPNT_CLIENT_SECRET in .env or the environment first.")
    r = requests.post(TOKEN_URL, data={"grant_type": "client_credentials",
                                        "client_id": cid, "client_secret": sec}, timeout=60)
    if not r.ok:
        sys.exit(f"Token request failed: {r.status_code} {r.reason}\n{r.text[:300]}")
    return r.json()["access_token"]


def show(label, url, token):
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=90)
    except Exception as e:
        print(f"[{label}] request error: {type(e).__name__}: {str(e)[:120]}")
        return
    body = r.text or ""
    is_csv = (";" in body.split("\n", 1)[0]) or ("," in body.split("\n", 1)[0])
    print(f"[{label}] HTTP {r.status_code} {r.reason} | bytes={len(body)} | {url}")
    if r.ok and body.strip():
        lines = [ln for ln in body.splitlines() if ln.strip()][:4]
        for ln in lines:
            print("    " + ln[:200])
    elif not r.ok:
        print("    " + body[:200].replace("\n", " "))


def main():
    load_dotenv()
    token = get_token()
    print("Authenticated OK.\n")

    show("health", f"{API}/health", token)

    # A recent finished month, so data is definitely published.
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)   # last day of previous month
    start = end.replace(day=1)                                    # first day of previous month
    d1, d2 = start.isoformat(), end.isoformat()
    print(f"\nTrying reBAP endpoints for {d1}..{d2} "
          f"(pattern: {API}/data/{{data}}/{{product}}/{{from}}/{{to}}):\n")

    # Candidate {data}/{product} segments for the uniform imbalance price.
    candidates = [
        "NrvSaldo/reBAP/Qualitaetsgesichert",   # confirmed from WebAPI docs v1.14 (Format 9)
        "reBAP",
        "Regelenergie/reBAP",
        "Bilanzkreis/reBAP",
        "Ausgleichsenergie/reBAP",
        "Ausgleichsenergiepreis/reBAP",
        "Regelenergie/Ausgleichsenergiepreis",
        "Bilanzkreis/Ausgleichsenergiepreis",
    ]
    for c in candidates:
        show(c, f"{API}/data/{c}/{d1}/{d2}", token)

    print("\nIf one endpoint returned CSV, note its path and the header row: I will "
          "build the fetcher's parser against those exact column names.")


if __name__ == "__main__":
    main()
