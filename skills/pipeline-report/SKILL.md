---
name: pipeline-report
description: Aggregate the deal notes into a forecast readout — totals, weighted value, coverage, slippage, deals at risk.
---

# PIPELINE REPORT

`PIPELINE REPORT [slice?]` — with no slice, the whole open pipeline. With a
slice (`at risk`, an account, a quarter), only what falls inside it.

## Sources

`notes/deals/*.md`. The frontmatter is the source of truth: `deal_id`,
`account`, `stage`, `stage_pct`, `amount`, `weighted`, `status`,
`expected_close`, `risk`, `qualification_score`.

Compute totals by reading every deal and summing. Do not estimate.

## Rules from the methodology

- Weighted value = `amount × stage_pct`. Prefer the stored `weighted`, but
  recompute and use the computed figure if the two disagree.
- **Commit** = stage probability ≥ 0.8 **and** qualification score ≥ 7 **and**
  the close date falls in the current quarter.
- **Best case** = stage probability ≥ 0.6 **and** qualification score ≥ 6 **and**
  the close date falls in the current quarter.
- A deal is slipped when its `expected_close` has passed and its status is still
  open.
- Quarterly quota: €1,000,000. Coverage = weighted open ÷ remaining quota.

## Output

1. **Forecast vs quota** — closed, commit, best case, each against quota.
2. **Coverage and slippage** — coverage ratio, number of slipped deals and value.
3. **Deals at risk** — count, total, and each one listed with its value.
4. **Breakdown** — value by account.
5. **One line in plain language** — do we make the number, and what is the
   single biggest lever.

## Rules

- **Report faithfully.** Where the data contradicts itself — a stage probability
  that does not match the stage, a missing close date, a stored weighted value
  that does not match the arithmetic — say so, by deal id. A clean total that
  hides a dirty record is worse than a dirty total that declares itself.
- Stay inside the requested slice. Do not volunteer the rest of the pipeline.
- Read only.
