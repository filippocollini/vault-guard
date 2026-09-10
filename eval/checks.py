#!/usr/bin/env python3
"""
checks.py — assertions about a model's output, grouped by class.

The grouping is the point of this file, not an organising convenience. It
follows the same rule as ../lint.py:

    what can be verified mechanically is not sent to a model to verify.

    STRUCTURE   the promised shape is there        -> parsing, free, exact
    GROUNDING   claims trace to the source, and
                inventions do not appear           -> string work, free, exact
    ORACLE      the numbers are the ones the data
                actually produces                  -> recomputation, free, exact
    JUDGEMENT   the reasoning is right             -> a second model (judge.py)

The first three run offline, cost nothing, and return the same answer every
time. The fourth is kept as small as possible and never fails the suite.

Standard library only.
"""

import re
import unicodedata

DIMENSIONS = {
    "metrics": ["metrics"],
    "economic_buyer": ["economic buyer", "economic-buyer"],
    "decision_criteria": ["decision criteria"],
    "decision_process": ["decision process"],
    "paper_process": ["paper process"],
    "identify_pain": ["identify pain", "pain"],
    "champion": ["champion"],
    "competition": ["competition"],
}

# How a model writes "we do not know". If a cell matches one of these, the
# dimension counts as declared-uncovered — which is what we want to verify,
# mechanically, rather than asking a model whether the model was honest.
UNKNOWN_MARKERS = [
    "gap", "unknown", "empty", "not confirmed", "unconfirmed", "not identified",
    "not documented", "not established", "not known", "missing", "absent",
    "none on file", "no data", "nothing", "no one", "tbd", "n/a", "not met",
    "to be confirmed",
]
# "?" used to be on that list. It is far too loose: a cell that ends in a
# genuine question ("...but is the board step a formality?") was read as
# declaring the dimension uncovered. A punctuation mark is not a vocabulary.

INFERENCE_MARKERS = ["inferred", "assumed", "implied", "unconfirmed",
                     "not confirmed", "to verify", "unverified"]

