"""CLI: python analyze.py data.csv [--json out.json]"""
import argparse
import json

from app.services.analyzer import analyze_csv

ap = argparse.ArgumentParser()
ap.add_argument("csv")
ap.add_argument("--json", help="write the full analysis to this file")
args = ap.parse_args()

res = analyze_csv(args.csv)
ov = res["overview"]
print(f"Rows: {ov['rows']:,} | Columns: {ov['columns']} | "
      f"Duplicates: {ov['duplicate_rows']} | Quality: {res['quality_score']}/100")
print("\nFindings\n--------")
for f in res["findings"]:
    print(f"[{f['severity'].upper():6}] {f['message']}")

if args.json:
    with open(args.json, "w") as fh:
        json.dump(res, fh, indent=2)
    print(f"\nSaved -> {args.json}")