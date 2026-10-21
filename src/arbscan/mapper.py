"""Event mapping across venues: the same match, with home and away the same way round.

A wrong match makes a fake arb, so only exact or near-exact name matches are
automatic. Partial names ('Bayern' vs 'Bayern Munich'), swapped home/away and
weak matches go to review; add an alias once a review is confirmed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher

# Normalized spelling -> canonical spelling. Extend as reviews are confirmed.
ALIASES = {
    'bayern munchen': 'bayern munich',
    'man utd': 'manchester united',
    'man united': 'manchester united',
    'man city': 'manchester city',
    'spurs': 'tottenham hotspur',
    'tottenham': 'tottenham hotspur',
    'wolves': 'wolverhampton wanderers',
    'psg': 'paris saint germain',
    'paris sg': 'paris saint germain',
    'inter': 'inter milan',
    'internazionale': 'inter milan',
    'milan': 'ac milan',
    'atletico': 'atletico madrid',
    'atl madrid': 'atletico madrid',
}
DROP = {'fc', 'afc', 'cf', 'sc', 'fk', 'sk', 'cd', 'the'}


@dataclass(frozen=True)
class VenueEvent:
    venue: str
    id: str
    home: str
    away: str
    kickoff: float                 # unix seconds


@dataclass(frozen=True)
class Match:
    event: VenueEvent | None
    score: float
    status: str                    # 'auto', 'review' or 'none'
    swapped: bool = False          # the candidate lists the teams the other way round


def normalize(name, aliases=ALIASES):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = ' '.join(t for t in re.sub(r'[^a-z0-9]+', ' ', s).split() if t not in DROP)
    return aliases.get(s, s)


def _sim(a, b):
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def _partial(a, b):
    ta, tb = set(a.split()), set(b.split())
    return bool(ta and tb) and (ta <= tb or tb <= ta)


def event_id(ev, aliases=ALIASES):
    day = datetime.fromtimestamp(ev.kickoff, timezone.utc).strftime('%Y-%m-%d')
    slug = lambda n: normalize(n, aliases).replace(' ', '-')
    return f'{day}:{slug(ev.home)}-v-{slug(ev.away)}'


class Mapper:
    def __init__(self, aliases=ALIASES, kickoff_tolerance=600.0, auto=0.92, review=0.6):
        self.aliases, self.tol, self.auto, self.review = aliases, kickoff_tolerance, auto, review

    def match(self, ev, candidates):
        """Best candidate on another venue for `ev`."""
        h, a = normalize(ev.home, self.aliases), normalize(ev.away, self.aliases)
        best = Match(None, 0.0, 'none')
        rank = {'none': 0, 'review': 1, 'auto': 2}
        for c in candidates:
            if c.venue == ev.venue or abs(c.kickoff - ev.kickoff) > self.tol:
                continue
            ch, ca = normalize(c.home, self.aliases), normalize(c.away, self.aliases)
            for swapped, (x, y) in ((False, (ch, ca)), (True, (ca, ch))):
                score = min(_sim(h, x), _sim(a, y))
                if score >= self.auto and not swapped:
                    status = 'auto'
                elif score >= self.review or (_partial(h, x) and _partial(a, y)):
                    status = 'review'
                else:
                    continue
                if (rank[status], score) > (rank[best.status], best.score):
                    best = Match(c, score, status, swapped)
        return best
