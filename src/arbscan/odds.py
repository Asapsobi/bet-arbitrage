"""Price conversions and net-of-fee effective odds.

Every leg is turned into effective decimal odds o' (payout per unit at risk
when the leg wins, after the venue's fee) before legs are summed. Formulas are
the ones in docs/08-research-report-fa.md, section on formulas.
"""


def from_bp(bp):
    """Smarkets quotes basis points of probability: 4587 -> 2.180."""
    return 10000 / bp


def back(o, c):
    """Exchange back at decimal o, commission c on winnings."""
    return 1 + (o - 1) * (1 - c)


def lay_gross(L):
    """Exchange lay at decimal L, as a back on 'not this outcome', before commission."""
    return L / (L - 1)


def lay(L, c):
    """Exchange lay at decimal L as a back on 'not this outcome', commission c on winnings."""
    return 1 + (1 - c) / (L - 1)


def share_cost(p, r):
    """Cost of one prediction-market share at price p with taker fee r * p * (1 - p)."""
    return p + r * p * (1 - p)


def share(p, r):
    """Prediction-market share bought at p (pays 1), taker fee rate r."""
    return 1 / share_cost(p, r)
