#!/usr/bin/env python3
"""
selftest.py — who checks the checks.

An evaluation suite has a quiet way of being useless: **passing always.** If
the assertions are written loosely the report is green whatever comes out, and
the suite becomes a ritual instead of a measurement — with the aggravating
detail that it inspires confidence while measuring nothing.

This file rules that out. For each class of assertion it takes a correct
output, breaks it in ways that correspond one-to-one with the failures the
suite is supposed to catch, and verifies that each break lights up the right
check. A mutation that slips through means the corresponding assertion earns
nothing and should be rewritten.

It calls no model, runs in about a second, and belongs in CI.

Three suites: text assertions, arithmetic, vault state.

    python3 eval/selftest.py
"""

import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import checks as C      # noqa: E402
import oracle           # noqa: E402
import statecheck       # noqa: E402

CASES = os.path.join(HERE, "cases")


def load_spec(case):
    with open(os.path.join(CASES, case, "case.json"), encoding="utf-8") as fh:
        return json.load(fh)["checks"]


def banner(title):
    print("\n" + "-" * 70 + f"\n{title}\n" + "-" * 70)


# ==========================================================================
# SUITE 1 — text assertions
# ==========================================================================

GOOD_REVIEW = """
## Northwind Marine — qualification

| Dimension | State | Source / note |
|---|---|---|
| **M**etrics | Partial — €195,000 over 12 months on the Kalmar tranche (300 gateways at €650); three sites still uncounted | account note; see gap 1 below |
| **E**conomic Buyer | **Gap** — never met. M. Falk named for signature, no contact of any kind | frontmatter empty |
| **D**ecision Criteria | Support continuity plus commercial terms — inferred, not confirmed | 18 June call |
| **D**ecision Process | Unknown — no steps and no dates on record | — |
| **P**aper Process | Unknown — legal and security review timing never discussed | — |
| **I**dentify Pain | End of support March 2027 against maintenance contracted to 2029 | 18 June call, in writing |
| **C**hampion | Not identified — Sollner is the technical contact and states she has no budget | 18 June call |
| **C**ompetition | No competitor named by the customer in any interaction | — |

**Critical gaps**

1. Economic buyer never met on €780,000 at negotiation stage — we are trading terms without knowing who signs.
2. No champion: Sollner does not carry the case when we are absent.
3. Decision process and paper process unknown two months before the expected close.

**Action per gap**

- Ask Sollner for an introduction to Falk this week, justified by the end-of-support date (A. Ferrand)
- Offer to build the internal business case for all four sites with Sollner (A. Ferrand)
- Map legal and procurement dates on the next call, anchored to the 15 December close (A. Ferrand)
"""

REVIEW_MUTATIONS = {
    "papers_over_the_gap": (
        lambda t: t.replace(
            "| **E**conomic Buyer | **Gap** — never met. M. Falk named for signature, no contact of any kind | frontmatter empty |",
            "| **E**conomic Buyer | M. Falk, procurement | account note |"),
        "economic_buyer declared uncovered"),
    "promotes_the_engineer": (
        lambda t: t.replace(
            "| **C**hampion | Not identified — Sollner is the technical contact and states she has no budget | 18 June call |",
            "| **C**hampion | Ingrid Sollner, OT manager | 18 June call |"),
        "champion declared uncovered"),
    "invents_a_competitor": (
        lambda t: t.replace(
            "| **C**ompetition | No competitor named by the customer in any interaction | — |",
            "| **C**ompetition | Competing against Claroty | — |"),
        "does not invent «Claroty»"),
    "drops_the_actions": (
        lambda t: t.split("**Action per gap**")[0],
        "actions-section"),
    "actions_without_owners": (
        lambda t: t.replace(" (A. Ferrand)", ""),
        "actions-have-owners"),
    "wrong_amount": (
        lambda t: t.replace("€195,000", "€400,000"),
        "cites 195000"),
    "drops_a_dimension": (
        lambda t: "\n".join(l for l in t.splitlines() if "**P**aper Process" not in l),
        "all-eight-dimensions"),
    "declares_no_gaps": (
        lambda t: re.sub(r"\*\*Critical gaps\*\*.*?\*\*Action per gap\*\*",
                         "**Critical gaps**\n\n- None\n\n**Action per gap**", t, flags=re.S),
        "at-least-2-gaps"),
}

