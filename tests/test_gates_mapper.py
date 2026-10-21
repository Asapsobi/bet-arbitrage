from datetime import datetime, timezone

from arbscan import gates
from arbscan.lifecycle import Episode
from arbscan.mapper import Mapper, VenueEvent, event_id
from arbscan.markets import MarketKey

DAY0 = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()


def ep(market, start, life=20.0, roi=0.006, depth=300.0, flags=(), gone_after=1.0):
    return Episode(f'{market}|x', MarketKey(market, 'ou', 2.5), ('a', 'b'), ('polymarket', 'smarkets'),
                   start, start + life, roi, roi, roi, depth, depth, frozenset(flags),
                   closed_at=start + life + gone_after)


def by_gate(res):
    return {g.gate.split()[0]: g for g in res}


def three_days():
    eps = [ep(f'm{d}{i}', DAY0 + d * 86400 + 3600 * i) for d, n in ((0, 4), (1, 3), (2, 3)) for i in range(n)]
    eps.append(ep('m00', DAY0 + 5, life=10))                       # overlaps m00: same chance, counted once
    eps.append(ep('palp', DAY0 + 7200, roi=0.05, flags=('palp',)))  # error price: never counted
    return eps


def test_gates_on_three_days():
    g = by_gate(gates.evaluate(three_days(), (DAY0, DAY0 + 3 * 86400 - 1), [1.0] * 10))
    assert (g['G2'].value, g['G2'].verdict) == ('3', 'GO')
    assert (g['G3'].value, g['G3'].verdict) == ('$300', 'GO')
    assert g['G4'].verdict == 'GO' and g['G4'].go_if == '>= 2 s'      # 1 s polling counts as streaming
    assert g['G6'].verdict == 'GREY'                                   # 10 x 0.6% x $300 over 3 days ~ $180/month
    assert g['G1'].verdict == 'MANUAL' and g['G5'].verdict == 'N/A'


def test_lifetimes_shorter_than_polling_are_called_out():
    eps = [ep(f'm{i}', DAY0 + 3600 * i, life=0.0, gone_after=30.0) for i in range(5)]   # seen once, gone next poll
    g = by_gate(gates.evaluate(eps, (DAY0, DAY0 + 86400 * 2), [30.0] * 10))
    assert g['G4'].verdict == 'GREY' and 'not resolved' in g['G4'].note


def test_thin_and_empty_windows():
    g = by_gate(gates.evaluate([ep('m', DAY0)], (DAY0, DAY0 + 600), [5.0]))
    assert g['G2'].verdict == 'N/A' and g['G6'].verdict == 'N/A'
    assert all(x.verdict in ('N/A', 'MANUAL') for x in gates.evaluate([], None, []))


def test_mapper():
    m = Mapper()
    ref = VenueEvent('smarkets', '1', 'Bayern Munich', 'Arsenal', DAY0)
    assert m.match(ref, [VenueEvent('polymarket', 'a', 'FC Bayern München', 'Arsenal FC', DAY0 + 60)]).status == 'auto'
    assert m.match(ref, [VenueEvent('polymarket', 'b', 'Bayern', 'Arsenal', DAY0)]).status == 'review'
    swapped = m.match(ref, [VenueEvent('polymarket', 'c', 'Arsenal', 'Bayern Munich', DAY0)])
    assert swapped.status == 'review' and swapped.swapped
    assert m.match(ref, [VenueEvent('polymarket', 'd', 'Bayern Munich', 'Arsenal', DAY0 + 3 * 3600)]).status == 'none'
    milan = VenueEvent('smarkets', '2', 'AC Milan', 'Roma', DAY0)
    assert m.match(milan, [VenueEvent('polymarket', 'e', 'Inter', 'Roma', DAY0)]).status != 'auto'
    assert event_id(ref) == '2026-11-01:bayern-munich-v-arsenal'
