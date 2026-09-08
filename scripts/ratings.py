"""
Computes Record / ACR / RPI / SOS for a set of completed divisional games,
replicating the methodology described on FieldHockeyCorner.com:

  ACR (Average Computer Rating) = equal-weighted average of:
     (a) a computer rating built purely from goal differentials
         (capped at +/-5 per game to blunt "running up the score")
     (b) a computer rating built purely from win/loss results
  RPI = 0.25 * own W/L pct + 0.50 * SOS + 0.25 * opponents' SOS
  SOS = average of opponents' W/L pct, excluding games against the target team

The exact computer-rating algorithm FieldHockeyCorner uses isn't published,
so this implements a standard Massey-style least-squares rating (the common
approach for this kind of "two blended computer ratings" system), then
z-normalizes both components before averaging so the "equal weighting" is
meaningful despite the two rating types living on different natural scales.
"""
from collections import defaultdict
from dataclasses import dataclass
import numpy as np

from scraper import Game, UpcomingGame, parse_games

GOAL_CAP = 5


@dataclass
class TeamRow:
    team: str
    wins: int
    losses: int
    record: str
    acr: float
    rpi: float
    sos: float


def _massey_ratings(teams: list[str], team_idx: dict[str, int], pairwise_diffs: list[tuple[int, int, float]]) -> dict[str, float]:
    """
    Solves a Massey-style linear system for ratings from a list of
    (team_i_idx, team_j_idx, diff) where diff = value attributed to team_i
    relative to team_j for that single game (e.g. capped goal margin, or
    +1/-1 for a win/loss rating).
    """
    n = len(teams)
    M = np.zeros((n, n))
    p = np.zeros(n)

    for i, j, diff in pairwise_diffs:
        M[i, i] += 1
        M[i, j] -= 1
        M[j, j] += 1
        M[j, i] -= 1
        p[i] += diff
        p[j] -= diff

    # System is singular (rows sum to 0) -> pin down with sum(ratings) = 0
    M[-1, :] = 1
    p[-1] = 0

    ratings = np.linalg.lstsq(M, p, rcond=None)[0]
    return {team: ratings[team_idx[team]] for team in teams}


def _zscore(d: dict[str, float]) -> dict[str, float]:
    vals = np.array(list(d.values()))
    mean, std = vals.mean(), vals.std()
    if std == 0:
        return {k: 0.0 for k in d}
    return {k: (v - mean) / std for k, v in d.items()}


_MONTH_ORDER = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


def _date_sort_key(date_str: str) -> tuple[int, int]:
    """'Fri, Sep 5' -> (8, 5) for chronological sort within a single season."""
    _, rest = date_str.split(", ", 1)
    month, day = rest.split()
    return (_MONTH_ORDER.get(month, 0), int(day))


def build_schedules(
    games: list[Game], upcoming: list[UpcomingGame] | None = None
) -> dict[str, list[dict]]:
    """
    Per-team list of every game -- played and upcoming -- sorted oldest to
    newest. Used to power a team's schedule/results view; not needed for the
    rating math itself, so this is a separate pass over the parsed data.
    """
    schedules: dict[str, list[dict]] = defaultdict(list)
    for g in games:
        for team, opp, gf, ga, ot in [
            (g.team_a, g.team_b, g.score_a, g.score_b, g.team_a_ot),
            (g.team_b, g.team_a, g.score_b, g.score_a, g.team_b_ot),
        ]:
            if gf > ga:
                result = "W"
            elif gf < ga:
                result = "L"
            else:
                result = "T"
            schedules[team].append({
                "status": "final",
                "date": g.date,
                "opponent": opp,
                "team_score": gf,
                "opp_score": ga,
                "result": result,
                "ot": ot,
            })

    for u in (upcoming or []):
        for team, opp in [(u.team_a, u.team_b), (u.team_b, u.team_a)]:
            schedules[team].append({
                "status": "upcoming",
                "date": u.date,
                "time": u.time,
                "opponent": opp,
            })

    for team in schedules:
        schedules[team].sort(key=lambda row: _date_sort_key(row["date"]))

    return schedules


def compute_ratings(games: list[Game]) -> list[TeamRow]:
    teams = sorted({g.team_a for g in games} | {g.team_b for g in games})
    team_idx = {t: i for i, t in enumerate(teams)}

    # Per-team game log: list of (opponent, result) where result is 1.0/0.0/0.5
    game_log: dict[str, list[tuple[str, float]]] = defaultdict(list)
    goal_diff_pairs: list[tuple[int, int, float]] = []
    winloss_pairs: list[tuple[int, int, float]] = []

    for g in games:
        diff = g.score_a - g.score_b
        capped = max(-GOAL_CAP, min(GOAL_CAP, diff))
        i, j = team_idx[g.team_a], team_idx[g.team_b]
        goal_diff_pairs.append((i, j, capped))

        if g.score_a > g.score_b:
            wl = 1.0
            game_log[g.team_a].append((g.team_b, 1.0))
            game_log[g.team_b].append((g.team_a, 0.0))
        elif g.score_a < g.score_b:
            wl = -1.0
            game_log[g.team_a].append((g.team_b, 0.0))
            game_log[g.team_b].append((g.team_a, 1.0))
        else:
            wl = 0.0
            game_log[g.team_a].append((g.team_b, 0.5))
            game_log[g.team_b].append((g.team_a, 0.5))
        winloss_pairs.append((i, j, wl))

    goal_rating = _massey_ratings(teams, team_idx, goal_diff_pairs)
    wl_rating = _massey_ratings(teams, team_idx, winloss_pairs)
    goal_z = _zscore(goal_rating)
    wl_z = _zscore(wl_rating)
    acr = {t: (goal_z[t] + wl_z[t]) / 2 for t in teams}

    def win_pct(team: str, exclude: str | None = None) -> float:
        results = [r for (opp, r) in game_log[team] if opp != exclude]
        if not results:
            return 0.0
        return sum(results) / len(results)

    sos: dict[str, float] = {}
    for team in teams:
        opp_pcts = [win_pct(opp, exclude=team) for (opp, _r) in game_log[team]]
        sos[team] = sum(opp_pcts) / len(opp_pcts) if opp_pcts else 0.0

    rpi: dict[str, float] = {}
    for team in teams:
        own_pct = win_pct(team)
        opp_sos = [sos[opp] for (opp, _r) in game_log[team]]
        oos = sum(opp_sos) / len(opp_sos) if opp_sos else 0.0
        rpi[team] = 0.25 * own_pct + 0.50 * sos[team] + 0.25 * oos

    rows = []
    for team in teams:
        wins = sum(1 for (_o, r) in game_log[team] if r == 1.0)
        losses = sum(1 for (_o, r) in game_log[team] if r == 0.0)
        ties = sum(1 for (_o, r) in game_log[team] if r == 0.5)
        record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        rows.append(TeamRow(
            team=team, wins=wins, losses=losses, record=record,
            acr=acr[team], rpi=rpi[team], sos=sos[team],
        ))

    rows.sort(key=lambda r: r.acr, reverse=True)
    return rows


if __name__ == "__main__":
    with open("fixture_raw.txt") as f:
        text = f.read()
    games = parse_games(text)
    print(f"{len(games)} divisional games parsed\n")
    rows = compute_ratings(games)
    print(f"{'Rank':<5}{'Team':<20}{'Record':<10}{'ACR':>8}{'RPI':>8}{'SOS':>8}")
    for rank, r in enumerate(rows, start=1):
        print(f"{rank:<5}{r.team:<20}{r.record:<10}{r.acr:>8.3f}{r.rpi:>8.3f}{r.sos:>8.3f}")
