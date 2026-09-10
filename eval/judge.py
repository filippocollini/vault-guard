#!/usr/bin/env python3
"""
judge.py — the assertions that need judgement, and only those.

One rule decides what belongs in this file:

    if a parser can settle it, it does not come here.

What is left is genuinely about the merits: "is the gap ranked first the right
one?" cannot be written as a rule, because it depends on the case.

Two precautions, because a judge is itself non-deterministic:

  1. The judge sees the rubric and the output, never a reference answer.
     Otherwise it grades similarity to a text instead of correctness.
  2. Every assertion is voted on several times (three by default) and the
     majority wins. The agreement rate is reported: an assertion that
     consistently splits 2-1 has a bad question, not a broken system.

Judgement results are labelled as such in the report and never change the exit
code. A non-deterministic opinion does not carry the same weight as a parse,
and the report should not let it look as though it does.
"""

import json
import re
import subprocess
from collections import Counter

RUBRIC = """You are grading one property of a model's output. Answer only the
question asked. Ignore style, length and formatting. Do not reward a confident
tone. If the output does not contain enough to decide, the answer is false.

Reply with exactly this JSON and nothing else:
{"verdict": true|false, "reason": "<25 words max>"}

--- QUESTION ---
{question}

--- OUTPUT UNDER REVIEW ---
{output}
--- END OUTPUT ---
"""


def _ask(question, output, model, timeout):
    prompt = RUBRIC.replace("{question}", question).replace("{output}", output)
    try:
        p = subprocess.run(["claude", "-p", prompt, "--model", model],
                           capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return None, "the `claude` CLI is not on PATH"
    except subprocess.TimeoutExpired:
        return None, "timed out"
    if p.returncode != 0:
        return None, (p.stderr or "").strip()[:120]
    m = re.search(r"\{.*\}", p.stdout, re.S)
    if not m:
        return None, "no JSON in the judge's reply"
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None, "the judge's JSON did not parse"
    return bool(data.get("verdict")), str(data.get("reason", ""))[:160]


def check_judgement(text, spec, model="claude-sonnet-5", votes=3, timeout=120):
    out = []
    for item in spec.get("judgement", []):
        ballots, reasons = [], []
        for _ in range(votes):
            verdict, reason = _ask(item["question"], text, model, timeout)
            if verdict is None:
                out.append({"class": "judgement", "check": item["id"], "pass": None,
                            "detail": f"not evaluated: {reason}"})
                ballots = []
                break
            ballots.append(verdict)
            reasons.append(reason)
        if not ballots:
            continue
        winner, count = Counter(ballots).most_common(1)[0]
        out.append({"class": "judgement", "check": item["id"], "pass": winner,
                    "detail": f"{count}/{len(ballots)} agreed — {reasons[ballots.index(winner)]}",
                    "agreement": round(count / len(ballots), 2)})
    return out
