---
name: account-review
description: Qualify an account against the eight-dimension methodology and name the gaps.
---

# ACCOUNT REVIEW

`ACCOUNT REVIEW <account>` — read the account note and its deals, fill the
qualification table, rank the gaps, give one action per gap.

## Sources

1. `notes/accounts/<slug>.md` — frontmatter is machine-readable state
   (`owner`, `status`, `open_pipeline`, `economic_buyer`, `champion`); the prose
   holds context and open items.
2. `notes/deals/*.md` for that account.
3. `notes/meta/methodology.md` — the eight dimensions.

Resolve the account name loosely. **If two accounts could match, ask which one
rather than choosing.** If none match, list what is available.

## Output

A table, one row per dimension:

| Dimension | State | Source / note |
|---|---|---|
| **M**etrics | … | … |
| **E**conomic Buyer | … | … |
| **D**ecision Criteria | … | … |
| **D**ecision Process | … | … |
| **P**aper Process | … | … |
| **I**dentify Pain | … | … |
| **C**hampion | … | … |
| **C**ompetition | … | … |

Then:
- **Critical gaps** — the weak dimensions that most threaten the deal, ranked.
- **Action per gap** — exactly one concrete next action per critical gap, each
  with an owner in parentheses.

## Rules

- **An empty field is the finding, not an error.** Do not promote a technical
  contact to champion, or a named procurement clerk to economic buyer, to make
  the table look complete.
- Mark inferred values as inferred. Do not invent qualification data.
- If the record supports nothing, say so. A mostly-empty review of a mostly-empty
  record is the correct output.
- Read only. Do not modify any note.
