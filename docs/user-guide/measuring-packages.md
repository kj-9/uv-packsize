# Measuring packages

## Measure a package set

```bash
uvx uv-packsize apache-airflow==3.0.0
uvx uv-packsize 'iniconfig==2.0.0' six
```

All requested packages and their resolved dependencies are installed together in one temporary environment. A shared dependency is installed once and counted once in the global total.

## Explain a total

Add text-only views when you need more context:

```bash
uvx uv-packsize requests --explain
uvx uv-packsize requests --breakdown
uvx uv-packsize 'package-a' 'package-b' --contributions
```

- `--explain` shows observed dependency paths and direct, transitive, and shared attribution from installed Core Metadata. It is not resolver provenance.
- `--breakdown` shows deduplicated global bytes by file category and, when the metadata graph is complete, dependency role.
- `--contributions` shows exclusive, shared, and closure bytes per requested root. A closure is not a hypothetical uninstall calculation, and closures must not be summed.

These options affect only the text presentation and do not change a JSON result.

## Use the compact summary

The default `--report standard` layout keeps the complete distribution table.
Use the opt-in rich layout for a compact, redacted overview:

```bash
uvx uv-packsize requests --report rich
```

```text
--- Rich Analysis Summary ---
Input kind: fresh-install
Build policy: wheel-only
Completeness: complete
Warnings: none
Distributions: 1
Canonical global size: 1.50 KiB
Distribution-owned aggregate: 1.50 KiB

--- Top Distributions (Showing 1 of 1) ---
Distribution  Owned size
------------  ----------
sample          1.50 KiB
```

This example is generated from a fixed test result; actual names and sizes
depend on the resolved environment. Rich analysis reports show at most five
distributions and state `Showing 5 of N` when more were measured. The rich
primary summary omits raw requirements, installed paths, resolved versions,
context fingerprints, and lock identities.

The existing `--bin`, `--explain`, `--breakdown`, `--contributions`, budget,
and baseline-writing behavior composes with the rich primary report. With a
baseline, rich mode renders a redacted comparison summary and up to five
non-zero distribution changes. Appended sections are not covered by the
primary-summary redaction: `--bin` can display script paths, and `--explain`
can display installed metadata including resolved versions and dependency
information. `--json` and `--comparison-json` ignore `--report`, preserving
their versioned output bytes.

## Suppress progress messages

Use `--quiet` when a script needs only the final report or JSON document:

```bash
uvx uv-packsize requests --quiet
uvx uv-packsize requests --json --quiet > analysis.json
```

Quiet mode suppresses transient progress and completion messages across fresh,
project/lock, and existing-prefix analysis. It does not suppress final standard
or rich text, graph explanation sections, budget output, sanitized errors, or
Click usage errors. Baseline comparison and writing keep their final output and
file behavior. For `--json` and `--comparison-json`, stdout is byte-identical
with and without `--quiet`; only routine stderr progress is removed.

## Save JSON

```bash
uvx uv-packsize requests==2.32.5 --json > analysis.json
```

On success, standard output is exactly one JSON document. Progress and sanitized operational errors go to standard error. Check `schema_version` and `context.input_kind` before interpreting a saved result.

## Inspect an existing environment

`--prefix` is read-only: it does not run Python, invoke uv, or change the prefix. Supply every site-packages directory relative to the prefix and declare its filesystem case rule:

```bash
uvx uv-packsize --prefix .venv \
  --site-packages lib/python3.12/site-packages \
  --case-rule sensitive --json > prefix-analysis.json
```

`--site-packages` can be repeated. Prefix scans use a distinct schema and do not support comparisons or budgets. Scan a stable prefix because a concurrent change can race validation and inventory collection.

`--bin` moves RECORD-owned scripts into a separate text table without changing the global total or JSON bytes.
