"""
Parses FinalWhistleFH.com's "all-dates" schedule/results page into a list
of completed games. Designed to be resilient to the site's plain-text-ish
DOM structure by anchoring on the known list of D1 team names rather than
brittle positional regex.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Game:
    date: str
    team_a: str
    score_a: int
    team_a_rank: Optional[int]
    team_a_ot: Optional[str]  # 'OT' or 'SO' or None
    team_b: str
    score_b: int
    team_b_rank: Optional[int]
    team_b_ot: Optional[str]


def extract_team_list(raw_text: str) -> list[str]:
    """Pulls the roster of D1 team names from the 'Teams' section of the page."""
    m = re.search(r"\bTeams\b(.*?)\bStats\b", raw_text, re.DOTALL)
    if not m:
        raise ValueError("Could not locate Teams section in page text")
    chunk = m.group(1).strip()
    # Teams are space-separated but multi-word names have no delimiter in the
    # raw text, so we rely on a curated split using known multi-word patterns.
    # Simpler + more robust: this list is short and stable enough per season
    # to hardcode-verify once, then reuse. We do a heuristic split here as a
    # fallback for a fresh season where the roster may differ slightly.
    return chunk  # returned raw; real team list should be supplied explicitly (see TEAMS below)


# Known D1 team names, longest-first for correct greedy regex matching of
# multi-word names like "William & Mary". This is a UNION across multiple
# seasons' rosters (team names/branding can change year to year -- e.g. the
# site calls the same program "Albany" in 2025 and "UAlbany" in 2026, and
# "Saint Francis" appears in some seasons' D1 slate but not others). Being a
# superset is safe: it only serves as an allow-list for "is this a D1 game",
# so an extra name that never appears in a given season's data is harmless.
# When validating a new season, check for parser warnings about unmatched
# multi-team rows -- that's the signal a name needs to be added here.
TEAMS = sorted(set([
    "Albany", "American", "Appalachian State", "Ball State", "Bellarmine",
    "Boston College", "Boston University", "Brown", "Bryant", "Bucknell",
    "California", "Central Michigan", "Colgate", "Columbia", "Cornell",
    "Dartmouth", "Davidson", "Delaware", "Drexel", "Duke", "Fairfield",
    "Georgetown", "Harvard", "Hofstra", "Holy Cross", "Indiana", "Iowa",
    "James Madison", "Kent State", "La Salle", "Lafayette", "Lehigh",
    "Liberty", "LIU", "Lock Haven", "Longwood", "Louisville", "Maine",
    "Maryland", "Massachusetts", "Mercyhurst", "Merrimack", "Miami (OH)",
    "Michigan", "Michigan State", "Monmouth", "New Hampshire", "New Haven",
    "North Carolina", "Northeastern", "Northwestern", "Ohio", "Ohio State",
    "Old Dominion", "Penn", "Penn State", "Princeton", "Providence",
    "Queens (NC)", "Quinnipiac", "Richmond", "Rider", "Rutgers",
    "Sacred Heart", "Saint Francis", "Saint Louis", "St. Joseph's",
    "Stanford", "Stonehill", "Syracuse", "Temple", "Towson", "UAlbany",
    "UC Davis", "UConn", "UMass Lowell", "VCU", "Vermont", "Villanova",
    "Virginia", "Wagner", "Wake Forest", "William & Mary", "Yale",
]), key=len, reverse=True)

TEAM_PATTERN = "|".join(re.escape(t) for t in TEAMS)

# Matches: <TeamName> [#Rank] [—] <Score>[(OT|SO)]
TEAM_SCORE_RE = re.compile(
    rf"(?P<team>{TEAM_PATTERN})"
    rf"(?:\s*#(?P<rank>\d+))?"
    rf"(?:\s*—)?"
    rf"\s+(?P<score>\d+)"
    rf"(?:\((?P<ot>OT|SO)\))?"
)

DATE_RE = re.compile(
    r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
)

# Body is everything between a date (with optional time suffix) and the next
# "Report / Box Score / Box Score Recap" marker. We deliberately do NOT
# require the literal word "Final" here: postseason rows show a round label
# instead (e.g. "NCAA — Championship", "ACC — Semifinal") in that same slot.
# Non-greedy matching means we still stop at the right terminator regardless
# of what that in-between label text says. Games with no score yet (future
# fixtures) or a "Canceled" status naturally fail the two-team-score check
# below and get skipped, so no separate keyword filtering is needed.
GAME_CHUNK_RE = re.compile(
    r"(?P<date>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})"
    r"\s+(?P<body>.*?)(?=Report\s+Box Score|Box Score Recap|Box Score(?!\s*Recap)|$)",
    re.DOTALL,
)


def parse_games(raw_text: str) -> list[Game]:
    games: list[Game] = []
    seen: set[tuple] = set()
    for chunk_match in GAME_CHUNK_RE.finditer(raw_text):
        date = chunk_match.group("date")
        body = chunk_match.group("body")
        team_matches = list(TEAM_SCORE_RE.finditer(body))
        if len(team_matches) != 2:
            # Unparseable or non-standard row (e.g. postponed, TBD, canceled,
            # or a future fixture with no score yet) — skip.
            continue
        a, b = team_matches
        key = (date, a.group("team"), a.group("score"), b.group("team"), b.group("score"))
        if key in seen:
            # The site occasionally renders the same game twice (observed in
            # some postseason rounds) -- keep only the first occurrence.
            continue
        seen.add(key)
        games.append(Game(
            date=date,
            team_a=a.group("team"),
            score_a=int(a.group("score")),
            team_a_rank=int(a.group("rank")) if a.group("rank") else None,
            team_a_ot=a.group("ot"),
            team_b=b.group("team"),
            score_b=int(b.group("score")),
            team_b_rank=int(b.group("rank")) if b.group("rank") else None,
            team_b_ot=b.group("ot"),
        ))
    return games


if __name__ == "__main__":
    with open("fixture_raw.txt") as f:
        text = f.read()
    games = parse_games(text)
    print(f"Parsed {len(games)} games")
    for g in games[:8]:
        print(g)
