# vault-guard

**Quality control for a markdown knowledge base that feeds a language model —
and for the model's output when it comes back.**

Two halves, joined by one rule: *if a parser can settle it, don't ask a model.*

```bash
python3 lint.py demo-vault --today 2026-09-10   # is the knowledge base sound?
python3 eval/selftest.py                        # are the assertions sound?
python3 eval/run.py                             # is the model's output sound?
```

No dependencies. Standard library only. Python 3.9+. MIT.

---

## What it found

Five evaluation cases, recorded against `claude-sonnet-5`:

```
[PASS] 01-unconfirmed-buyer      20/20   large deal, buyer never met
[PASS] 02-sparse-record          20/20   one call on file
[PASS] 03-well-qualified         21/21   negative control
[PASS] 04-pipeline-arithmetic    18/18   checked against an oracle
[PASS] 05-note-write             24/24   graded on the vault, not the prose
```

Green is the end of the story, not the beginning. The first run failed almost
everywhere, and working through it changed the suite more than anything else:

- **The negative control was contaminated.** My "healthy" account carried two
  contradictions I had written without noticing: procurement's 30-day window
  didn't fit the stated signature date, and the buyer's signing authority
  conflicted with a board step. The model found both. The fixture was wrong,
  not the output.
- **A spec ambiguity sent two different numbers to the same reader.** The
  skill said "commit" without saying gross or weighted. The model summed
  weighted, the oracle summed gross, and both readings were defensible — so
  the specification was the defect. Same again for coverage, where the
  model's reading was right and my oracle's was wrong.
- **Four assertions were measuring the wrong thing.** A question mark counted
  as "unknown"; the word "Empty" did not. A verdict column was read together
  with its evidence, so a well-filled row failed because the prose said "see
  gap below". And `€1,878k` was reported missing, because the number matcher
  had never learned the notation every real forecast uses.

Each of those is now a test case or a comment in the code.

---

## The problem

Point a language model at a folder of notes and it starts answering questions
about your business. It works immediately, which is the trap.

**The notes are wrong in ways nobody has checked.** Frontmatter drifts, links
rot, two pages record the same figure and disagree. The model doesn't notice.
It reads what's there and answers fluently from it.

**The answers are wrong in ways nobody can see.** The output is always
plausible — well written when it's right, and well written when it has
invented a name, dropped the one blocker that mattered, or reported on the
wrong company. There's no red error. There's a tidy table that is false.

The usual response is to try it a few times and form an impression. That
covers the easy cases instead of the real failure modes, can't be repeated
when the prompt changes, and depends on someone who already knows the answer.

---

## The rule

> **If a parser can settle it, don't ask a model.**

[METHOD.md](METHOD.md) has the full argument. In short: teams route every
check through the model because it's there, and pay in cost, latency and
non-determinism. A check that disagrees with itself can't gate anything, so
after the second false alarm people stop reading it.

Assertions fall into five classes:

| Class | Verifies | How | Cost | Reliability |
|---|---|---|---|---|
| Structure | the promised shape is there | parsing | zero | exact |
| Grounding | claims trace to the source, inventions don't appear | string comparison | zero | exact |
| Oracle | the numbers are the ones the data produces | recomputation | zero | exact |
| State | the vault afterwards is the right vault | file hashing | zero | exact |
| Judgement | the reasoning is right | a second model | high | partial |

**About nine assertions in ten are deterministic.** Things that sound like
judgement usually aren't: *"did it invent a competitor?"* is a name present in
the output and absent from the source. *"did it paper over a missing field?"*
is a cell that fails to contain any known way of writing "unknown".

The tenth is small enough to vote on three times and report the agreement
rate — and it **never changes the exit code**. An opinion shouldn't be able to
pass for a measurement.

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

Worth copying if you adapt this:

- **The schema has one home.** `schema.py` defines it, `--emit-schema`
  generates the documentation from it. It used to live in three places —
  linter, templates, docs — and they drifted until none was right.
- **`--today` pins the clock.** A check that depends on the current date can't
  be tested.
- **It never modifies a note**, and exits 1 on ERROR so it can gate a commit.
- **Cross-layer reconciliation earns its keep.** Each account states its open
  pipeline, each deal states its amount, both are maintained by hand in
  different places. Better to find the divergence here than in a meeting.

## Half two — `eval/`

Five cases, each a miniature synthetic vault built around **one specific way
of being wrong** — not around a feature:

