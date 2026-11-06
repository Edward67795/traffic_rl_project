#!/usr/bin/env python3
"""E12: turn results/results.csv into a Markdown table for the report.

The newest row per suite id wins, so re-running an entry replaces its old result.
Ad-hoc runs (notes marked "adhoc") are left out unless --adhoc is given.

Usage (from the repo root):
    python verification/esbmc/scripts/results_table.py > verification/esbmc/results/results_table.md
"""
import argparse
import csv
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "results" / "results.csv"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adhoc", action="store_true", help="include ad-hoc runs")
    args = ap.parse_args()
    latest = {}
    for row in csv.DictReader(CSV_PATH.open()):
        tag, status = (row["notes"].split(";") + ["", ""])[:2]
        status = status.strip()
        if status == "adhoc" and not args.adhoc:
            continue
        latest[tag.strip()] = (row, status)
    print("| ID | Property | Version | Config | Bound | Result | CE steps | Time (s) | Memory (MB) | As expected |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for tag, (r, status) in latest.items():
        print(f"| {tag} | {r['property']} | {r['version']} | {r['config']} | {r['bound']} | {r['result']} "
              f"| {r['ce_length'] or '—'} | {r['time_s']} | {r['memory_mb']} | {status} |")


if __name__ == "__main__":
    main()
