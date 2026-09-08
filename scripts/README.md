# FH Ratings — replicates FieldHockeyCorner's ACR/RPI/SOS

Scrapes the Division 1 schedule/results from FinalWhistleFH.com and computes
Record, ACR, RPI, and SOS for every team, output as JSON for a front end.

## Setup

```bash
pip install requests beautifulsoup4 numpy
```

## Run

```bash
python main.py --div 1 --year 2026 --out ratings.json
```

This makes a live network request, so it must run somewhere with normal
internet access (your own machine, a server, a cron job/scheduled task) —
it will NOT work inside a sandboxed tool runner with restricted network
access.

For a periodically-refreshing front end, just re-run this on a schedule
(e.g. daily during the season) and have your app read the resulting
`ratings.json`.

## Files

- `fetch.py` — pulls the live page as flattened text
- `scraper.py` — regex-based parser that turns page text into `Game` objects.
  Anchored on the known D1 team-name list (`TEAMS`), which also has the
  side effect of automatically excluding games against non-D1 opponents
  (i.e. only "divisional" games count, matching the site's own rule)
- `ratings.py` — the actual math (see below)
- `main.py` — glues it together, writes JSON

## How the ratings are computed

- **Record**: pure W/L tally from divisional games only (SO/OT results count
  as a normal decision).
- **ACR**: FieldHockeyCorner describes this as "an equal weighting of two
  computer ratings — one on goal differentials (capped at 5), one on wins
  and losses" but doesn't publish the underlying rating algorithm. This
  implementation uses a standard **Massey-style least-squares rating**
  (solve a linear system from pairwise schedule results) for each of the
  two components, z-normalizes both so they sit on a comparable scale, then
  averages them. This is a faithful, defensible interpretation of "equal
  weighting of two computer ratings" but **will not produce numerically
  identical values** to the original site unless it happens to use the same
  algorithm — treat ACR's *relative ordering* as the meaningful output, not
  the raw number.
- **SOS**: average of opponents' W/L percentage, with games against the
  target team excluded from each opponent's percentage — exactly as
  described on the site, weighted per-game (a team played twice counts
  twice).
- **RPI**: `0.25 * own W/L% + 0.50 * SOS + 0.25 * opponents' SOS`, where
  opponents' SOS is the average of each opponent's own SOS value.

## Known limitations / things to sanity-check as the season progresses

1. **Team roster drift**: `TEAMS` in `scraper.py` is hardcoded from this
   season's "Teams" list. If a team is added/dropped/renamed, update that
   list or games involving it will be silently skipped.
2. **Page structure changes**: this is a scrape, not an API — if
   FinalWhistleFH changes their HTML/text layout, `GAME_CHUNK_RE` in
   `scraper.py` may need adjusting. Re-run `python scraper.py` against a
   fresh saved copy of the page text to check it still parses expected
   game counts.
3. **Ties**: field hockey rarely ends in a true tie at this level (games
   go to OT/SO), but the code supports 0.5/0.5 win-pct credit if one shows
   up in the data.
4. **Region splits**: this version computes one combined D1 ranking. If you
   later want the Mid-Atlantic/Mideast/Northeast/South/West regional views
   like the original site, you'd need a team → region mapping (not present
   in the scraped page) to filter games/teams before calling
   `compute_ratings()`.
5. Respect FinalWhistleFH's terms of use / robots.txt for scraping
   frequency — don't hit it more than once every so often (e.g. hourly at
   most, daily is plenty during a normal season).
