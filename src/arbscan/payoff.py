"""Equal-payout stakes when exchange commission is charged on net market winnings.

Per-leg net odds assume each leg pays commission on its own winnings. When two
legs sit in the same exchange market the venue charges commission once, on
the market's net result, which costs less. This solves the stakes that pay the
same in every outcome under that rule (docs/08, formulas section, case A).
"""
from itertools import product


def _solve(a, b):
    """Gaussian elimination with partial pivoting; None if singular."""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return None
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def equal_payout(legs):
    """(stakes per unit bankroll, profit per unit bankroll), or None if no positive solution.

    Leg i must be the only leg paying on its block of outcomes, so in block i
    leg i wins and every other leg loses.
    """
    k = len(legs)
    groups = {}
    for i, leg in enumerate(legs):
        if leg.group:
            groups.setdefault(leg.group, []).append(i)
    shared = {g: ix for g, ix in groups.items() if len(ix) > 1}
    grouped = {i for ix in shared.values() for i in ix}

    def group_row(g, b):           # the group's net market result in block b, per unit of each stake
        row = [0.0] * k
        for i in shared[g]:
            row[i] = legs[i].gross_odds - 1 if i == b else -1.0
        return row

    def payoff_rows(wins):         # wins[(g, b)]: the group nets a win in block b, so commission applies
        rows = []
        for b in range(k):
            row = [0.0] * k
            for i in range(k):
                if i not in grouped:
                    row[i] = legs[i].net_odds - 1 if i == b else -1.0
            for g, ix in shared.items():
                f = 1 - legs[ix[0]].commission if wins[(g, b)] else 1.0
                row = [x + f * v for x, v in zip(row, group_row(g, b))]
            rows.append(row)
        return rows

    def dot(u, v):
        return sum(x * y for x, y in zip(u, v))

    cells = [(g, b) for g in shared for b in range(k)]
    for pattern in product((True, False), repeat=len(cells)):
        wins = dict(zip(cells, pattern))
        rows = payoff_rows(wins)
        a = [[x - y for x, y in zip(rows[b], rows[0])] for b in range(1, k)] + [[1.0] * k]
        s = _solve(a, [0.0] * (k - 1) + [1.0])
        if s is None or min(s) <= 0:
            continue
        if all((dot(group_row(g, b), s) > 0) == wins[(g, b)] for g, b in cells):
            return s, dot(rows[0], s)
    return None