# "No critical gaps" written as a bullet states zero, it is not itself a gap.
# The filter must stay narrow: an early version dropped any line starting with
# "no", which swallowed "No champion identified — Sollner has no budget".
# That is a gap, not the absence of one. See selftest.py.
NO_ITEM_RE = re.compile(
    r"^(no|none|zero|not any)\s+(critical\s+)?(gaps?|issues?|blockers?|items?|concerns?)\b"
)
NO_ITEM_BARE = {"none", "n/a", "nil", "-", "--", "—"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def number_variants(n):
    """Forms a number can legitimately take in prose.

    1878000 -> 1878000 | 1,878,000 | 1.878.000 | 1 878 000
             | 1878k | 1,878k | 1.878k | 1878.0k
             | 1.9m | 1,9m | 1.88m

    The k and M suffixes matter more than they look. A real forecast readout
    writes "EUR 1,878k" and "EUR 1.0M", and an earlier version of this
    function produced only a bare "1878k" — so entirely correct figures were
    reported missing, six times in one case. A suite that cries wolf on
    formatting stops being read, which costs more than the check is worth.
    """
    n = int(n)
    out = {str(n)}
    for sep in (",", ".", " ", "\u00a0", "'"):
        out.add(f"{n:,}".replace(",", sep))

    if n >= 1000:
        k = n / 1000
        forms = {f"{k:.1f}", f"{k:.2f}".rstrip("0").rstrip(".")}
        if k.is_integer():
            forms.add(str(int(k)))
        for form in forms:
            whole, _, frac = form.partition(".")
            for sep in ("", ",", ".", " "):
                grouped = whole if not sep else f"{int(whole):,}".replace(",", sep)
                if frac:
                    out.add(f"{grouped}.{frac}k")
                    out.add(f"{grouped},{frac}k")
                else:
                    out.add(f"{grouped}k")

    if n >= 100_000:
        for d in (1, 2):
            m = f"{n / 1_000_000:.{d}f}"
            for form in (m, m.rstrip("0").rstrip(".")):
                out.add(form + "m")
                out.add(form.replace(".", ",") + "m")
    return {norm(v) for v in out}


def contains_number(hay, variants):
    """Is one of these numeric forms present *as a number*?

    Plain substring matching is wrong here and selftest.py proved it: a
    coverage ratio of 1.9 was found inside the total "1,331,900", so a readout
    quoting the wrong coverage passed. Digits have to be bounded — not
    adjacent to another digit, and not sitting inside a grouped number.
    """
    for v in variants:
        if re.search(r"(?<!\d)(?<![\d][.,'\s])" + re.escape(v) + r"(?!\d)(?![.,'\s]\d)", hay):
            return True
    return False


def ratio_variants(x):
    out = set()
    for d in (1, 2):
        s = f"{x:.{d}f}"
        out.update({s, s.replace(".", ",")})
    out.update({f"{x:.0%}", f"{x:.0%}".replace("%", " %")})
    return {norm(v) for v in out}


# ------------------------------------------------------------------- parsing

def parse_table(text):
    """{dimension: {"state": ..., "full": ...}} from the qualification table.

    The two are kept apart because conflating them was wrong. A three-column
    table puts the verdict in column two and the evidence in column three, and
    joining them meant a perfectly well-filled row failed its check because
    the *evidence* prose happened to contain the word "gap" ("...but see gap
    below"). The verdict lives in the state column; the prose is context.

    With only two columns there is no separation to make, so state is the
    whole cell.
    """
    found = {}
    for line in text.splitlines():
        if line.count("|") < 2:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = norm(re.sub(r"[*_`]", "", cells[0]))
        for key, aliases in DIMENSIONS.items():
            if key not in found and any(label == a or label.startswith(a) for a in aliases):
                found[key] = {"state": cells[1].strip(),
                              "full": " ".join(cells[1:]).strip()}
    return found


def cell_state(table, dim):
    """The verdict for a dimension, without the supporting prose."""
    entry = table.get(dim)
    return norm(entry["state"]) if entry else ""


def cell_full(table, dim):
    entry = table.get(dim)
    return norm(entry["full"]) if entry else ""


def parse_section(text, *titles):
    """Bullets under a section, found by heading or bold label."""
    keys = [norm(t) for t in titles]
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        bare = norm(re.sub(r"[#*_`:\-]", " ", line))
        if any(bare.startswith(k) for k in keys):
            start = i + 1
            break
    if start is None:
        return None
    bullets, blanks = [], 0
    for line in lines[start:]:
        s = line.strip()
        if not s:
            blanks += 1
            if blanks >= 2 and bullets:
                break
            continue
        if re.match(r"^#{1,6}\s", s):
            break
        if re.match(r"^\*\*[^*]+\*\*:?$", s) and bullets:
            break
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            bullets.append(re.sub(r"^([-*+]|\d+[.)])\s+", "", s))
        blanks = 0
    return bullets


def is_no_item_line(bullet):
    n = norm(re.sub(r"[*_`.]", "", bullet)).strip()
    return n in NO_ITEM_BARE or bool(NO_ITEM_RE.match(n))


def real_items(bullets):
    return None if bullets is None else [b for b in bullets if not is_no_item_line(b)]


def _r(cls, name, passed, detail=""):
    return {"class": cls, "check": name, "pass": passed, "detail": detail}


# ----------------------------------------------------------------- structure

def check_structure(text, spec):
    out = []
    st = spec.get("structure", {})

    if st.get("qualification_table"):
        table = parse_table(text)
        missing = [k for k in DIMENSIONS if k not in table]
        out.append(_r("structure", "all-eight-dimensions", not missing,
                      "present" if not missing else f"missing: {', '.join(missing)}"))
        empty = [k for k in table if not cell_full(table, k)]
        out.append(_r("structure", "no-empty-cells", not empty,
                      "every dimension has content" if not empty
                      else f"empty: {', '.join(empty)}"))

    for title in st.get("required_sections", []):
        ok = norm(title) in norm(text)
        out.append(_r("structure", f"section «{title}»", ok, "present" if ok else "absent"))

    gaps = real_items(parse_section(text, "critical gaps", "gaps"))
    actions = real_items(parse_section(text, "action per gap", "actions", "next actions"))
    # Some outputs put the action directly under its gap rather than in a
    # section of their own. That satisfies "one action per gap" perfectly
    # well; only a checker that confuses layout with substance objects.
    inline = re.findall(r"(?im)^\s*(?:[-*+]\s*)?\*\*action[^:*]*:?\*\*:?\s*(.+)$", text)
    if inline and (actions is None or len(inline) > len(actions)):
        actions = inline

    if st.get("gaps_and_actions"):
        out.append(_r("structure", "gaps-section", gaps is not None,
                      f"{len(gaps)} real gaps" if gaps is not None else "section absent"))
        out.append(_r("structure", "actions-section", actions is not None,
                      f"{len(actions)} actions" if actions is not None else "section absent"))
        if gaps is not None and actions is not None:
            out.append(_r("structure", "one-action-per-gap", len(actions) == len(gaps),
                          f"{len(gaps)} gaps / {len(actions)} actions"))
            ownerless = [a for a in actions
                         if not re.search(r"\(([^)]{2,40})\)|owner\s*:", a, re.I)]
            out.append(_r("structure", "actions-have-owners", not ownerless,
                          "all owned" if not ownerless else f"{len(ownerless)} without an owner"))

    # The upper bound is the assertion that catches a model inventing problems
    # on a healthy record to look useful.
    if gaps is not None and "max_gaps" in st:
        out.append(_r("structure", f"at-most-{st['max_gaps']}-gaps",
                      len(gaps) <= st["max_gaps"], f"{len(gaps)} declared"))
    if gaps is not None and "min_gaps" in st:
        out.append(_r("structure", f"at-least-{st['min_gaps']}-gaps",
                      len(gaps) >= st["min_gaps"], f"{len(gaps)} declared"))
    if "max_words" in st:
        n = len(text.split())
        out.append(_r("structure", f"at-most-{st['max_words']}-words",
                      n <= st["max_words"], f"{n} words"))
    return out


# ----------------------------------------------------------------- grounding

def check_grounding(text, spec):
    """Does the output trace to the source, and stay clear of what is not there?

    The second half is the one that matters. It measures invention, which is
    how these systems fail silently: a hallucinated output is perfectly formed.
    """
    out = []
    hay = norm(text)
    g = spec.get("grounding", {})

    for item in g.get("must_cite", []):
        if isinstance(item, dict) and "number" in item:
            ok = contains_number(hay, number_variants(item["number"]))
            label = f"cites {item['number']}"
        else:
            ok = norm(item) in hay
            label = f"cites «{item}»"
        out.append(_r("grounding", label, ok, "present" if ok else "absent"))

    for item in g.get("must_absent", []):
        ok = norm(item) not in hay
        out.append(_r("grounding", f"does not invent «{item}»", ok,
                      "absent, correct" if ok else "PRESENT but not in the source"))

    table = parse_table(text)
    for dim in g.get("must_flag_unknown", []):
        cell = cell_state(table, dim)
        ok = bool(cell) and any(m in cell for m in UNKNOWN_MARKERS)
        out.append(_r("grounding", f"{dim} declared uncovered", ok,
                      f"«{cell[:70]}»" if cell else "row absent"))

    for dim in g.get("must_be_filled", []):
        cell = cell_state(table, dim)
        ok = bool(cell) and not any(m in cell for m in UNKNOWN_MARKERS)
        out.append(_r("grounding", f"{dim} filled", ok,
                      f"«{cell[:70]}»" if cell else "row absent"))

    for dim in g.get("must_mark_inferred", []):
        cell = cell_full(table, dim)
        ok = any(m in cell for m in INFERENCE_MARKERS)
        out.append(_r("grounding", f"{dim} marked inferred", ok,
                      f"«{cell[:70]}»" if cell else "row absent"))

    for pat in g.get("must_match", []):
        ok = re.search(pat, text, re.I | re.S) is not None
        out.append(_r("grounding", f"pattern /{pat[:40]}/", ok, "found" if ok else "not found"))
    return out


# -------------------------------------------------------------------- oracle

def check_oracle(text, spec, facts):
    """Compare the output's numbers with numbers recomputed from the fixture.

    oracle.py is a second, independent implementation of the same arithmetic.
    This does not check that the model wrote the number we expected to read:
    it checks that the model wrote the number the data produces. Change the
    fixture and the expectation follows.
    """
    out = []
    hay = norm(text)
    o = spec.get("oracle", {})

    for key in o.get("must_cite", []):
        val = facts.get(key)
        if val is None:
            out.append(_r("oracle", key, False, "key absent from the oracle"))
            continue
        variants = (ratio_variants(val) if isinstance(val, float) and not val.is_integer()
                    else number_variants(int(val)))
        ok = contains_number(hay, variants)
        out.append(_r("oracle", f"{key} = {val:g}", ok,
                      "cited" if ok else f"none of {sorted(variants)[:4]} appears"))

    # An identifier appearing "somewhere" does not prove the deal was listed
    # where it needed to be: an early version passed because a deal dropped
    # from the at-risk list was still named in a data-quality footnote. It has
    # to appear next to its own value, which is what listing a deal means.
    amounts = facts.get("amounts_by_id") or {}
    for key in o.get("must_list_ids", []):
        ids, missing = facts.get(key) or [], []
        for i in ids:
            positions = [m.start() for m in re.finditer(re.escape(norm(i)), hay)]
            variants = number_variants(int(amounts[i])) if i in amounts else set()
            listed = (any(contains_number(hay[max(0, p - 160):p + 160], variants)
                          for p in positions) if variants else bool(positions))
            if not listed:
                missing.append(i)
        out.append(_r("oracle", f"{key} ({len(ids)}) listed with their value", not missing,
                      "all listed" if not missing else f"not listed with a value: {', '.join(missing)}"))

    for key in o.get("must_not_list_ids", []):
        leaked = [i for i in (facts.get(key) or []) if norm(i) in hay]
        out.append(_r("oracle", f"out of scope: {key}", not leaked,
                      "no leakage" if not leaked
                      else f"appear outside the requested slice: {', '.join(leaked)}"))

    if o.get("must_flag_inconsistencies"):
        bad = sorted({i["deal_id"] for i in facts.get("inconsistencies", [])})
        missing = [i for i in bad if norm(i) not in hay]
        out.append(_r("oracle", f"flags inconsistent deals ({len(bad)})", not missing,
                      "all named" if not missing
                      else f"not named: {', '.join(missing)} — washed out of the report"))

    for bad in o.get("must_not_cite_numbers", []):
        ok = not contains_number(hay, number_variants(int(bad)))
        out.append(_r("oracle", f"does not cite {bad}", ok,
                      "absent, correct" if ok else "PRESENT — not a number in the data"))
    return out


def read_frontmatter_text(text):
    """Flat frontmatter from an already-read string (used by statecheck.py)."""
    m = re.match(r"^---\n(.*?)\n---", text or "", re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith(" ") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.split("  #")[0].strip().strip('"').strip("'")
    return fm
