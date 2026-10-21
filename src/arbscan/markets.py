"""Canonical markets, their outcomes, and which outcomes a position pays on."""
from __future__ import annotations

from dataclasses import dataclass

OUTCOMES = {
    '1x2': ('home', 'draw', 'away'),
    'ou': ('over', 'under'),          # total goals; line = 2.5 etc.
    'ah': ('home', 'away'),           # Asian handicap; line = home handicap; draw-no-bet is line 0
    'btts': ('btts_yes', 'btts_no'),
}

SIDES = ('back', 'lay', 'yes', 'no')


@dataclass(frozen=True, order=True)
class MarketKey:
    event: str                # canonical event id from the mapper
    market: str               # key of OUTCOMES
    line: float | None = None

    def __str__(self):
        return f'{self.event}/{self.market}' + ('' if self.line is None else f'@{self.line:g}')


def outcomes(key):
    """Outcomes of a market. Integer lines can push; that is fine only when every venue refunds a push."""
    if key.market not in OUTCOMES:
        raise ValueError(f'unsupported market {key.market!r}')
    if key.market in ('ou', 'ah'):
        if key.line is None:
            raise ValueError(f'{key.market} needs a line')
        if (key.line * 4) % 2:
            raise ValueError(f'quarter line {key.line:g} splits the stake in two; not a clean 2-way market')
    return OUTCOMES[key.market]


def covers(key, selection, side):
    """Outcomes a position pays on: back/yes pays on the selection, lay/no on everything else."""
    outs = outcomes(key)
    if selection not in outs:
        raise ValueError(f'{selection!r} is not an outcome of {key.market}')
    if side in ('back', 'yes'):
        return frozenset({selection})
    if side in ('lay', 'no'):
        return frozenset(outs) - {selection}
    raise ValueError(f'unknown side {side!r}')


def partitions(outs):
    """Every split of the outcomes into two or more blocks; an arb takes one leg per block."""
    def rec(items):
        if not items:
            yield []
            return
        first, rest = items[0], items[1:]
        for p in rec(rest):
            for i in range(len(p)):
                yield p[:i] + [p[i] | {first}] + p[i + 1:]
            yield [frozenset({first})] + p
    return [tuple(p) for p in rec(list(outs)) if len(p) >= 2]
