# Note schema

Generated from `schema.py`. Do not edit by hand — edit the source and
regenerate with `python3 lint.py --emit-schema`.

## Required on every note

- `type`
- `created`
- `updated`
- `tags`

## Required by type

| Type | Additional required keys | Valid `status` |
|---|---|---|
| `account` | `name`, `owner`, `status` | `active`, `churned`, `dormant` |
| `deal` | `deal_id`, `account`, `amount`, `stage_pct`, `status`, `expected_close` | `lost`, `open`, `won` |
| `decision` | `status` | `accepted`, `proposed`, `superseded` |
| `meeting` | `date`, `account` | `cancelled`, `held` |
| `meta` | — | — |

## Deal stages

| Stage | Probability |
|---|---|
| `lead` | 10% |
| `discovery` | 20% |
| `solution-fit` | 40% |
| `proposal` | 60% |
| `negotiation` | 80% |
| `closed-won` | 100% |
| `closed-lost` | 0% |

## Staleness

An open note untouched for more than **42 days** is reported.
