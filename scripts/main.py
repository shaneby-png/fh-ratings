"""
Entry point: fetches the current D1 schedule, computes ACR/RPI/SOS ratings,
and writes a JSON file your front end can consume directly.

Usage:
    python main.py                  # division 1, current default year, writes ratings.json
    python main.py --div 1 --year 2026 --out ratings.json
    python main.py --offline fixture_raw.txt   # skip network fetch, use a saved text file instead
"""
import argparse
import json
import sys

from fetch import fetch_schedule_text
from scraper import parse_games, parse_upcoming
from ratings import compute_ratings, build_schedules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--div", type=int, default=1)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--out", default="ratings.json")
    ap.add_argument("--offline", default=None,
                     help="Path to a saved page-text file, skips the live fetch")
    args = ap.parse_args()

    if args.offline:
        with open(args.offline) as f:
            text = f.read()
    else:
        text = fetch_schedule_text(division=args.div, year=args.year)

    games = parse_games(text)
    if not games:
        print("No games parsed -- check that the page structure hasn't changed.",
              file=sys.stderr)
        sys.exit(1)

    rows = compute_ratings(games)
    upcoming = parse_upcoming(text)
    schedules = build_schedules(games, upcoming)

    output = {
        "division": args.div,
        "year": args.year,
        "games_counted": len(games),
        "ratings": [
            {
                "rank": i + 1,
                "team": r.team,
                "record": r.record,
                "acr": round(r.acr, 4),
                "rpi": round(r.rpi, 4),
                "sos": round(r.sos, 4),
            }
            for i, r in enumerate(rows)
        ],
        "schedules": schedules,
    }

    with open(args.out, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(rows)} teams to {args.out} ({len(games)} games counted)")


if __name__ == "__main__":
    main()
