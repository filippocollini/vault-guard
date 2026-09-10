# vault-guard

**Quality control for a markdown knowledge base that feeds a language model —
and for the model's output when it comes back.**

Two halves, joined by one rule.

```bash
python3 lint.py demo-vault --today 2026-09-10   # is the knowledge base sound?
python3 eval/selftest.py                        # are the assertions sound?
python3 eval/run.py                             # is the model's output sound?
```

No dependencies. Standard library only. Python 3.9+.

---

## The problem

You point a language model at a folder of notes and it starts answering
questions about your business. It works immediately, which is the trap. Two
things are now true and neither is visible:

**The notes are wrong in ways nobody has checked.** Frontmatter drifts. Links
rot. Two pages record the same figure and disagree. The model does not notice
— it reads what is there and answers fluently from it.

**The answers are wrong in ways nobody can see.** The output is always
plausible. It is well written when it is right and well written when it has
invented a name, dropped the one blocker that mattered, or quietly reported on
the wrong entity. There is no red error. There is a tidy table that is false.

The usual response to the second problem is to try it a few times and form an
impression. That does not survive contact with a changing system: it covers the
easy cases rather than the real failure modes, it cannot be repeated when the
prompt changes, and it depends on someone who already knows what the answer
should be.

This repository is the alternative: **check the input mechanically, check the
output mechanically, and use a model only where nothing else can decide.**

---

## The rule

> **If a parser can settle it, do not ask a model.**

[METHOD.md](METHOD.md) is the full argument. The short version: teams route
every check through the model because it is there, and pay in cost, latency
and — the expensive one — non-determinism. A check that disagrees with itself
cannot gate anything, so after the second false alarm people stop reading it.
It still runs. It has stopped being a control.

Assertions here fall into five classes:

| Class | Verifies | How | Cost | Reliability |
|---|---|---|---|---|
| Structure | the promised shape is there | parsing | zero | exact |
| Grounding | claims trace to the source, inventions do not appear | string comparison | zero | exact |
| Oracle | the numbers are the ones the data produces | recomputation | zero | exact |
| State | the vault afterwards is the right vault | file hashing | zero | exact |
| Judgement | the reasoning is right | a second model | high | partial |

**Roughly nine assertions in ten are deterministic.** Things that sound like
judgement usually are not: *"did it invent a competitor?"* is a name present in
the output and absent from the source. *"did it paper over a missing field?"*
is a cell that fails to contain any of the known ways to write "unknown".

The tenth is kept small enough to vote on three times and report the agreement
rate — and it **never changes the exit code**. An opinion should not be able
to masquerade as a measurement.

---

## Half one — `lint.py`

Deterministic checks over the notes themselves.

```
$ python3 lint.py demo-vault --today 2026-09-10

3 ERROR · 4 WARN · 4 INFO

| Check          | ERROR | WARN | INFO |
|----------------|-------|------|------|
| links          | 0     | 2    | 3    |
| pipeline       | 2     | 2    | 0    |
| reconciliation | 1     | 0    | 0    |
| staleness      | 0     | 0    | 1    |

## ERROR (3)
- notes/accounts/verta-robotics.md — account states 500000 open, deals sum to 410000 (difference +90000)
- notes/deals/d-104-orbit-logistics.md — stage `proposal` implies 0.6, stage_pct says 0.4
- notes/deals/d-104-orbit-logistics.md — weighted 54000 but amount x stage_pct = 36000
```

Properties worth copying if you adapt this:

- **The schema has one home.** `schema.py` defines it; `lint.py --emit-schema`
  generates the documentation from it. The schema was previously written down
  in three places — linter, templates, docs — and they drifted until none was
  right.
- **`--today` pins the clock.** A check that depends on the current date cannot
  be tested, so staleness and overdue-date checks take the date as an argument.
- **It never modifies a note.** It writes a report and nothing else.
- **Exit 1 on ERROR**, so it works as a commit hook or CI gate.
- **Cross-layer reconciliation** is the check that earns its keep: each account
  states its open pipeline, each deal states its amount, both are maintained by
  hand in different places, and they diverge. Better to find that here than in
  a meeting.

