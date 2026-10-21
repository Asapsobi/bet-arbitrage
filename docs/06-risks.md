# Risks and gotchas

The edge in football arbs is thin (often 0.5–3%), so execution and account risk decide profitability, not detection.

| Risk | What happens | Mitigation |
| --- | --- | --- |
| Account limits | Soft books cut stakes or close accounts once they spot arb patterns | Build on exchanges, Pinnacle, brokers and crypto books that tolerate winners |
| Leg risk | Price moves or bet is rejected after leg 1 fills | Fill the illiquid / slow leg first; auto-hedge the rest on an exchange |
| Voids / palps | A book voids an obvious error price, leaving you one-sided | Skip arbs above a sanity threshold (e.g. > 5%); prefer sharp prices |
| Commission and fees | Exchange commission and withdrawal fees eat the margin | Model net-of-fee odds in the engine, not gross |
| Rollover rules | Pinnacle and brokers charge if you withdraw before turnover | Keep working capital parked per venue; rebalance rarely |
| Bots vs ToS | Venues without public APIs (Stake) may ban automated play | Automate only where an API is offered; manual elsewhere |
| Counterparty | Offshore venues and brokers can freeze funds | Cap exposure per venue; withdraw profits on a schedule |
| Legal / KYC / geo | Betting legality and venue availability depend on where you live; most venues require KYC | Check local law and each venue's restricted-country list before funding |

Account limits are the biggest one: plan the product so it still works if every soft book is gone.
