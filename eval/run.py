#!/usr/bin/env python3
"""
run.py — run the evaluation suite.

Two modes, and the split is the most consequential design choice here:

  REPLAY (default)  re-check the outputs already stored in cases/*/recorded.md
                    (and cases/*/recorded-vault/ for the case that writes).
                    Free, offline, deterministic, belongs in CI.

  RECORD (--record) actually call the model and rewrite those stored outputs.
                    Costs tokens; you do it when a skill changes, not on every
                    commit.

The system under test is non-deterministic. If every assertion required a
model call, the suite would be slow, expensive and flaky — and nobody would
run it. Splitting the two means almost all the checking runs in a second and
spending money becomes an explicit decision rather than a side effect.

Usage:
    python3 eval/run.py                 # replay
    python3 eval/run.py --record        # regenerate outputs
    python3 eval/run.py --judge         # add the judgement class
    python3 eval/run.py --case 04       # one case

Exit code 1 on any failed deterministic assertion, or if a case has no
recorded output at all: a CI run must not go green for having checked nothing.
"""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import checks as C  # noqa: E402

CASES_DIR = os.path.join(HERE, "cases")
SKILLS_DIR = os.path.join(ROOT, "skills")


def load_cases(filt):
    out = []
    for name in sorted(os.listdir(CASES_DIR)):
        path = os.path.join(CASES_DIR, name)
        spec_file = os.path.join(path, "case.json")
        if name.startswith("_") or not os.path.isfile(spec_file):
            continue
        if filt and filt not in name:
            continue
        with open(spec_file, encoding="utf-8") as fh:
            spec = json.load(fh)
        spec["_dir"] = path
        out.append(spec)
    return out


def vault_of(case):
    """A case's fixture, or another case's if it reuses one.

    Duplicating a fixture to ask a different question means maintaining it in
    two places; the copy drifts and the suite starts measuring two worlds.
    """
    src = case.get("vault_from")
    return os.path.join(CASES_DIR, src, "vault") if src else os.path.join(case["_dir"], "vault")


def build_vault(case):
    """Compose an isolated copy: the fixture plus the skills under test.

    Each case runs in its own copy. Without that, a case which writes dirties
    the next one and failures become order-dependent — the quickest way to
    make a suite useless.
    """
    tmp = tempfile.mkdtemp(prefix="eval-vault-")
    shutil.copytree(vault_of(case), tmp, dirs_exist_ok=True)
    for skill in case.get("skills", []):
        src = os.path.join(SKILLS_DIR, skill)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(tmp, ".claude", "skills", skill),
                            dirs_exist_ok=True)
    return tmp