## Half two — `eval/`

The same discipline applied to what comes back out.

Five cases, each a miniature synthetic vault built around **one specific way of
being wrong** — not around a feature:

| Case | Situation | Failure it measures |
|---|---|---|
| 01 | €780k deal, nobody has met the buyer | **filling a hole** — promoting the technical contact to champion, because a complete table looks like better work |
| 02 | one call on file, six dimensions unsupported | **invention** — plausibility in place of fact when the source is silent |
| 03 | healthy deal, eight of eight covered | **manufacturing problems** — the negative control |
| 04 | nine deals, three contradicting themselves | **a wrong number nobody can see**, and **laundering dirty records into a clean total** |
| 05 | a note that must be written into the vault | **collateral damage**, **inferring too much**, **skipped conventions** |

Three deserve a note.

**Case 03 is the negative control**: the right answer is "this is fine". Almost
no evaluation suite contains one, which is why so many systems appear to work
until someone looks. Everyone verifies that the system finds something; nobody
verifies that it stops when there is nothing to find. A system that always
reports a problem is not cautious, it is noise.

**Case 04 uses an oracle.** The expected figures are not written down. A second
independent implementation (`eval/oracle.py`) recomputes them from the fixture.
So the expectation updates itself when the fixture changes, the forecast rules
have to exist as executable code rather than as prose in a prompt, and "the
model got the total wrong" becomes falsifiable — you know by how much.

**Case 05 grades the vault, not the prose.** The one skill that writes is
judged on the difference between the vault before and after: what must change,
and — the neglected half — what must not, byte for byte. Its raw text mentions
a second account in passing, and that page must not move. A skill that writes
fails in two ways: it fails to do the job, which you notice; or it does
something *else as well*, which is silent.

### Record and replay

- **replay** (default) re-checks stored outputs. Free, offline, deterministic,
  belongs in CI.
- **record** (`--record`) calls the model and rewrites them. Costs tokens; you
  do it when a skill changes.

Without the split, every assertion would need a model call, the suite would be
slow and flaky, and nobody would run it. With it, almost all the checking runs
in a second and spending money is an explicit decision.

---

## Who checks the checks

`eval/selftest.py` is the part I would point at first.

An evaluation suite has a quiet way of being useless: **passing always.** Write
the assertions loosely and the report is green whatever comes out — and it
inspires confidence while measuring nothing.

The selftest takes a correct output, breaks it in twenty ways that map
one-to-one onto the failures the suite should catch, and verifies that each
break trips the right check. A mutation that slips through means that assertion
earns nothing.

It calls no model, runs in about a second, and **has found four real defects**:

1. **The item filter was too broad.** It discarded any bullet starting with
   "no", so *"No champion identified — Sollner has no budget"*, a serious gap,
   was read as a declaration that there were none. The negative-control case
   would have gone green for the wrong reason.
2. **The log-ordering check measured the wrong thing.** It looked for a keyword
   in the first 900 characters of the log — but the account was already named
   in an older entry sitting at the top, so a new entry appended at the bottom
   passed. It was checking for a word, not an order.
3. **Listing a deal was satisfied by any mention.** A deal dropped from the
   at-risk list was still named in a data-quality footnote, and the check
   passed. An identifier now has to appear next to its own value.
4. **Numbers were matched as substrings.** A coverage ratio of 1.9 was found
   inside the total 1,331,900, so a readout quoting the wrong coverage passed.
   Numeric matches are now bounded.

Every one of those would have produced a green suite on a broken system.

```
$ python3 eval/selftest.py

suite 1 — text assertions
  item filter: 7/7 lines classified correctly
  reference output: 20/20 assertions passed
  caught   papers_over_the_gap      -> expected «economic_buyer declared uncovered»
  caught   promotes_the_engineer    -> expected «champion declared uncovered»
  ...
suite 2 — arithmetic
  oracle: 10/10 values agree with the hand calculation
  oracle: 3/3 self-contradicting deals detected
  ...
suite 3 — vault state
  reference vault: 22/22 assertions passed
  caught   collateral_damage        -> expected «other files left alone»
  ...
SELFTEST OK — every assertion tells a correct output from a broken one
```

