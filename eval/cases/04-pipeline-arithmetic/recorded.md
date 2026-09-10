# Pipeline Report — full pipeline (as of 2026-09-10)

**Data integrity notes first**, since three of nine deals have inconsistencies that affect the numbers below:

- **D-206 Talvik Steel**: stored `weighted` (120,000) doesn't match `amount × stage_pct` (250,000 × 0.4 = 100,000). Recomputed value (100,000) used below, per methodology.
- **D-203 Halden Energie**: note explicitly flags the stage probability (0.3) as hand-edited and no longer matching the `discovery` stage. Amount is small (€23K) so impact is minor, but the figure is not trustworthy.
- **D-208 Brenner Mobility**: `expected_close` is blank. It cannot be classified into commit, best case, or slippage — excluded from all quarter-dated categories below and just carried in open pipeline and the account breakdown.

---

## 1. Forecast vs quota (quota = €1,000,000/quarter)

| Category | Value | vs quota |
|---|---|---|
| Closed (won) | €300,000 | 30% |
| Commit | €1,190,000 | 119% |
| Best case (cumulative, includes commit) | €1,350,000 | 135% |

- Commit = D-201 Northwind Marine (€780K) + D-202 Verta Robotics (€410K) — both negotiation, 0.8 probability, qualification ≥7, closing this quarter.
- Best case adds D-204 Kestrel Pharma (€160K) — proposal, 0.6 probability, qualification 6, closing this quarter.
- D-207 Marrow Water (negotiation, 0.8) just misses both tiers — qualification score is only 5.

## 2. Coverage and slippage

- Open pipeline (full value): **€1,878,000**
- Open pipeline (weighted, corrected for the D-206 discrepancy): **€1,331,900**
- Remaining quota (quota − closed): €700,000
- **Coverage = 1.90x**
- **Slipped deals: 1**, worth €90,000 — D-205 Orbit Logistics (expected close 2026-08-15, still open; partner hasn't booked the technical call).

## 3. Deals at risk

**2 deals, €340,000 total:**

- D-205 Orbit Logistics — €90,000 (also slipped; partner stalled on technical call)
- D-206 Talvik Steel — €250,000 (budget frozen pending 2027 capex plan; also carries the weighted-value discrepancy above)

## 4. Breakdown by account

| Account | Amount | Status / flag |
|---|---|---|
| Northwind Marine | €780,000 | open, commit |
| Verta Robotics | €410,000 | open, commit |
| Ferro Group | €300,000 | closed-won |
| Talvik Steel | €250,000 | open, at risk, weighted-value mismatch |
| Kestrel Pharma | €160,000 | open, best case |
| Marrow Water | €120,000 | open, thin qualification |
| Orbit Logistics | €90,000 | open, at risk, slipped |
| Brenner Mobility | €45,000 | open, missing close date |
| Halden Energie | €23,000 | open, stage/probability mismatch |

## 5. Bottom line

Yes, on paper the quarter is covered — commit alone (€1.19M) already exceeds the €700K of remaining quota — but that cushion rests almost entirely on two deals, so the single biggest lever is keeping Northwind Marine and Verta Robotics on track to close in Q3, since between them they carry the whole quarter.