def record(case, model, timeout):
    vault = build_vault(case)
    mutation = case.get("expect") == "mutation"

    # A skill that writes cannot be recorded headlessly under the default
    # permission mode: every edit raises a prompt nobody can answer, the run
    # produces a polite refusal, and the state assertions all fail for a
    # reason that has nothing to do with the skill. `acceptEdits` is scoped to
    # this throwaway copy of the fixture in a temp directory, and only for
    # cases that declare themselves as writing.
    cmd = ["claude", "-p", case["prompt"], "--model", model]
    if mutation:
        cmd += ["--permission-mode", "acceptEdits"]
    try:
        p = subprocess.run(cmd, cwd=vault, capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return None, "the `claude` CLI is not on PATH"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    finally:
        if mutation:
            dest = os.path.join(case["_dir"], "recorded-vault")
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(vault, dest, ignore=shutil.ignore_patterns(".claude"))
        shutil.rmtree(vault, ignore_errors=True)

    # The CLI can fail while exiting 0 and printing the error to stdout — an
    # expired token, for instance. Trusting the return code alone once saved
    # an empty file as a recorded output: a green case containing nothing.
    if p.returncode != 0:
        return None, ((p.stderr or p.stdout or "").strip()[:200] or f"exit {p.returncode}")
    out = p.stdout or ""
    if "Failed to authenticate" in out or "API Error" in out:
        return None, out.strip().splitlines()[0][:200]
    if len(out.strip()) < 40:
        return None, f"suspiciously short output ({len(out.strip())} chars)"
    return out, None


def evaluate(case, text, use_judge, judge_opts):
    if case.get("expect") == "mutation":
        import statecheck
        pristine = build_vault(case)
        try:
            results = statecheck.check_state(
                pristine, os.path.join(case["_dir"], "recorded-vault"), case["checks"])
        finally:
            shutil.rmtree(pristine, ignore_errors=True)
        results += C.check_grounding(text, case["checks"])
    else:
        results = C.check_structure(text, case["checks"])
        results += C.check_grounding(text, case["checks"])
        if case["checks"].get("oracle"):
            import oracle
            facts = oracle.compute(vault_of(case), case.get("today"))
            results += C.check_oracle(text, case["checks"], facts)

    if use_judge and case["checks"].get("judgement"):
        import judge
        results += judge.check_judgement(text, case["checks"], **judge_opts)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--case", default="")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--judge-model", default="claude-sonnet-5")
    ap.add_argument("--votes", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--report", default=os.path.join(HERE, "runs", "latest.md"))
    args = ap.parse_args()

    cases = load_cases(args.case)
    if not cases:
        print("no cases found", file=sys.stderr)
        return 2

    rows, failed_hard = [], 0
    for case in cases:
        rec = os.path.join(case["_dir"], "recorded.md")
        has_vault = os.path.isdir(os.path.join(case["_dir"], "recorded-vault"))
        needs_vault = case.get("expect") == "mutation"

        if args.record:
            text, err = record(case, args.model, args.timeout)
            if err or text is None:
                print(f"  ! {case['id']}: recording failed — {err}", file=sys.stderr)
                rows.append((case, None, [], err or "no output"))
                continue
            with open(rec, "w", encoding="utf-8") as fh:
                fh.write(text)
        elif os.path.isfile(rec) and (has_vault or not needs_vault):
            with open(rec, encoding="utf-8") as fh:
                text = fh.read()
        else:
            rows.append((case, None, [], "no recorded output — run with --record"))
            continue

        res = evaluate(case, text, args.judge,
                       {"model": args.judge_model, "votes": args.votes, "timeout": args.timeout})
        hard = [r for r in res if r["class"] != "judgement" and not r["pass"]]
        failed_hard += len(hard)
        rows.append((case, text, res, None))

        print(f"[{'PASS' if not hard else 'FAIL'}] {case['id']}  "
              f"{sum(1 for r in res if r['pass'])}/{len(res)}  — {case['title']}")
        for r in res:
            if r["pass"] is not True:
                print(f"       {'?' if r['pass'] is None else 'x'} "
                      f"[{r['class']}] {r['check']}: {r['detail']}")

    write_report(args.report, rows, args)
    unmeasured = [c["id"] for c, t, r, e in rows if t is None]
    print(f"\nreport: {os.path.relpath(args.report, ROOT)}")
    print("failed deterministic assertions:", failed_hard)
    if unmeasured:
        print("unmeasured cases:", ", ".join(unmeasured))
        print("  -> run with --record (needs an authenticated `claude` CLI)")
    return 1 if (failed_hard or unmeasured) else 0


def write_report(path, rows, args):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    L = ["# Evaluation report", "",
         f"{dt.datetime.now():%Y-%m-%d %H:%M} · mode: "
         f"{'record' if args.record else 'replay'} · "
         f"judgement: {'on' if args.judge else 'off'}", "",
         "| Case | Structure | Grounding | Oracle | State | Judgement | Result |",
         "|---|---|---|---|---|---|---|"]
    for case, text, res, err in rows:
        if err:
            L.append(f"| {case['id']} | — | — | — | — | — | error: {err} |")
            continue

        def score(cls):
            sub = [r for r in res if r["class"] == cls]
            return f"{sum(1 for r in sub if r['pass'])}/{len(sub)}" if sub else "—"
        hard = any(r["class"] != "judgement" and not r["pass"] for r in res)
        L.append(f"| {case['id']} | {score('structure')} | {score('grounding')} "
                 f"| {score('oracle')} | {score('state')} | {score('judgement')} "
                 f"| {'FAIL' if hard else 'PASS'} |")

    L += ["", "## Detail", ""]
    for case, text, res, err in rows:
        L += [f"### {case['id']} — {case['title']}", "",
              f"**Failure mode under test:** {case.get('failure_mode', '—')}", ""]
        if err:
            L += [f"Error: {err}", ""]
            continue
        for r in res:
            state = {True: "ok", False: "FAILED", None: "not evaluated"}[r["pass"]]
            L.append(f"- `{r['class']}` **{r['check']}** — {state}. {r['detail']}")
        L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
