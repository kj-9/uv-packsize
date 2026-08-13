# Measuring packages

## Measure a package set

```bash
uvx uv-packsize apache-airflow==3.0.0
uvx uv-packsize 'iniconfig==2.0.0' six
```

All requested packages and their resolved dependencies are installed together in one temporary environment. A shared dependency is installed once and counted once in the global total.

## Choose output or save JSON with `--json`

The default terminal report is a compact rich summary. Save the versioned result when another tool, review, or later comparison needs stable data:

```bash
uvx uv-packsize requests==2.32.5 --json > analysis.json
```

On success, standard output is exactly one JSON document. Check `schema_version` and `context.input_kind` before using a saved result. `--comparison-json` produces a versioned comparison document when a compatible baseline is supplied.

## Explain a total with `--explain`

Add text-only views when you need context for a result:

```bash
uvx uv-packsize requests --explain
uvx uv-packsize requests --breakdown
uvx uv-packsize 'package-a' 'package-b' --contributions
```

- `--explain` shows observed dependency paths and direct, transitive, and shared attribution from installed Core Metadata; it is not resolver provenance.
- `--breakdown` groups deduplicated global bytes by file category and, when available, dependency role.
- `--contributions` shows exclusive, shared, and closure bytes per requested root. Closures are not hypothetical uninstall calculations and must not be summed.

These options change text presentation only, not the JSON result.

## Show scripts separately with `--bin`

```bash
uvx uv-packsize requests --bin
```

With `--report standard`, `--bin` moves RECORD-owned scripts from the package
table into a separate Binaries table. With `--report rich`, it leaves the
primary summary and Largest Distributions owned sizes unchanged, then appends
the binary details section. Both layouts preserve the canonical global total,
and `--bin` never changes JSON bytes.

## Inspect an existing environment with `--prefix`

`--prefix` is read-only: it does not run Python, invoke uv, or change the prefix. Supply every site-packages directory relative to the prefix and its filesystem case rule:

```bash
uvx uv-packsize --prefix .venv \
  --site-packages lib/python3.12/site-packages \
  --case-rule sensitive --json > prefix-analysis.json
```

`--site-packages` can be repeated. Prefix scans use a separate schema and do not support comparisons or budgets, so scan a stable prefix rather than one being changed concurrently. With `--bin`, prefix text output uses the heading `Binaries in prefix`; generated script sizes can differ from a fresh temporary installation because POSIX shebangs can include the installation path. In prefix JSON mode, `--bin` is accepted but ignored, preserving the same schema v2 bytes.

## Choose a text layout with `--report`

`--report rich` is the default compact overview. The legacy full plain-text table remains available when a script needs it:

```bash
uvx uv-packsize requests --report standard --color never
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

--- Largest Distributions (Showing 1 of 1) ---
Distribution  Owned size
------------  ----------
sample          1.50 KiB
```

The example is generated from a fixed test result; actual names and sizes depend on the resolved environment. Rich reports show at most five distributions. Their primary summary omits raw requirements, installed paths, resolved versions, context fingerprints, and lock identities. `--bin` can show script paths and `--explain` can show installed metadata, so use them carefully when sharing output. Full output and JSON channel details are in the [Measurement contract](reference/measurement-contract.md).

## Suppress progress with `--quiet`

Use `--quiet` when a script needs only the final report or JSON document:

```bash
uvx uv-packsize requests --json --quiet > analysis.json
```

It removes routine progress and completion messages, not final output or sanitized errors. JSON bytes are unchanged.

## Control ANSI color with `--color`

Color defaults to `auto`. Force or disable it explicitly when needed:

```bash
uvx uv-packsize requests --report rich --color always
uvx uv-packsize requests --report standard --color never
```

`auto` decorates only a suitable stdout terminal; `--json` and `--comparison-json` ignore color values. The standard/never combination is the legacy text escape for scripts that cannot consume JSON.

## Next step

- [Compare a baseline or enforce a budget](baselines-and-budgets.md) for package-request results.
- [Measure a locked project](locked-projects.md) when `pyproject.toml` and `uv.lock` define the dependency set.
