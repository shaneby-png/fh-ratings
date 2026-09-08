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


# Known D1 team names (verbatim from the site's Teams listing, longest-first
# for correct greedy regex matching of multi-word names like "William & Mary").
TEAMS = sorted([
    "American", "Appalachian State", "Ball State", "Bellarmine", "Boston College",
    "Boston University", "Brown", "Bryant", "Bucknell", "California",
    "Central Michigan", "Colgate", "Columbia", "Cornell", "Dartmouth", "Davidson",
    "Delaware", "Drexel", "Duke", "Fairfield", "Georgetown", "Harvard", "Hofstra",
    "Holy Cross", "Indiana", "Iowa", "James Madison", "Kent State", "La Salle",
    "Lafayette", "Lehigh", "Liberty", "LIU", "Lock Haven", "Longwood", "Louisville",
    "Maine", "Maryland", "Massachusetts", "Mercyhurst", "Merrimack", "Miami (OH)",
    "Michigan", "Michigan State", "Monmouth", "New Hampshire", "New Haven",
    "North Carolina", "Northeastern", "Northwestern", "Ohio", "Ohio State",
    "Old Dominion", "Penn", "Penn State", "Princeton", "Providence", "Queens (NC)",
    "Quinnipiac", "Richmond", "Rider", "Rutgers", "Sacred Heart", "Saint Louis",
    "St. Joseph's", "Stanford", "Stonehill", "Syracuse", "Temple", "Towson",
    "UAlbany", "UC Davis", "UConn", "UMass Lowell", "VCU", "Vermont", "Villanova",
    "Virginia", "Wagner", "Wake Forest", "William & Mary", "Yale",
], key=len, reverse=True)

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

GAME_CHUNK_RE = re.compile(
    r"(?P<date>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})"
    r"(?:\s*·[^F]*?)?"  # optional time suffix before 'Final'
    r"\s+Final\s+(?P<body>.*?)(?=Report\s+Box Score|Box Score Recap|Box Score(?!\s*Recap)|$)",
    re.DOTALL,
)


def parse_games(raw_text: str) -> list[Game]:
    games: list[Game] = []
    for chunk_match in GAME_CHUNK_RE.finditer(raw_text):
        date = chunk_match.group("date")
        body = chunk_match.group("body")
        team_matches = list(TEAM_SCORE_RE.finditer(body))
        if len(team_matches) != 2:
            # Unparseable or non-standard row (e.g. postponed, TBD) — skip.
            continue
        a, b = team_matches
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
