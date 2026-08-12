# Measurement contract

## Definition

For package requests, `uv-packsize` creates a temporary virtual environment, installs requested packages and resolved dependencies with `uv pip install`, then scans installed distributions. Project/lock mode instead uses an isolated locked sync from explicit staged inputs.

The total is **installed logical size**. It is neither compressed wheel or source-distribution size nor allocated filesystem-block usage. `KiB`, `MiB`, and `GiB` use powers of 1024.

## Included files and ownership

Each distribution's `.dist-info/RECORD` is the primary source of file ownership. The scope is the temporary environment prefix, not only `site-packages`, so RECORD-owned scripts, data files, and headers are included when they resolve inside that prefix. Generated `.pyc` files matching recorded Python source files are included when present.

The global total is derived from the included inventory. If multiple distributions claim an installed file, the global total counts it once, so distribution-owned totals can sum to a different value.

The total excludes:

- the Python interpreter and virtual-environment base files;
- the uv cache; and
- files not owned by a distribution RECORD or conservative metadata fallback.

Missing RECORD files, missing installed files, malformed metadata, duplicate ownership, and similar observations leave structured warnings and completeness information; they are not silently treated as a complete result.

## Reproducibility and JSON

Results depend on Python, platform, extras, dependency groups, requirements, and resolver conditions. Compare only compatible results.

| Input mode | Schema | Comparison support |
| --- | --- | --- |
| package requests | analysis-result v1 | v1 fresh-install only |
| existing prefix | analysis-result v2 | not supported yet |
| explicit project and lock | analysis-result v3 | v3 project-lock only |

Check `schema_version` and `context.input_kind` before consuming or comparing a document. The committed schemas live in the repository's [`schemas`](https://github.com/kj-9/uv-packsize/tree/main/schemas) directory.

## Output and exit statuses

`--json` and `--comparison-json` write exactly one JSON document to standard output on success. Progress and sanitized failures go to standard error.

`--quiet` suppresses progress and completion messages only. It applies to all
input modes and both text layouts, including comparison and baseline-writing
flows. Final text or JSON, budget diagnostics, sanitized operational errors,
Click usage errors, and exit statuses remain visible. Successful JSON stdout is
byte-identical with and without `--quiet`; failures retain their existing
stdout-empty rules.

`--color [auto|always|never]` affects only a human-readable final stdout report
and defaults to `auto`. `never` disables ANSI.
`auto` enables ANSI only for a stdout TTY when `TERM != dumb` and `NO_COLOR` is
unset; `always` deliberately ignores those conditions. Decoration is applied
after terminal-safe rendering and does not change semantic text. Progress,
completion messages, sanitized errors, Click usage, and JSON-mode budget
failure diagnostics are always plain. Analysis and comparison JSON accept but
ignore every color value, preserving bytes, channels, and exit behavior.

For human-readable output, `--report rich` is the default terminal-safe summary
limited to five distribution rows. Its primary summary exposes aggregate
measurement facts but not raw requirements, installed paths, resolved versions,
lock identities, or context fingerprints. This redaction does not cover
appended legacy sections: `--bin` can display script paths, and `--explain` can
display installed metadata including resolved versions and dependency
information. Both JSON modes accept and ignore `--report`, leaving their schema
and bytes unchanged.

The 0.2.0 text defaults are rich/auto. `--report standard --color never`
preserves the pre-0.2.0 full plain-text output escape. Standard rows keep their
full size-descending/name-tie order. Rich uses `Largest Distributions (Showing
N of M)` and comparisons use `Largest Distribution Changes (Showing N of M)`;
neither adds a numeric rank column.

| Status | Meaning |
| --- | --- |
| 0 | completed analysis or comparison |
| 1 | operational install or analysis failure |
| 2 | invalid command-line usage |
| 3 | baseline, baseline-write, or budget-policy source failure |
| 4 | incompatible baselines |
| 5 | completed measurement violated its budget policy |
