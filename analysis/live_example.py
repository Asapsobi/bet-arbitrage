"""Net-of-fee arb check on a real snapshot: Bayern Munich vs Arsenal, 2026-10-21.

Quotes: Smarkets v3 public API (~09:06 UTC, event 45379705) and Polymarket Gamma API
(~09:07 UTC, event ucl-bay-ars-2026-10-21). Smarkets prices are basis points of
probability (4587 = 45.87% = decimal 2.180). Polymarket NO ask = 1 - YES bid.
"""
import numpy as np

C_SMK = 0.02   # Smarkets commission on net market winnings
PM_FEE = 0.05  # Polymarket sports taker fee rate: fee per share = r * p * (1 - p)


def eff_back(o, c=C_SMK):
    return 1 + (o - 1) * (1 - c)


def eff_lay(L, c=C_SMK):
    """Lay at decimal L, expressed as a back on 'not this outcome'."""
    return 1 + (1 - c) / (L - 1)


def eff_pm(p, r=PM_FEE):
    return 1 / (p + r * p * (1 - p))


def smk(bp):
    return 10000 / bp


def arb(legs, bankroll=1000):
    S = sum(1 / o for o in legs)
    return S, bankroll * (1 / S - 1), [bankroll * (1 / o) / S for o in legs]


def report(name, gross, net):
    gs, _, _ = arb(gross)
    ns, pnl, stakes = arb(net)
    print(f'{name:<48} gross S={gs:.4f} ({(1 / gs - 1) * 100:+.2f}%)  '
          f'net S={ns:.4f} ({(1 / ns - 1) * 100:+.2f}%)  stakes={[round(s, 2) for s in stakes]}')


report('B  back Bayern Smk + NO Bayern PM 0.53',
       [smk(4587), 1 / 0.53], [eff_back(smk(4587)), eff_pm(0.53)])
report('B2 YES Arsenal PM 0.29 + lay Arsenal Smk',
       [1 / 0.29, smk(2941) / (smk(2941) - 1)], [eff_pm(0.29), eff_lay(smk(2941))])
report('C  Under 2.5 Smk + Over 2.5 PM 0.62',
       [smk(3788), 1 / 0.62], [eff_back(smk(3788)), eff_pm(0.62)])
report('A2 1X2 Smarkets only (gross; no commission on a net loss)',
       [smk(4587), smk(2500), smk(2985)], [smk(4587), smk(2500), smk(2985)])
report('A3 1X2 Polymarket only',
       [1 / 0.48, 1 / 0.25, 1 / 0.29], [eff_pm(0.48), eff_pm(0.25), eff_pm(0.29)])

# A: Bayern + Draw backed on the same Smarkets market, Arsenal YES on Polymarket.
# Commission applies to net market winnings, so solve the equal-payout system directly.
B, oB, oD, pA = 1000, smk(4587), smk(2500), 0.29
kA = 1 / (pA + PM_FEE * pA * (1 - pA))  # Polymarket payout per unit staked
#   P_Bayern = (sB(oB-1) - sD)(1-c) - sA
#   P_Draw   = (sD(oD-1) - sB)(1-c) - sA
#   P_Ars    = sA(kA-1) - sB - sD
M = np.array([
    [(oB - 1) * (1 - C_SMK) + (1 - C_SMK), -(1 - C_SMK) - (oD - 1) * (1 - C_SMK), 0],  # P_B - P_D = 0
    [(oB - 1) * (1 - C_SMK) + 1, -(1 - C_SMK) + 1, -kA],                              # P_B - P_A = 0
    [1, 1, 1],                                                                         # sB + sD + sA = B
])
sB, sD, sA = np.linalg.solve(M, [0, 0, B])
pnl = (sB * (oB - 1) - sD) * (1 - C_SMK) - sA
print(f'{"A  1X2 best of two venues (market-level comm.)":<48} stakes={[round(float(s), 1) for s in (sB, sD, sA)]} '
      f'pnl={pnl:.2f} ({pnl / B * 100:+.2f}%)')
