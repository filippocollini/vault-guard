#!/usr/bin/env python3
"""
lint.py — deterministic checks over a markdown knowledge base.

Every check in this file is mechanical: it parses, compares, and reports.
None of them asks a language model anything, and that is deliberate — see
METHOD.md. Broken frontmatter, a dead link, a stage probability that does not
match its stage: these have exact answers, and a model would give you an
approximate one, slowly, for money, differently each time.

Properties worth keeping if you adapt this:

  * Reads the schema from schema.py. Nothing is duplicated here.
  * Never modifies a note. Writes a report and nothing else.
  * Takes `--today` so runs are reproducible. A check that depends on the
    wall clock cannot be tested.
  * Exits 1 on ERROR findings, so it works as a commit or CI gate.
  * Standard library only.

Usage:
    python3 lint.py demo-vault
    python3 lint.py demo-vault --report report.md --today 2026-09-10
    python3 lint.py --emit-schema > SCHEMA.md
"""

import argparse
import datetime as dt
import glob
import os
import re
import sys
from collections import defaultdict

import schema

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"


# --------------------------------------------------------------------------- io

def read_note(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith(" ") or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.split("  #")[0].strip().strip('"').strip("'")
    return fm, m.group(2)


def load(vault):
    notes = {}
    for path in glob.glob(os.path.join(vault, "**", "*.md"), recursive=True):
        rel = os.path.relpath(path, vault)
        fm, body = read_note(path)
        notes[rel] = {"path": path, "rel": rel, "fm": fm or {}, "body": body,
                      "has_fm": fm is not None,
                      "stem": os.path.splitext(os.path.basename(rel))[0]}
    return notes


def as_date(v):
    try:
        return dt.date.fromisoformat(str(v).strip())
    except (TypeError, ValueError):
        return None


def as_num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------- checks

def check_frontmatter(notes, ctx):
    out = []
    for n in notes.values():
        if not n["has_fm"]:
            out.append((ERROR, "frontmatter", n["rel"], "no frontmatter block"))
            continue
        fm = n["fm"]
        for key in schema.REQUIRED_ALL:
            if not fm.get(key):
                out.append((ERROR, "frontmatter", n["rel"], f"missing required key `{key}`"))
        t = fm.get("type", "")
        if t and t not in schema.REQUIRED_BY_TYPE:
            out.append((ERROR, "frontmatter", n["rel"], f"unknown type `{t}`"))
            continue
        for key in schema.REQUIRED_BY_TYPE.get(t, []):
            if not fm.get(key):
                out.append((ERROR, "frontmatter", n["rel"],
                            f"type `{t}` requires `{key}`"))
        st, allowed = fm.get("status"), schema.STATUS_BY_TYPE.get(t)
        if st and allowed and st not in allowed:
            out.append((ERROR, "frontmatter", n["rel"],
                        f"status `{st}` not valid for type `{t}` "
                        f"(expected one of {sorted(allowed)})"))
        mat = fm.get("maturity")
        if mat and mat not in schema.MATURITY:
            out.append((WARN, "frontmatter", n["rel"], f"unknown maturity `{mat}`"))
    return out


def check_dates(notes, ctx):
    out = []
    for n in notes.values():
        fm = n["fm"]
        created, updated = as_date(fm.get("created")), as_date(fm.get("updated"))
        for label, value in (("created", fm.get("created")), ("updated", fm.get("updated"))):
            if value and as_date(value) is None:
                out.append((ERROR, "dates", n["rel"], f"`{label}` is not a date: {value!r}"))
        if created and updated and updated < created:
            out.append((ERROR, "dates", n["rel"], f"updated {updated} precedes created {created}"))
        if updated and updated > ctx["today"]:
            out.append((WARN, "dates", n["rel"], f"updated {updated} is in the future"))
    return out


def check_links(notes, ctx):
    """Dead wikilinks, and pages nothing points at."""
    out = []
    stems = {n["stem"] for n in notes.values()}
    inbound = defaultdict(int)
    for n in notes.values():
        for target in re.findall(r"\[\[([^\]|#]+)", n["body"]):
            target = target.strip().split("/")[-1]
            if target in stems:
                inbound[target] += 1
            else:
                out.append((WARN, "links", n["rel"], f"dead wikilink `[[{target}]]`"))
    for n in notes.values():
        # Index and meta pages are entry points; nothing pointing at them is normal.
        if n["fm"].get("type") == "meta" or n["stem"].startswith("_"):
            continue
        if inbound[n["stem"]] == 0:
            out.append((INFO, "links", n["rel"], "orphan: no inbound wikilinks"))
    return out


def check_stages(notes, ctx):
    """A deal's stored probability must match its stage.

    Two fields encoding the same fact will disagree eventually. Recomputing
    is cheap; trusting whichever was edited last is how a forecast quietly
    becomes wrong.
    """
    out = []
    for n in notes.values():
        if n["fm"].get("type") != "deal":
            continue
        fm, rel = n["fm"], n["rel"]
        stage = (fm.get("stage") or "").strip().lower()
        pct, expected = as_num(fm.get("stage_pct")), schema.STAGES.get(stage)
        if stage and expected is None:
            out.append((ERROR, "pipeline", rel, f"unknown stage `{stage}`"))
        elif expected is not None and pct is not None and abs(pct - expected) > 0.001:
            out.append((ERROR, "pipeline", rel,
                        f"stage `{stage}` implies {expected}, stage_pct says {pct}"))
        amount = as_num(fm.get("amount"))
        weighted = as_num(fm.get("weighted"))
        if amount is not None and pct is not None and weighted is not None:
            if abs(weighted - amount * pct) > 1:
                out.append((ERROR, "pipeline", rel,
                            f"weighted {weighted:.0f} but amount x stage_pct = {amount * pct:.0f}"))
        if fm.get("status") == "lost" and not fm.get("lost_reason"):
            out.append((WARN, "pipeline", rel, "lost deal without `lost_reason`"))
        close = as_date(fm.get("expected_close"))
        if fm.get("status") == "open" and close and close < ctx["today"]:
            out.append((WARN, "pipeline", rel,
                        f"still open but expected_close {close} has passed"))
    return out


def check_reconciliation(notes, ctx):
    """Does the account layer agree with the deal layer?

    Each account states its open pipeline; each deal states its amount. Both
    numbers are maintained by hand in different places, so they diverge. This
    is the check that finds the divergence before someone quotes one of them
    in a meeting.
    """
    out = []
    per_account = defaultdict(float)
    for n in notes.values():
        fm = n["fm"]
        if fm.get("type") == "deal" and fm.get("status") == "open":
            per_account[(fm.get("account") or "").strip()] += as_num(fm.get("amount")) or 0.0
    for n in notes.values():
        fm = n["fm"]
        if fm.get("type") != "account":
            continue
        stated = as_num(fm.get("open_pipeline"))
        if stated is None:
            continue
        actual = per_account.get((fm.get("name") or "").strip(), 0.0)
        if abs(stated - actual) > 1:
            out.append((ERROR, "reconciliation", n["rel"],
                        f"account states {stated:.0f} open, deals sum to {actual:.0f} "
                        f"(difference {stated - actual:+.0f})"))
    return out


def check_staleness(notes, ctx):
    out = []
    for n in notes.values():
        fm = n["fm"]
        if fm.get("status") not in ("open", "active", "proposed"):
            continue
        updated = as_date(fm.get("updated"))
        if not updated:
            continue
        age = (ctx["today"] - updated).days
        if age > schema.STALE_DAYS:
            out.append((INFO, "staleness", n["rel"],
                        f"open for {age} days without an update"))
    return out


CHECKS = [check_frontmatter, check_dates, check_links,
          check_stages, check_reconciliation, check_staleness]


# ----------------------------------------------------------------------- report

def report(findings, vault, today, n_notes):
    by_sev = defaultdict(int)
    by_cat = defaultdict(lambda: defaultdict(int))
    for sev, cat, _, _ in findings:
        by_sev[sev] += 1
        by_cat[cat][sev] += 1
    L = [f"# Lint report — {vault}", "",
         f"{n_notes} notes · run for {today}", "",
         f"**{by_sev[ERROR]} ERROR · {by_sev[WARN]} WARN · {by_sev[INFO]} INFO**", "",
         "| Check | ERROR | WARN | INFO |", "|---|---|---|---|"]
    for cat in sorted(by_cat):
        c = by_cat[cat]
        L.append(f"| {cat} | {c[ERROR]} | {c[WARN]} | {c[INFO]} |")
    for sev in (ERROR, WARN, INFO):
        rows = [f for f in findings if f[0] == sev]
        if not rows:
            continue
        L += ["", f"## {sev} ({len(rows)})", ""]
        L += [f"- `{rel}` — {msg}" for _, _, rel, msg in sorted(rows, key=lambda r: r[2])]
    return "\n".join(L) + "\n", by_sev


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("vault", nargs="?", default="demo-vault")
    ap.add_argument("--report", default="", help="write the report to this file")
    ap.add_argument("--today", default=dt.date.today().isoformat(),
                    help="pin the date so runs are reproducible")
    ap.add_argument("--emit-schema", action="store_true",
                    help="print the schema documentation and exit")
    ap.add_argument("--max-errors", type=int, default=0,
                    help="tolerate this many ERROR findings before failing")
    args = ap.parse_args()

    if args.emit_schema:
        sys.stdout.write(schema.emit_markdown())
        return 0

    today = as_date(args.today)
    if today is None:
        print(f"--today is not a date: {args.today!r}", file=sys.stderr)
        return 2
    if not os.path.isdir(args.vault):
        print(f"no such vault: {args.vault}", file=sys.stderr)
        return 2

    notes = load(args.vault)
    ctx = {"today": today}
    findings = [f for check in CHECKS for f in check(notes, ctx)]
    text, by_sev = report(findings, args.vault, today, len(notes))

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"report written to {args.report}")
    else:
        sys.stdout.write(text)

    n_err = by_sev[ERROR]
    print(f"\n{n_err} ERROR · {by_sev[WARN]} WARN · {by_sev[INFO]} INFO", file=sys.stderr)
    return 1 if n_err > args.max_errors else 0


if __name__ == "__main__":
    sys.exit(main())
