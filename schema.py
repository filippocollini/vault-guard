#!/usr/bin/env python3
"""
schema.py — the single source of truth for what a note must contain.

This file exists because the schema was previously written down in three
places: the linter, the note templates, and the documentation. They drifted.
By the time anyone noticed, each one described a slightly different vault and
none of them was right.

Everything downstream now reads from here. `lint.py --emit-schema` regenerates
the human-readable documentation from these tables, so the docs cannot fall
behind the code: they are the code, printed.

Standard library only.
"""

# Every note, regardless of type, carries these.
REQUIRED_ALL = ["type", "created", "updated", "tags"]

# Additional keys required per type.
REQUIRED_BY_TYPE = {
    "account": ["name", "owner", "status"],
    "deal": ["deal_id", "account", "amount", "stage_pct", "status", "expected_close"],
    "meeting": ["date", "account"],
    "decision": ["status"],
    "meta": [],
}

# `status` is LIFECYCLE — where a thing is in its progression.
# `maturity` is CONFIDENCE — how finished the page itself is.
#
# These were once the same key. On a vault of a few hundred notes that
# conflation silently lost one of the two meanings on every page that needed
# both: a fully-written page about an early-stage deal, or a stub about a
# closed one, could not be expressed.
STATUS_BY_TYPE = {
    "account": {"active", "dormant", "churned"},
    "deal": {"open", "won", "lost"},
    "decision": {"proposed", "accepted", "superseded"},
    "meeting": {"held", "cancelled"},
}

MATURITY = {"stub", "developing", "mature", "evergreen"}

# Deal stages and the probability each carries. The linter checks that a
# deal's stored stage_pct matches its stage rather than trusting either.
STAGES = {
    "lead": 0.1,
    "discovery": 0.2,
    "solution-fit": 0.4,
    "proposal": 0.6,
    "negotiation": 0.8,
    "closed-won": 1.0,
    "closed-lost": 0.0,
}

# A note whose `updated` is older than this, while its status is still open,
# is reported as stale. Not an error: an open thing nobody has touched in six
# weeks is a fact about the vault worth surfacing, not a mistake.
STALE_DAYS = 42


def emit_markdown():
    """Render the schema as documentation. Called by `lint.py --emit-schema`."""
    L = ["# Note schema", "",
         "Generated from `schema.py`. Do not edit by hand — edit the source and",
         "regenerate with `python3 lint.py --emit-schema`.", "",
         "## Required on every note", "",
         "".join(f"- `{k}`\n" for k in REQUIRED_ALL),
         "## Required by type", "",
         "| Type | Additional required keys | Valid `status` |", "|---|---|---|"]
    for t in sorted(REQUIRED_BY_TYPE):
        extra = ", ".join(f"`{k}`" for k in REQUIRED_BY_TYPE[t]) or "—"
        st = ", ".join(f"`{s}`" for s in sorted(STATUS_BY_TYPE.get(t, []))) or "—"
        L.append(f"| `{t}` | {extra} | {st} |")
    L += ["", "## Deal stages", "", "| Stage | Probability |", "|---|---|"]
    L += [f"| `{s}` | {p:.0%} |" for s, p in STAGES.items()]
    L += ["", f"## Staleness", "",
          f"An open note untouched for more than **{STALE_DAYS} days** is reported."]
    return "\n".join(L) + "\n"