# The filter that decides whether a bullet is an item or a statement that there
# are none has already been wrong once: it discarded "No champion identified",
# treating a serious gap as a declaration of absence. It has had its own cases
# ever since.
ITEM_LINES = [
    ("No critical gaps",                                  False),
    ("None",                                              False),
    ("No issues",                                         False),
    ("no blockers",                                       False),
    ("No champion identified — Sollner has no budget",    True),
    ("No decision process on record",                     True),
    ("Economic buyer never met on €780,000",              True),
]


# Two properties the state/prose split and the marker vocabulary have to hold.
# Both come from real failures: a filled row was rejected because its evidence
# column said "see gap below", and a row whose verdict was literally "Empty"
# was not recognised as declaring the dimension uncovered.
VERDICT_CASES = [
    ("| **E**conomic Buyer | Empty | nobody identified |", "economic_buyer", "uncovered"),
    ("| **E**conomic Buyer | Unconfirmed | a name circulates |", "economic_buyer", "uncovered"),
    ("| **E**conomic Buyer | Strong | Reuter, COO — but see gap 2 below |", "economic_buyer", "filled"),
    ("| **C**hampion | Not identified | technical contact only |", "champion", "uncovered"),
    ("| **C**hampion | Strong | Muraro, Head of Service |", "champion", "filled"),
]


def suite_verdicts():
    problems = []
    bad = 0
    for row, dim, expected in VERDICT_CASES:
        table = C.parse_table(row)
        state = C.cell_state(table, dim)
        uncovered = bool(state) and any(m in state for m in C.UNKNOWN_MARKERS)
        got = "uncovered" if uncovered else "filled"
        if got != expected:
            bad += 1
            problems.append(f"VERDICT — {row.strip()} read as {got}, expected {expected}")
    print(f"verdict column: {len(VERDICT_CASES) - bad}/{len(VERDICT_CASES)} rows read correctly")
    return problems


def suite_text():
    banner("suite 1 — text assertions")
    problems = []

    bad = [f"«{line}» classified as {'item' if not C.is_no_item_line(line) else 'absence'}"
           for line, is_item in ITEM_LINES
           if (not C.is_no_item_line(line)) != is_item]
    print(f"item filter: {len(ITEM_LINES) - len(bad)}/{len(ITEM_LINES)} lines classified correctly")
    problems += [f"ITEM FILTER — {b}" for b in bad]
    problems += suite_verdicts()

    spec = load_spec("01-unconfirmed-buyer")

    def run(text):
        return C.check_structure(text, spec) + C.check_grounding(text, spec)

    base = run(GOOD_REVIEW)
    for r in base:
        if not r["pass"]:
            problems.append(f"FALSE POSITIVE — the correct output fails «{r['check']}»: {r['detail']}")
    print(f"reference output: {sum(1 for r in base if r['pass'])}/{len(base)} assertions passed\n")

    for name, (breaker, expected) in REVIEW_MUTATIONS.items():
        failed = {r["check"] for r in run(breaker(GOOD_REVIEW)) if not r["pass"]}
        caught = any(expected in f for f in failed)
        print(f"  {'caught ' if caught else 'MISSED '}  {name:24s} -> expected «{expected}»")
        if not caught:
            problems.append(f"FALSE NEGATIVE — «{name}» does not trip «{expected}». "
                            f"Failed instead: {sorted(failed) or 'nothing'}")
    return problems


# ==========================================================================
# SUITE 2 — arithmetic
# ==========================================================================

# Worked by hand from the fixture, independently of oracle.py. Where the two
# disagree one of them is wrong, and that is the point of writing both.
#   open:     780+410+23+160+90+250+120+45          = 1,878,000
#   weighted: 624+328+6.9+96+54+100+96+27           = 1,331,900
#   commit (>=0.8 pct, >=7 score, closing in Q3):
#             D-201 780,000 + D-202 410,000         = 1,190,000
#   coverage: 1,331,900 / (1,000,000 - 300,000 won) = 1.9
BY_HAND = {
    "open_total": 1_878_000, "weighted_open": 1_331_900,
    "commit_total": 1_190_000, "best_case_total": 1_350_000,
    "coverage": 1.9, "n_slipped": 1, "slipped_total": 90_000,
    "n_at_risk": 2, "at_risk_total": 340_000, "closed_this_quarter": 300_000,
}

