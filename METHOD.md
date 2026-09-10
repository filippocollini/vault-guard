# Where not to use a language model

This is the design rule the whole repository is built on. It is short, it is
unglamorous, and following it is most of what separates an AI feature that can
be trusted from one that merely demos well.

> **If a parser can settle it, do not ask a model.**

## The problem it solves

Teams building on language models tend to route every check through the model,
because the model is right there and it can do anything. So they ask it whether
the frontmatter is valid, whether the totals add up, whether a link is dead.

The model answers. It is usually right. And you have paid three ways:

- **Cost.** Every check is a call.
- **Latency.** Every check is a round trip.
- **Non-determinism.** The same input can produce a different verdict tomorrow.

That last one is the expensive one. A check that sometimes disagrees with
itself cannot gate anything. You cannot put it in CI, you cannot block a commit
on it, and after the second false alarm people stop reading its output. The
check still runs. It has stopped being a control.

Meanwhile the checks that genuinely need judgement get the same treatment as
the trivial ones, so they are neither cheap nor trustworthy, and nothing in the
report tells you which is which.

## The two questions

Before writing any check, ask:

**1. Does this have exactly one right answer, derivable from the data?**

If yes, it is arithmetic, parsing or comparison. Write code.

- Is `type` one of the permitted values?
- Does this wikilink point at a note that exists?
- Does `stage_pct` match the stage it claims?
- Does the sum of the deals equal the total the account states?
- Did this operation modify a file it had no business touching?

None of these needs a model. All of them are the kind of thing a model will
get right 97% of the time, which is exactly the failure rate that erodes trust
without ever being bad enough to force a fix.

**2. Does answering it require weighing the merits of this particular case?**

If yes, and only then, a model is the right instrument.

- Of the gaps found, is the one ranked first actually the most dangerous?
- Is the proposed action something a person could do this week?
- Does this section describe scenarios honestly, or defensively?

These have no closed form. Reasonable people would disagree. A model is a
reasonable estimator here, and it is the only one available.

## Where the line actually falls

The interesting discovery, applying this to a real knowledge base, was **how
much falls on the deterministic side of the line once you look.**

Things that sound like judgement and are not:

| Sounds like judgement | Actually |
|---|---|
| "Did it invent a competitor?" | the name appears in the output and not in the source — string comparison |
| "Did it paper over a missing field?" | the cell does not contain any of the known ways to write "unknown" — substring match |
| "Did it get the forecast right?" | recompute it and compare — arithmetic |
| "Did it stay within the requested scope?" | identifiers outside the slice appear in the output — set difference |
| "Did it quietly break something else?" | hash every other file before and after — comparison |

In this repository, of the assertions across five evaluation cases, **roughly
nine in ten are deterministic.** The model-graded remainder is small enough to
run three times per assertion and report the agreement rate.

## The consequences, once you commit to the line

**Deterministic checks are pinned to a clock you control.** `lint.py --today`
and the fixed `today` in each evaluation case exist because a check that
depends on the current date cannot be tested. Reproducibility is not a nicety
here; it is what makes a regression suite possible at all.

**The schema lives in exactly one place.** `schema.py` is the source; the
documentation is generated from it with `--emit-schema`. This is a direct
consequence of the rule: if the schema is executable, nothing downstream needs
to be asked what the schema is.

**Model-graded results are labelled and never gate.** In `eval/run.py` a failed
judgement assertion is reported and does not change the exit code. It is an
opinion. The report should not let it look like a measurement.

**The judge never sees the expected answer.** Given one, it grades similarity
to a text rather than correctness — which is a different property, and an
easier one to satisfy badly.

**Assertions get their own tests.** `eval/selftest.py` breaks a known-good
output in twenty ways and checks that each break trips the right assertion.
This is not belt-and-braces: a loose assertion produces a green suite on a
broken system, which is worse than no suite, because it is trusted. Writing
this file found four real defects in the checks — each of which would have
done exactly that. They are described in the README.

## What this is not

It is not an argument against language models. It is an argument for spending
them where they are the only tool that works, and for being honest in the
report about which results carry which kind of weight.

A system where 90% of the checking is exact and 10% is a labelled estimate is
worth far more than one where 100% is a confident guess.
