#!/usr/bin/env python3
"""Crash volume for a signature, from Socorro's public SuperSearch API.

  crash_stats.py "SIGNATURE" [--days 28] [--product Firefox] …

Prints the total and the top values per facet (version, release channel,
platform, process type, product) as JSON. Used instead of socorro-cli in locked
runs, where socorro-cli's TLS fails inside the macOS sandbox. Anonymous: no
personal data or crash report details, only counts.
"""

import argparse
import datetime
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmo_http  # noqa: E402

API = "https://crash-stats.mozilla.org/api/SuperSearch/"
FACETS = ("version", "release_channel", "platform", "process_type", "product")


def query(signature, days, products, today=None):
    """SuperSearch params for an exact signature over the last `days` days."""
    if not signature or len(signature) > 500:
        raise ValueError("signature must be 1-500 characters")
    today = today or datetime.date.today()
    start = (today - datetime.timedelta(days=days)).isoformat()
    params = [("signature", "=" + signature), ("date", ">=" + start), ("_results_number", "0")]
    params += [("product", p) for p in products]
    params += [("_facets", f) for f in FACETS]
    params += [("_facets_size", "10")]
    return params


def summarize(data, days):
    out = {"days": days, "total": data.get("total", 0)}
    for facet, rows in (data.get("facets") or {}).items():
        out[facet] = {str(r.get("term")): r.get("count") for r in rows}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signature", help="exact signature, without [@ ]")
    ap.add_argument("--days", type=int, default=28, choices=range(1, 181), metavar="1-180")
    ap.add_argument("--product", action="append", default=[], help="repeatable; default: all")
    args = ap.parse_args(argv)
    url = API + "?" + urllib.parse.urlencode(query(args.signature, args.days, args.product))
    data = json.loads(bmo_http.get(url, limit=4 * 1024 * 1024))
    json.dump(summarize(data, args.days), sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
