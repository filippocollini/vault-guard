#!/usr/bin/env python3
"""
statecheck.py — assertions about what a skill *did*, not what it said.

`record-note` is the one skill here that writes. Grading its prose is
pointless: its product is the difference between the vault before and after.
That changes the object of measurement, so it changes the kind of assertion.

Two classes matter, and the second is the neglected one:

    WHAT MUST CHANGE       a field updated, a section created, a log entry
                           added at the top
    WHAT MUST NOT CHANGE   every other file, byte for byte

A skill that writes fails in two ways. It fails to do what it should, and you
notice immediately. Or it does something *else as well*: the requested note is
written correctly and meanwhile a line changes in an unrelated page. The
second one is silent. Under version control you find it at the next diff, if
someone reads the diff. Here you find it now, by comparing hashes with the
starting fixture.

Standard library only.
"""

import hashlib
import os
import re

from checks import _r, norm, read_frontmatter_text


def _walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".claude")]
        for name in filenames:
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, root), full


def snapshot(root):
    out = {}
    for rel, full in _walk(root):
        with open(full, "rb") as fh:
            out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _read(root, rel):
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _log_entries(text):
    """[(date, body)] for `## YYYY-MM-DD …` entries, in file order."""
    if not text:
        return []
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    out = []
    for part in re.split(r"(?m)^##\s+", body)[1:]:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", part.strip())
        out.append((m.group(1) if m else "", part))
    return out


def check_state(pristine, result, spec):
    out = []
    before, after = snapshot(pristine), snapshot(result)
    st = spec.get("state", {})

    for rel in st.get("files_created", []):
        ok = rel in after and rel not in before
        out.append(_r("state", f"created {rel}", ok,
                      "created" if ok else ("already existed" if rel in before else "not created")))

    for rel in st.get("files_modified", []):
        ok = rel in after and rel in before and before[rel] != after[rel]
        out.append(_r("state", f"modified {rel}", ok, "modified" if ok else "unchanged or missing"))

    # The most important assertion in this file. Without it a skill can touch
    # half the vault and still pass, because it also did the right thing.
    protected = st.get("files_untouched", [])
    if protected == "*":
        allowed = set(st.get("files_created", [])) | set(st.get("files_modified", []))
        protected = [rel for rel in before if rel not in allowed]
    touched = [rel for rel in protected if rel not in after or before.get(rel) != after.get(rel)]
    if protected:
        out.append(_r("state", f"{len(protected)} other files left alone", not touched,
                      "no collateral change" if not touched
                      else f"changed for no reason: {', '.join(sorted(touched)[:6])}"))

    for rel, fields in (st.get("frontmatter") or {}).items():
        text_after = _read(result, rel)
        if text_after is None:
            out.append(_r("state", f"frontmatter {rel}", False, "file missing afterwards"))
            continue
        fm_b = read_frontmatter_text(_read(pristine, rel) or "")
        fm_a = read_frontmatter_text(text_after)
        for key, expected in fields.items():
            got, old = (fm_a.get(key) or "").strip(), (fm_b.get(key) or "").strip()
            if expected == "CHANGED":
                ok, detail = got != old, f"«{old}» -> «{got}»"
            elif expected == "UNCHANGED":
                ok, detail = got == old, f"«{old}» -> «{got}»"
            elif expected == "NONEMPTY":
                ok, detail = bool(got), f"«{got}»"
            elif expected == "EMPTY":
                ok, detail = not got, f"«{got}»"
            else:
                ok, detail = norm(expected) in norm(got), f"«{got}» (expected ~«{expected}»)"
            out.append(_r("state", f"{rel}:{key} = {expected}", ok, detail))

    for rel, needles in (st.get("contains") or {}).items():
        text = _read(result, rel) or ""
        for needle in needles:
            ok = norm(needle) in norm(text)
            out.append(_r("state", f"{rel} contains «{needle}»", ok,
                          "present" if ok else "absent"))

    # The log is append-only with new entries at the TOP. An earlier version of
    # this check looked for a keyword in the first 900 characters — and the
    # account was already named in an older entry sitting at the top, so a new
    # entry appended at the bottom passed. It was checking for a word, not an
    # order. See selftest.py.
    top = st.get("log_top_mentions")
    if top:
        rel = st.get("log_file", "log.md")
        before_e, after_e = _log_entries(_read(pristine, rel)), _log_entries(_read(result, rel))
        out.append(_r("state", "a log entry was added", len(after_e) > len(before_e),
                      f"{len(before_e)} -> {len(after_e)} entries"))
        if after_e:
            dates = [d for d, _ in after_e if d]
            first = after_e[0][0]
            ordered = bool(first) and bool(dates) and first == max(dates)
            out.append(_r("state", "newest log entry is at the top", ordered,
                          f"first entry {first}, most recent {max(dates) if dates else '—'}"
                          + ("" if ordered else " — the new entry went to the bottom")))
            missing = [t for t in top if norm(t) not in norm(after_e[0][1])]
            out.append(_r("state", "the top entry is the right one", not missing,
                          "mentions what it should" if not missing
                          else f"top entry does not mention: {', '.join(missing)}"))
        else:
            out.append(_r("state", "newest log entry is at the top", False, "no dated entries"))
    return out
