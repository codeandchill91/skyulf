# Agent Guidelines: Token Optimization via TOON

## 1. When to use TOON

TOON is a compact encoding for **uniform tabular data**. Its value is real but
narrow: it pays off when you are about to pull a large JSON payload *into your
own context*.

**The trip-wire:** before reading any JSON larger than ~5 KB / ~100 lines that
is an array of objects sharing the same keys, convert it with
`convert_file_to_toon(file_path=..., output_path=...)` and read the written
file instead of the raw JSON.

This fires when you are about to:
- `view` / `cat` a `.json` file over ~5 KB
- pipe `gh api ...`, `npm ls --json`, a coverage or test report into context
- read a lockfile, manifest, or fixture that is a long uniform record list

## 2. Always pass `output_path` for large files

With `output_path` set, `convert_file_to_toon` writes the TOON to disk and
returns only a short summary, so the conversion itself costs almost nothing.
Without it, the entire payload comes back in the response — fine for a quick
look, wasteful when you only need part of a large file.

## 3. When NOT to use TOON

These carve-outs matter as much as the rule:

- **Human-facing output** — Markdown reports, PR descriptions, chat responses.
  A Markdown table is only ~12% larger than TOON and far more readable.
  Readability wins. Do **not** encode deliverables as TOON.
- **Data that never was JSON.** Values already held in a program and printed as
  text are compact; converting them to JSON just to encode as TOON is a net
  loss.
- **Irregular structures** — nested, ragged, or heterogeneous objects. TOON's
  gain comes from hoisting shared keys into one header row; without uniform
  keys it degrades toward JSON size with worse readability.
- **Small payloads** (< ~100 rows / ~5 KB) — the round-trip costs more than it
  saves.
- **Anything another program parses** — configs, fixtures, API bodies. Keep
  JSON.

## 4. Realistic savings (measured)

The savings depend entirely on your baseline:

| Baseline | TOON saving |
|---|---|
| JSON (pretty, indent=2) | ~44% |
| JSON (compact) | ~35% |
| Markdown table | ~12% |

The commonly-quoted "30–60%" holds **only against JSON**. Compare against the
format you would actually have written otherwise — if that is a Markdown table,
TOON is usually not worth it.

Nested (non-tabular) JSON benefits far less, and can even be *larger* than
compact JSON. Check the shape before assuming a win.

## 5. TOON Syntax Overview

TOON removes extraneous punctuation (braces, brackets, redundant quotes):

### Objects (Indentation-based)
```
user:
  id: 101
  name: Alice
  role: admin
```

### Primitive Arrays (Inline)
```
tags[3]: python,mcp,ai
```

### Tabular Arrays (Array of Homogeneous Objects)
```
items[3]{id,name,active}:
  1,Alice,true
  2,Bob,false
  3,Charlie,true
```

This last form is where the savings come from — the keys appear once in the
header instead of on every row.