---

## Layout

```
vault-guard/
├── METHOD.md              where not to use a language model — the design argument
├── schema.py              the single source of truth for the note schema
├── lint.py                deterministic checks over the knowledge base
├── demo-vault/            a small synthetic vault, with defects planted on purpose
├── skills/                the three skills under evaluation
└── eval/
    ├── run.py             orchestration, record/replay, reporting
    ├── checks.py          structure, grounding, oracle — all deterministic
    ├── statecheck.py      vault state, for the skill that writes
    ├── oracle.py          independent recomputation of the arithmetic
    ├── judge.py           judgement — deliberately isolated
    ├── selftest.py        breaks known-good outputs to test the assertions
    └── cases/NN-name/
        ├── case.json      prompt, assertions, and the failure under test
        ├── vault/         the fixture (or `vault_from` to reuse another)
        └── recorded.md    the last recorded output
```

Adding a case means creating a folder with a `case.json` and a fixture. No code
to touch.

---

## What this is not

Stated plainly, because a suite that presents itself as complete is worse than
none:

- **It does not measure writing quality.** It measures correctness, grounding,
  structural completeness and effects on the vault. A correct, graceless output
  passes.
- **Five cases are not coverage.** They are five ways of failing, chosen
  because they were observed or expected. There are others.
- **Judgement remains an opinion.** Hence labelled separately, and never gating.
- **The oracle can be wrong too.** It is independent, not infallible; the
  selftest compares it against figures worked by hand, which is as far as that
  goes.
- **The fixtures are synthetic.** Every company, person and figure is invented.
  The cost is that they are tidier than a real vault.

## Current results

All five cases recorded and passing, against `claude-sonnet-5`:

```
[PASS] 01-unconfirmed-buyer      20/20   large deal, buyer never met
[PASS] 02-sparse-record          20/20   one call on file
[PASS] 03-well-qualified         21/21   negative control
[PASS] 04-pipeline-arithmetic    18/18   checked against the oracle
[PASS] 05-note-write             24/24   graded on the vault, not the prose
```

Green is the *end* of the story here, not the beginning. The first recorded
run failed almost everywhere, and working through it changed the suite more
than it changed anything else:

- **The negative control was contaminated.** The "healthy" account carried two
  contradictions I had written without noticing — procurement's 30-day window
  did not fit the stated signature date, and the buyer's signing authority
  conflicted with a board step. The model found both. The fixture was wrong,
  not the output. And after cleaning it the model still named two epistemic
  weaknesses that were fair, which is why "zero gaps" turned out to be the
  wrong bar for a negative control: what must not happen is presenting a
  *documented* dimension as uncovered.
- **A spec ambiguity sent two different numbers to the same reader.** The
  skill said "commit" without saying gross or weighted. The model summed
  weighted, the oracle summed gross, and both readings were defensible — which
  means the specification was the defect. Same again for coverage: dividing
  the whole open pipeline by one quarter's remaining quota compares two
  horizons, and there the model's reading was right and the oracle's was
  wrong.
- **Four assertions were measuring the wrong thing.** A question mark counted
  as "unknown". "Empty" did not. A verdict column was being read together with
  its evidence prose, so a well-filled row failed because the prose said "see
  gap below". And `€1,878k` was reported missing because the number matcher
  had never learned the notation every real forecast uses.

Each of those was found by running the thing, and each is now a case or a
comment in the code.

## Background

Extracted from a private knowledge vault of a few hundred notes used for
day-to-day account work, where the linter and the evaluation suite both run as
commit gates. The private version covers eleven cases across five skills; this
is the method, with the domain-specific parts removed and the reasoning left in.

MIT licensed.