| Case | Situation | Failure it measures |
|---|---|---|
| 01 | €780k deal, nobody has met the buyer | **filling a hole** — promoting the technical contact to champion, because a complete table looks like better work |
| 02 | one call on file, six dimensions unsupported | **invention** — plausibility in place of fact when the source is silent |
| 03 | healthy deal, eight of eight covered | **manufacturing problems** — the negative control |
| 04 | nine deals, three contradicting themselves | **a wrong number nobody can see**, and **laundering dirty records into a clean total** |
| 05 | a note that must be written into the vault | **collateral damage**, **inferring too much**, **skipped conventions** |

**Case 03 is the negative control**: the right answer is "this is fine".
Almost no suite has one, which is why so many systems look fine until someone
checks. Everyone verifies that the system finds something; nobody verifies
that it stops when there's nothing to find.

**Case 04 uses an oracle.** The expected figures aren't written down — a
second implementation (`eval/oracle.py`) recomputes them from the fixture. So
the expectation updates itself when the fixture changes, the forecast rules
have to exist as code rather than as prose in a prompt, and "the model got the
total wrong" becomes falsifiable: you know by how much.

**Case 05 grades the vault, not the prose.** The one skill that writes is
judged on the difference between the vault before and after — what must
change, and what must not, byte for byte. Its input mentions a second account
in passing, and that page must not move. A writing skill fails either by not
doing the job, which you notice, or by doing something *else as well*, which
is silent.

Outputs are recorded once (`--record`, costs tokens) and re-checked offline
after that (default, free). Without that split every assertion would need a
model call, and nobody would run the suite.

---

## Who checks the checks

`eval/selftest.py` is the part I'd point at first.

A suite has a quiet way of being useless: **passing always.** Write the
assertions loosely and the report is green whatever comes out — inspiring
confidence while measuring nothing.

The selftest takes a correct output, breaks it in twenty ways that map
one-to-one onto the failures the suite should catch, and checks that each
break trips the right assertion. A mutation that slips through means that
assertion earns nothing.

It calls no model, runs in a second, and has found **four real defects**:

1. **The item filter was too broad.** It dropped any bullet starting with
   "no", so *"No champion identified — Sollner has no budget"*, a serious gap,
   read as a declaration that there were none.
2. **The log-ordering check measured the wrong thing.** It looked for a
   keyword in the first 900 characters — but the account was already named in
   an older entry at the top, so a new entry appended at the bottom passed.
   It was checking for a word, not an order.
3. **Listing a deal was satisfied by any mention.** A deal dropped from the
   at-risk list was still named in a footnote, and the check passed. An
   identifier now has to appear next to its own value.
4. **Numbers were matched as substrings.** A coverage ratio of 1.9 was found
   inside the total 1,331,900, so a readout quoting the wrong coverage passed.

Every one would have produced a green suite on a broken system.

---

## Layout

```
vault-guard/
├── METHOD.md              where not to use a language model — the argument
├── schema.py              single source of truth for the note schema
├── lint.py                deterministic checks over the knowledge base
├── demo-vault/            a small synthetic vault, defects planted on purpose
├── skills/                the three skills under evaluation
└── eval/
    ├── run.py             orchestration, record/replay, reporting
    ├── checks.py          structure, grounding, oracle — all deterministic
    ├── statecheck.py      vault state, for the skill that writes
    ├── oracle.py          independent recomputation of the arithmetic
    ├── judge.py           judgement — deliberately isolated
    ├── selftest.py        breaks known-good outputs to test the assertions
    └── cases/NN-name/     case.json + fixture + recorded output
```

Adding a case means creating a folder with a `case.json` and a fixture. No
code to touch.

## What this is not

- **It doesn't measure writing quality.** A correct, graceless output passes.
- **Five cases are not coverage.** They're five ways of failing, chosen
  because they were observed or expected. There are others.
- **Judgement remains an opinion** — labelled separately, never gating.
- **The oracle can be wrong too.** It's independent, not infallible; on the
  first run it was the oracle that had the coverage rule wrong, not the model.
- **The fixtures are synthetic.** Every company, person and figure is
  invented, which also makes them tidier than a real vault.

## Background

Extracted from a private knowledge vault of a few hundred notes used for
day-to-day account work, where the linter and the suite both run as commit
gates. The private version covers eleven cases across five skills; this is the
method, with the domain-specific parts removed and the reasoning left in.