GOOD_PIPELINE = """
## 1 — Forecast vs quota (Q3)
Closed 300,000 against a quota of 1,000,000. Commit 1,190,000 (D-201, D-202).
Best case 1,350,000. Amber.

## 2 — Coverage and slippage
Open pipeline 1,878,000, weighted 1,331,900. Coverage 1.9 against the remainder.
1 deal slipped, worth 90,000: D-205, due 15 August.

## 3 — Deals at risk
2 deals, 340,000 in total: D-205 (90,000) and D-206 (250,000).

## 4 — Breakdown by account
Northwind Marine 780,000 · Verta Robotics 410,000 · Talvik Steel 250,000.

## 5 — In one line
The quarter closes if D-201 signs; on its own it exceeds the remaining quota.
Caveat: D-203 has a stage probability that does not match its stage, D-206
stores a weighted value that does not match the arithmetic, and D-208 has no
close date. The totals above include all three exactly as recorded.
"""

PIPELINE_MUTATIONS = {
    "wrong_total": (lambda t: t.replace("1,878,000", "1,978,000"), "open_total"),
    "wrong_coverage": (lambda t: t.replace("Coverage 1.9", "Coverage 2.4"), "coverage"),
    "drops_an_at_risk_deal": (
        lambda t: t.replace("D-205 (90,000) and D-206 (250,000)", "D-206 (250,000)")
                   .replace("1 deal slipped, worth 90,000: D-205, due 15 August.", ""),
        "at_risk_ids"),
    "launders_the_records": (
        lambda t: t.split("Caveat:")[0] + "The totals above are reliable.\n",
        "flags inconsistent deals"),
    "invents_a_number": (
        lambda t: t.replace("Best case 1,350,000", "Best case 1,350,000 (upside 2,500,000)"),
        "does not cite 2500000"),
    "drops_a_section": (lambda t: t.replace("## 4 — Breakdown by account", "## 4 — Other"),
                        "section «Breakdown»"),
}


def suite_numbers():
    banner("suite 2 — arithmetic")
    problems = []

    facts = oracle.compute(os.path.join(CASES, "04-pipeline-arithmetic", "vault"), "2026-09-10")
    wrong = {k: (v, facts.get(k)) for k, v in BY_HAND.items() if facts.get(k) != v}
    print(f"oracle: {len(BY_HAND) - len(wrong)}/{len(BY_HAND)} values agree with the hand calculation")
    problems += [f"ORACLE — {k}: expected {e}, computed {g}" for k, (e, g) in wrong.items()]

    found = {i["deal_id"] for i in facts["inconsistencies"]}
    if found != {"D-203", "D-206", "D-208"}:
        problems.append(f"ORACLE — inconsistencies {sorted(found)}, expected D-203/D-206/D-208")
    else:
        print("oracle: 3/3 self-contradicting deals detected")

    spec = load_spec("04-pipeline-arithmetic")

    def run(text):
        return (C.check_structure(text, spec) + C.check_grounding(text, spec)
                + C.check_oracle(text, spec, facts))

    base = run(GOOD_PIPELINE)
    for r in base:
        if not r["pass"]:
            problems.append(f"FALSE POSITIVE — the correct readout fails «{r['check']}»: {r['detail']}")
    print(f"\nreference readout: {sum(1 for r in base if r['pass'])}/{len(base)} assertions passed\n")

    for name, (breaker, expected) in PIPELINE_MUTATIONS.items():
        failed = {r["check"] for r in run(breaker(GOOD_PIPELINE)) if not r["pass"]}
        caught = any(expected in f for f in failed)
        print(f"  {'caught ' if caught else 'MISSED '}  {name:24s} -> expected «{expected}»")
        if not caught:
            problems.append(f"FALSE NEGATIVE — «{name}» does not trip «{expected}». "
                            f"Failed instead: {sorted(failed) or 'nothing'}")
    return problems


# ==========================================================================
# SUITE 3 — vault state
# ==========================================================================

FIXTURE = os.path.join(CASES, "05-note-write", "vault")
ACCOUNT = "notes/accounts/brenner-mobility.md"
DEAL = "notes/deals/d-301-brenner-diagnostics.md"
OTHER = "notes/accounts/talvik-steel.md"

