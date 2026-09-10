#!/usr/bin/env python3
"""
oracle.py — compute the right answer instead of writing it down.

For anything that produces numbers there is a stronger check than comparing
against expected values: **a second, independent implementation of the same
arithmetic**. This reads the deal frontmatter of a fixture and recomputes
totals, weighted value, coverage, commit and best case, slippage, and the
places where the records contradict themselves.

Why not hardcode expected numbers in the case file:

  1. Change the fixture and the expectation follows. A copied number ages
     silently and the suite starts measuring the past.
  2. It forces the rules (commit = 80%+ and score >= 7 and closing this
     quarter) to exist as executable code rather than as prose inside a
     prompt. If the two implementations disagree, one of them is wrong, and
     finding that out is the point.
  3. It makes "the model got the total wrong" falsifiable: you know by how much.

The oracle is not ground truth. It is a second opinion written in a language
that does not hallucinate.

Standard library only.
"""

import datetime as dt
import glob
import os
import re
import sys

# Mirrors the rules stated in skills/pipeline-report/SKILL.md. Deliberately
# duplicated: the skill states them in English for a model, this states them
# in Python for a machine, and the eval is what keeps the two honest.
COMMIT_MIN_PCT, COMMIT_MIN_SCORE = 0.8, 7
BESTCASE_MIN_PCT, BESTCASE_MIN_SCORE = 0.6, 6
QUARTER_QUOTA = 1_000_000

STAGE_PCT = {"lead": 0.1, "discovery": 0.2, "solution-fit": 0.4,
             "proposal": 0.6, "negotiation": 0.8,
             "closed-won": 1.0, "closed-lost": 0.0}


def read_frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith(" ") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.split("  #")[0].strip().strip('"').strip("'")
    return fm


def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _date(v):
    try:
        return dt.date.fromisoformat(str(v).strip())
    except (TypeError, ValueError):
        return None


def compute(vault, today):
    today = _date(today) or dt.date.today()
    quarter = (today.month - 1) // 3 + 1

    deals = []
    for path in sorted(glob.glob(os.path.join(vault, "notes", "deals", "*.md"))):
        fm = read_frontmatter(path)
        if not fm.get("deal_id"):
            continue
        fm["_amount"] = _num(fm.get("amount"))
        fm["_pct"] = _num(fm.get("stage_pct"))
        fm["_weighted_stored"] = _num(fm.get("weighted"))
        fm["_weighted"] = round(fm["_amount"] * fm["_pct"], 2)
        fm["_close"] = _date(fm.get("expected_close"))
        fm["_score"] = int(_num(fm.get("qualification_score")))
        fm["_open"] = (fm.get("status") or "open").strip().lower() == "open"
        deals.append(fm)

    open_deals = [d for d in deals if d["_open"]]
    won = [d for d in deals if (d.get("status") or "").lower() == "won"]

    def this_quarter(d):
        return (d["_close"] is not None
                and d["_close"].year == today.year
                and (d["_close"].month - 1) // 3 + 1 == quarter)

    commit = [d for d in open_deals if this_quarter(d)
              and d["_pct"] >= COMMIT_MIN_PCT and d["_score"] >= COMMIT_MIN_SCORE]
    best = [d for d in open_deals if this_quarter(d)
            and d["_pct"] >= BESTCASE_MIN_PCT and d["_score"] >= BESTCASE_MIN_SCORE]
    slipped = [d for d in open_deals if d["_close"] and d["_close"] < today]
    at_risk = [d for d in open_deals
               if (d.get("risk") or "").strip().lower() in ("at risk", "at-risk", "high")]

    def total(ds, key="_amount"):
        return round(sum(d[key] for d in ds), 2)

    closed_q = total([d for d in won if this_quarter(d)])
    weighted_open = total(open_deals, "_weighted")
    remaining = max(QUARTER_QUOTA - closed_q, 0)

    by_account = {}
    for d in open_deals:
        k = (d.get("account") or "—").strip()
        by_account[k] = round(by_account.get(k, 0) + d["_amount"], 2)

    return {
        "today": today.isoformat(),
        "quarter": quarter,
        "n_open": len(open_deals),
        "open_total": total(open_deals),
        "weighted_open": weighted_open,
        "quarter_quota": QUARTER_QUOTA,
        "closed_this_quarter": closed_q,
        "commit_total": total(commit),
        "commit_ids": [d["deal_id"] for d in commit],
        "best_case_total": total(best),
        "best_case_ids": [d["deal_id"] for d in best],
        "coverage": round(weighted_open / remaining, 2) if remaining else None,
        "n_slipped": len(slipped),
        "slipped_total": total(slipped),
        "slipped_ids": [d["deal_id"] for d in slipped],
        "n_at_risk": len(at_risk),
        "at_risk_total": total(at_risk),
        "at_risk_ids": [d["deal_id"] for d in at_risk],
        "amounts_by_id": {d["deal_id"]: d["_amount"] for d in open_deals},
        "by_account": dict(sorted(by_account.items(), key=lambda kv: -kv[1])),
        "inconsistencies": inconsistencies(open_deals, this_quarter),
    }


def inconsistencies(open_deals, this_quarter):
    """Defects the report must declare rather than tidy away.

    A clean total reached by ignoring a deal whose stage probability does not
    match its stage is worse than a dirty total that says so: the first one
    cannot be seen.
    """
    out = []
    for d in open_deals:
        did, stage = d["deal_id"], (d.get("stage") or "").strip().lower()
        expected = STAGE_PCT.get(stage)
        if expected is not None and abs(d["_pct"] - expected) > 0.001:
            out.append({"deal_id": did, "kind": "stage_pct_mismatch",
                        "detail": f"stage {stage} implies {expected}, record says {d['_pct']}"})
        if abs(d["_weighted_stored"] - d["_weighted"]) > 1:
            out.append({"deal_id": did, "kind": "weighted_drift",
                        "detail": f"stored {d['_weighted_stored']:.0f}, "
                                  f"amount x stage_pct = {d['_weighted']:.0f}"})
        if not d.get("expected_close"):
            out.append({"deal_id": did, "kind": "missing_close_date",
                        "detail": "expected_close is empty"})
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(compute(sys.argv[1],
                             sys.argv[2] if len(sys.argv) > 2 else None),
                     indent=2))
