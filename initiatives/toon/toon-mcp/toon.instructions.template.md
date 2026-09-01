---
    description: Global instructions for token-efficient structured data representation using TOON
    applyTo: '**'
---
# Token Optimization with TOON (Token-Oriented Object Notation)

TOON is a compact encoding for **uniform tabular data**. Its value is real but
narrow: it only pays off when you are about to pull a large JSON payload
*into your own context*. Use it there, and nowhere else.

## The trip-wire (this is the rule)

**BEFORE reading any JSON into context — a file, an API response, or tool
output — that is larger than ~100 lines or ~5 KB AND is an array of objects
sharing the same keys: convert it with `convert_file_to_toon`, passing
`output_path`, then read the written file.**

Concretely, this fires when you are about to:
- `view` / `cat` a `.json` file over ~5 KB
- pipe `gh api ...`, `npm ls --json`, `pytest --json-report`, a coverage
  report, or any similar command's JSON output into your context
- read a lockfile, manifest, or fixture that is a long uniform record list

If the payload is a **file**, use `convert_file_to_toon` (it never round-trips
the JSON through your context). If it is **command output**, write it to a temp
file first, then convert — do not paste the JSON into `encode_toon`, because
that spends the tokens you are trying to save.

## Always pass `output_path` for large files

`convert_file_to_toon` returns a **short summary** (not the payload) when
`output_path` is set, then you read the written file. This keeps the conversion
itself nearly free.

Measured on a 9,368-char fixture:

| Approach | Cost into context | Net |
|---|---:|---|
| Read the source JSON directly | ~2,316 tokens | baseline |
| `output_path` + read the file | ~1,412 tokens | **-39%** |
| Tool call overhead itself | ~50 tokens | negligible |

Without `output_path` the full TOON comes back in the response, which is fine
for a quick look but wastes tokens if you only need part of it.

> **Historical note:** this server previously mirrored every return value into a
> `structuredContent` block, sending each payload **twice** and making TOON more
> expensive than the JSON it replaced. Fixed via `structured_output=False`; if
> you see a `{"result": ...}` duplicate, the server is out of date.

## When NOT to use TOON

These carve-outs matter as much as the rule. Do not reach for TOON when:

- **You are writing a deliverable for a human** — `.md` reports, PR
  descriptions, code comments, chat responses. Markdown tables are only ~12%
  larger than TOON (measured, 188-row table: 12,259 vs 10,775 chars) and are
  vastly more readable. Readability wins; the saving does not justify it.
- **The data never becomes JSON.** Data that lives inside a Python/Node process
  and is printed directly as text is already compact. Converting it *to* JSON
  just to encode it as TOON is a net loss.
- **The structure is irregular** — nested, ragged, or heterogeneous objects.
  TOON's gain comes from hoisting shared keys into one header row; without
  uniform keys it degrades toward JSON size with worse readability.
- **The payload is small** (under ~100 rows / ~5 KB). The MCP round-trip costs
  more than it saves.
- **Exact fidelity is required for a downstream consumer** — writing a config,
  a fixture, or anything another program parses. Keep it as JSON.

## Realistic savings (measured, not advertised)

Baselines matter. Against a 188-row uniform dataset:

| Baseline | Chars | TOON saving |
|---|---:|---|
| JSON (pretty, indent=2) | 19,356 | **44%** |
| JSON (compact) | 16,722 | **35%** |
| Markdown table | 12,259 | **12%** |

The commonly-quoted "30–60%" holds **only against JSON**. If your alternative
is a markdown table, the real gain is ~12% and usually not worth the
readability cost. Choose the tool by comparing against what you would
*actually* have written otherwise.

## Tool notes / known rough edges

- `convert_file_to_toon` reports output size in a way that **overstates it for
  non-ASCII content** (emoji, accents) because it counts bytes, not characters.
  A "22 KB" report can be a 10.8 KB string. Don't abandon the conversion based
  on that number.
- Converting a large file can still trip the harness's "output too large to
  read" guard — another reason to always write to `output_path` and read the
  slice you need.
- `estimate_token_savings` requires the JSON **inline**, so it costs the tokens
  it is measuring. Use it once on a representative *sample* to decide, never on
  the full payload. It counts with `tiktoken` (cl100k_base), not a chars/token
  guess, so its numbers are trustworthy.
- Deeply nested JSON (`{"groups": {...}}`) still converts, but the gain comes
  from flat uniform record lists. Check the shape before assuming a win.

## TOON Syntax Reference

- **Objects**: Indentation-based key-value pairs without quotes or braces.
- **Primitive Lists**: Inlined with count header `tags[3]: a,b,c`.
- **Tabular Arrays**: Column-header format `items[N]{col1,col2}: val1,val2` to
  avoid repeating JSON keys for every row.