INTERACTIONS = """
## Interactions

### 2026-09-09 — call
- Anna Kofler (Head of Maintenance) will take the case to the October investment committee
- Luca Varesi asked whether the collector runs on ARM; check with the product team by Friday
- No close date agreed: it depends on the committee
"""

LOG_ENTRY = """## 2026-09-10 — Brenner Mobility call, Kofler steps forward
Kofler takes the case to the October committee. ARM support check opened.
"""


def _edit(path, fn):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(fn(text))


def _set(text, key, value):
    return re.sub(rf"^{re.escape(key)}:.*$", f"{key}: {value}", text, count=1, flags=re.M)


def build_good_vault():
    tmp = tempfile.mkdtemp(prefix="selftest-after-")
    shutil.copytree(FIXTURE, tmp, dirs_exist_ok=True)
    _edit(os.path.join(tmp, ACCOUNT), lambda t: _set(
        _set(t, "champion", '"Anna Kofler — Head of Maintenance"'),
        "updated", "2026-09-10") + INTERACTIONS)
    _edit(os.path.join(tmp, DEAL), lambda t: _set(
        _set(t, "next_action", '"Check ARM support for the collector with the product team"'),
        "updated", "2026-09-10")
        + "\n### 2026-09-09\n- Kofler to the October committee; ARM check opened\n")
    _edit(os.path.join(tmp, "log.md"),
          lambda t: t.replace("## 2026-08-30", LOG_ENTRY + "\n## 2026-08-30", 1))
    return tmp


STATE_MUTATIONS = {
    "collateral_damage": (
        lambda d: _edit(os.path.join(d, OTHER), lambda t: _set(t, "status", "dormant")),
        "other files left alone"),
    "advances_the_stage": (
        lambda d: _edit(os.path.join(d, DEAL), lambda t: _set(t, "stage", "negotiation")),
        "stage = UNCHANGED"),
    "invents_a_close_date": (
        lambda d: _edit(os.path.join(d, DEAL), lambda t: _set(t, "expected_close", "2026-10-31")),
        "expected_close = EMPTY"),
    "empty_next_action": (
        lambda d: _edit(os.path.join(d, DEAL), lambda t: _set(t, "next_action", '""')),
        "next_action = NONEMPTY"),
    "log_at_the_bottom": (
        lambda d: _edit(os.path.join(d, "log.md"),
                        lambda t: t.replace(LOG_ENTRY + "\n", "") + "\n" + LOG_ENTRY),
        "newest log entry is at the top"),
    "champion_not_recorded": (
        lambda d: _edit(os.path.join(d, ACCOUNT), lambda t: _set(t, "champion", '""')),
        "champion = Kofler"),
}


def suite_state():
    banner("suite 3 — vault state")
    problems = []
    spec = load_spec("05-note-write")
    good = build_good_vault()
    try:
        base = statecheck.check_state(FIXTURE, good, spec)
        for r in base:
            if not r["pass"]:
                problems.append(f"FALSE POSITIVE — the correct vault fails «{r['check']}»: {r['detail']}")
        print(f"reference vault: {sum(1 for r in base if r['pass'])}/{len(base)} assertions passed\n")

        for name, (breaker, expected) in STATE_MUTATIONS.items():
            broken = tempfile.mkdtemp(prefix="selftest-broken-")
            try:
                shutil.copytree(good, broken, dirs_exist_ok=True)
                breaker(broken)
                failed = {r["check"] for r in statecheck.check_state(FIXTURE, broken, spec)
                          if not r["pass"]}
                caught = any(expected in f for f in failed)
                print(f"  {'caught ' if caught else 'MISSED '}  {name:24s} -> expected «{expected}»")
                if not caught:
                    problems.append(f"FALSE NEGATIVE — «{name}» does not trip «{expected}». "
                                    f"Failed instead: {sorted(failed) or 'nothing'}")
            finally:
                shutil.rmtree(broken, ignore_errors=True)
    finally:
        shutil.rmtree(good, ignore_errors=True)
    return problems


def main():
    problems = suite_text() + suite_numbers() + suite_state()
    print()
    if problems:
        for p in problems:
            print("  ! " + p)
        print(f"\nSELFTEST FAILED — {len(problems)} problems in the assertions")
        return 1
    print("SELFTEST OK — every assertion tells a correct output from a broken one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
