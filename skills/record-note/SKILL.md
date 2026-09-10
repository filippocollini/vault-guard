---
name: record-note
description: Record raw meeting notes into the right account and deal notes, and update the log. Writes to the vault.
---

# RECORD NOTE

```
RECORD <account>
<raw meeting text>
```

## What it does

1. **Distil** the raw text into a date, an interaction type, and three to six
   bullets. Extractive: capture what was said. Do not infer commitments nobody
   made.
2. **Update the account note** `notes/accounts/<slug>.md`:
   - Append a dated entry under `## Interactions`, newest first (create the
     section if absent). Never rewrite past entries.
   - Update frontmatter only where the raw text clearly supports it
     (`champion`, `economic_buyer`, `status`), and always bump `updated`.
3. **Update the deal note** in `notes/deals/`:
   - `next_action` must never be left empty after a real interaction.
   - Bump `updated`.
   - Change `stage`, `stage_pct` or `expected_close` **only** when the raw text
     clearly supports it. A meeting that mentions a future committee is not a
     stage change.
4. **Append to `log.md`** — newest entry at the **top** of the file.
5. **Report** exactly which files were created and which were modified.

## Rules

- Touch nothing else. If the raw text mentions another account in passing, that
  account's note must not change.
- Never invent a close date. "It depends on the committee" is not a date.
- Frontmatter stays flat YAML. Links use `[[slug]]`.
