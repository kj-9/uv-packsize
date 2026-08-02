# uv-packsize

[![PyPI](https://img.shields.io/pypi/v/uv-packsize.svg)](https://pypi.org/project/uv-packsize/)
[![Changelog](https://img.shields.io/github/v/release/kj-9/uv-packsize?include_prereleases&label=changelog)](https://github.com/kj-9/uv-packsize/releases)
[![Tests](https://github.com/kj-9/uv-packsize/actions/workflows/ci.yml/badge.svg)](https://github.com/kj-9/uv-packsize/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/kj-9/uv-packsize/blob/master/LICENSE)

report size of python package with its deps using uv

## Installation

Install this tool using `pip`:
```bash
pip install uv-packsize
```
or using `uv`:
```bash
uv tool install uv-packsize
```

## Usage

For help, run:
```
uv-packsize --help
```
<!-- [[[cog
import cog
from uv_packsize import cli
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(cli.cli, ["--help"])
help = result.output.replace("Usage: cli", "Usage: uv-packsize")
cog.out(
    f"```bash\n{help}\n```"
)
]]] -->
```bash
Usage: uv-packsize [OPTIONS] [PACKAGE_NAMES]...

  Report the size of a Python package and its dependencies using uv.

Options:
  --version                       Show the version and exit.
  --prefix PATH                   Analyze an existing prefix without running or
                                  changing it.
  --baseline PATH                 Read a baseline JSON file and report its diff
                                  from a fresh analysis.
  --write-baseline PATH           Atomically write the fresh schema v1 analysis
                                  JSON to PATH.
  --overwrite-baseline            Replace an existing --write-baseline target
                                  explicitly.
  --site-packages REL             Relative site-packages directory inside
                                  --prefix (repeatable).
  --case-rule [sensitive|insensitive]
                                  Target filesystem case rule required with
                                  --prefix.
  --bin                           Text output only: display RECORD-owned scripts
                                  separately without changing the total.
  --allow-build                   Allow source builds during installation;
                                  disabled by default.
  --json                          Write the versioned analysis result as JSON to
                                  stdout.
  --comparison-json               Write the versioned baseline comparison result
                                  as JSON to stdout.
  --budget-config PATH            Read budget policy from [tool.uv-
                                  packsize.budget] in PATH.
  --max-total BYTES               Maximum canonical global logical size in
                                  bytes.  [0<=x<=9223372036854775807]
  --max-increase BYTES            Maximum canonical global logical-size increase
                                  in bytes.  [0<=x<=9223372036854775807]
  --incomplete-policy [fail|allow-partial]
                                  Budget handling for incomplete measurements.
  --explain                       Text output only: show installed-metadata
                                  dependency paths and attribution.
  --breakdown                     Text output only: show global file-category
                                  and dependency-role sizes.
  --contributions                 Text output only: show non-split requested-
                                  root byte contributions.
  -p, --python TEXT               Specify the Python version for the virtual
                                  environment.
  --help                          Show this message and exit.

```
<!-- [[[end]]] -->

You can also use:
```bash
python -m uv_packsize --help
```

### Existing prefix analysis

Use `--prefix` to inspect an already-installed environment without running or
changing it. Specify every site-packages directory relative to that prefix and
declare its filesystem case rule explicitly:

```bash
uv-packsize --prefix .venv \
  --site-packages lib/python3.12/site-packages \
  --case-rule sensitive --json > prefix-analysis.json
```

`--site-packages` is repeatable. Its value must be a non-empty, canonical
relative path in the native path form of the host running the command; absolute
paths, `.`/`..`, and symlink components are rejected. A relative `--prefix` is
resolved from the current working directory and fixed to its canonical physical
directory before scanning. This mode only supports the host's native path
flavor. `--case-rule sensitive` or `--case-rule insensitive` is a trusted
caller declaration, not a filesystem probe, so it must match the target
filesystem's semantics.

The prefix is never used to create an environment, install or uninstall a
package, run Python, invoke `uv`, or write metadata. Directory validation and
the subsequent inventory scan are necessarily best-effort: a concurrent change
to the prefix can still race them (TOCTOU), so scan an otherwise stable prefix.

Fresh package requests produce JSON schema v1. Existing-prefix scans produce
schema v2, whose context deliberately leaves unknown resolution fields as
`null` or empty values and never contains the raw prefix or site-packages
paths. Inspect `schema_version` before comparing results from the two input
modes. In prefix text output, `--bin` uses the heading `Binaries in prefix`;
generated script sizes can differ from a fresh temporary installation because
POSIX script shebangs can contain the installation path.

`--explain`, `--breakdown`, and `--contributions` are unavailable with prefix text output because
the original requested roots and resolver conditions are not known. With
`--json`, those presentation flags (and `--bin`) are accepted but ignored, so
all such option combinations produce the same schema v2 bytes.

If virtual environment creation or package installation fails, the command exits
with status 1 and shows a concise failure summary with the `uv` exit code,
without a Python traceback or raw `uv` diagnostic output. A wheel-only install
failure explains that a compatible wheel may be unavailable and directs you to
`--allow-build` only when you trust the package source and its build backend.

### Example

```bash
uv-packsize apache-airflow==3.0.0
```

### Multiple Packages

You can also specify multiple packages to calculate the total size of all of them combined.

```bash
uv-packsize 'iniconfig==2.0.0' six
```
```bash
Calculating size for 2 requested packages...
Creating virtual environment...
Installing 2 requested packages and their dependencies...
Analyzing sizes...

--- Package Sizes ---
Package                  Size
-------------------  --------
six                  37.25 KiB
iniconfig            12.88 KiB
-------------------  --------
Total Package Size   50.13 KiB

Total size:          50.13 KiB

Calculation complete.
```

### JSON output

Use `--json` to write the complete, versioned analysis result to standard
output. It is intended for recording, comparison, and further processing:

```bash
uv-packsize requests==2.32.5 --json > analysis.json
```

Successful JSON output conforms to the committed
[analysis result schema v1](./schemas/analysis-result-v1.schema.json). Its
top-level fields describe the schema version, measurement definition,
resolution context, resolved distributions and their file inventories,
warnings/completeness, duplicate ownership, and global/distribution totals.
Schema version 1 is a compatibility boundary; consumers should check
`schema_version` before interpreting a result.

The JSON representation is deliberately safe to share as a measurement record:
requirements are non-reversible summaries rather than their raw text, and it
does not contain requirement URLs, credentials, digests, raw local paths, or
raw symlink targets. File paths in the measured temporary environment remain
part of the inventory because they are needed to explain the measurement.

With `--json`, standard output contains exactly one JSON document and no
progress messages, text table, or completion message. Progress and sanitized
operational errors are written to standard error instead. A successful analysis
exits with status 0; an operational failure exits with status 1 and leaves
standard output empty; invalid command-line usage uses Click's status 2.
`--bin` is a text-presentation option and has no effect on JSON bytes, so
`--json --bin` is accepted but produces the same JSON as `--json`.
`--explain` is also text-only: `--json --explain` is accepted and produces
byte-identical output (including progress and errors) to `--json`, preserving
the schema v1 compatibility boundary.
`--breakdown` and `--contributions` follow the same rule, including when
combined with other text-only options:
all `--json` combinations preserve the same schema v1 bytes as `--json` alone.

### Baseline comparison

Record a schema v1 fresh-install measurement with `--json`, then compare a new
fresh measurement to that read-only file:

```bash
uv-packsize requests==2.32.5 --json > baseline.json
uv-packsize requests==2.32.5 --baseline baseline.json
uv-packsize requests==2.32.5 --baseline baseline.json --comparison-json
```

The default comparison writes only the text diff report to standard output.
`--comparison-json` instead writes one successful, versioned JSON document
conforming to the committed [comparison result schema v1](./schemas/comparison-result-v1.schema.json),
including its final newline. It is a closed `comparison-result-v1` contract;
consumers must check `schema_version` before interpreting it. This comparison
document is separate from analysis-result JSON v1/v2: it reports the baseline
and current global/distribution aggregates, every distribution change,
nonreconciliation, and completeness rather than a file inventory.

Comparison JSON exposes an opaque context fingerprint for correlation, not raw
requirements, paths, resolver observations, or the individual context
fingerprints. The two measurements must use the same measurement definition
and resolution context (including requirements, Python/platform fingerprints,
build policy, and resolver conditions). Existing-prefix schema v2 baselines
are deliberately not comparable yet. The baseline file is read once and never
modified.

The report shows both the deduplicated global logical-size change and the
distribution-owned aggregate change. They can differ when multiple
distributions own the same installed file: global totals count each canonical
file once, while distribution totals retain ownership. Incomplete but
comparable inputs still exit successfully and label their deltas as partial.

`--comparison-json` requires `--baseline` and is mutually exclusive with
`--json`; the existing `--baseline` exclusions for `--prefix`, `--bin`,
`--explain`, `--breakdown`, and `--contributions` also apply. Progress and
sanitized errors go to standard error. Both comparison forms exit 0 on a
completed comparison, including an incomplete comparison whose JSON
`completeness` and warning summaries describe the partial result. Regular
install or analysis failures exit 1; invalid usage exits 2; baseline load or
validation failures exit 3; and incompatible baselines exit 4. Every failure
leaves standard output empty, so comparison JSON can be consumed safely only
on success.

### Writing a baseline

For fresh-install measurements, `--write-baseline PATH` writes the same
readable schema v1 JSON document that `--json` emits. It is useful when the
measurement is both a CI artifact and the next comparison input:

```bash
uv-packsize requests==2.32.5 --json --write-baseline baseline.json
uv-packsize requests==2.32.5 --baseline baseline.json
```

On success, `--json --write-baseline` writes byte-identical JSON to stdout and
to the file (including its final newline). Text presentation options such as
`--bin`, `--explain`, `--breakdown`, and `--contributions` only affect the
report; they never change the saved baseline bytes. The baseline is rendered,
validated, and published before either report or JSON is written to stdout.

Publication is no-clobber by default: an existing target causes a sanitized
exit 3 error and is left untouched. Replace a known baseline only with the
explicit opt-in:

```bash
uv-packsize requests==2.32.5 --json \
  --write-baseline baseline.json --overwrite-baseline
```

`--overwrite-baseline` requires `--write-baseline`. Writing is fresh-only and
cannot be combined with `--prefix` or `--baseline` (and consequently not with
`--comparison-json`). In write mode all progress and `Calculation complete.`
go to stderr; stdout is only the successful final report or JSON. Render and
write failures also use exit 3, contain only a fixed `code` and `field`, and
leave stdout empty.

The atomic writer currently supports POSIX platforms only. It creates a 0600
temporary file in an existing trusted parent directory and atomically publishes
it without following symlinks or replacing a target unless overwrite was
requested. The parent-directory policy rejects symlinked, unsafe writable, or
otherwise untrusted traversal components; choose a normal directory you own.
Directory-entry durability after a successful publish is filesystem/platform
dependent even when directory fsync is available. On Windows and other
unsupported platforms, keep using the portable existing path:

```bash
uv-packsize requests==2.32.5 --json > baseline.json
```

### Size budgets

Apply an explicit size policy to a fresh-install analysis with a project file,
individual command-line limits, or both. There is no automatic `pyproject.toml`
discovery: `--budget-config` reads exactly the path supplied and uses only its
`[tool.uv-packsize.budget]` table.

```toml
[tool.uv-packsize.budget]
max_total_logical_bytes = 52428800
max_increase_logical_bytes = 1048576
incomplete_policy = "fail"
```

```bash
uv-packsize requests==2.32.5 --budget-config pyproject.toml
uv-packsize requests==2.32.5 --baseline baseline.json \
  --budget-config pyproject.toml --max-increase 524288
```

`--max-total` and `--max-increase` accept non-negative decimal bytes and apply
to canonical global logical bytes, never distribution-owned aggregates. A
policy file supplies the base policy; each explicitly supplied CLI field
overrides only its corresponding field, while unspecified fields remain from
the file. An absent budget table supplies no policy, while an explicit empty
table or `--incomplete-policy` alone is a valid no-op policy.

An increase limit requires `--baseline`; the comparison must pass the existing
schema-v1 compatibility checks before the delta can be evaluated. Total-only
policies do not use baseline size, completeness, or nonreconciliation as a
budget input. By default, a policy with a limit fails incomplete measurements;
`--incomplete-policy allow-partial` suppresses only that incomplete-result
violation and still evaluates observed total and increase limits.

Text output appends a Size Budget report to the regular analysis or comparison
report. A budget violation exits with status 5 after that completed text
report. With `--json` or `--comparison-json`, successful policy runs retain
the exact pre-existing JSON bytes, while a violation writes no standard output
and instead emits the safe budget report and summary on standard error before
exiting 5. A `--write-baseline` target is rendered and published only after the
policy passes, so a violation never creates or replaces it.

Budget policy inputs are unavailable with `--prefix`; existing-prefix JSON v2
is not retroactively budgeted. Invalid explicit policy sources and policy
fields use status 3 without echoing local paths or TOML values. Existing status
codes remain unchanged: operational failures use 1, usage errors 2, baseline
and policy-source failures 3, and incompatible baselines 4.

For CI, commit the policy in the project file and make the baseline an explicit
artifact or tracked file:

```bash
uv-packsize -p 3.12 --budget-config pyproject.toml \
  --baseline .ci/uv-packsize-baseline.json 'your-package==1.2.3'
```

### Dependency explanations

Pass `--explain` with text output to append requested-root status, dependency
attribution, and shortest installed dependency paths. The explanation is built
from the installed distributions' Core Metadata after the size measurement; it
is not a claim about resolver provenance. If installed metadata is missing,
invalid, or otherwise incomplete, the command still reports the size and adds
a sanitized graph-warning summary with warning-code counts.

Dependency paths explain which roots reach an installed distribution. Use
`--contributions` for the corresponding non-split byte view.

### Requested-root contributions

Pass `--contributions` with text output to append requested-root exclusive,
shared, and closure bytes; exact shared root-set buckets; and a reconciliation
to the global total. Reachability is derived from installed distributions'
Core Metadata, not resolver provenance. A closure includes every observed byte
reachable from that root, so closures for different roots must not be summed.
An exact shared root-set bucket is counted once globally, never once per root.

`exclusive` contains bytes reachable from exactly one recognized root;
`shared` contains bytes in observed root sets containing that root and at least
one other recognized root; and `closure = exclusive + shared`. This describes
the fixed, observed installed graph only. It is not a resolver counterfactual
about what would be installed if a root were removed.

Duplicate requested root inputs do not create bytes or root sets: they retain
their distinct 1-based input indices in the root row. If Core Metadata cannot
form a complete graph, contribution numbers and root-set details are marked
unavailable; the measured global footprint and its inventory completeness are
still reported. As with `--explain` and `--breakdown`, this text-only option
does not change JSON schema v1.

### Global footprint breakdown

Pass `--breakdown` with text output to append two global, deduplicated views of
the measured inventory. File Category Breakdown always shows all six stable
categories (`python`, `native`, `data`, `metadata`, `script`, and `other`),
including zero-sized rows. Dependency Size Attribution classifies the same
global bytes as `self`, `direct`, `transitive`, `unattributed`, or
`mixed-ownership`; a file claimed by more than one distribution is still
counted once globally.

The role breakdown is derived from the same installed Core Metadata graph used
by `--explain`, not from resolver provenance. If that graph is incomplete, the
category breakdown remains available while dependency-role sizes are marked
unavailable and a sanitized warning-code summary is shown. `--explain
--breakdown` prints the normal report once, then dependency explanations and
the footprint sections; any graph warning is shown once. JSON schema v1 is not
extended by these opt-in text outputs. `--contributions` follows them, with the
normal report rendered once and its contribution sections last.

## Measurement

`uv-packsize` creates a temporary virtual environment, installs all requested
packages and their resolved dependencies with `uv pip install`, and then scans
the installed distributions. The environment is removed after the command
finishes.

For each distribution, its `.dist-info/RECORD` file is the source of file
ownership. The measurement scope is the temporary environment prefix, not just
`site-packages`: RECORD-owned scripts, data files, and headers are included
when they resolve inside that prefix. Generated `.pyc` files matching recorded
Python source files are also included when present.

This is installed logical size: it is neither the compressed wheel or sdist
size nor the number of filesystem blocks allocated on disk. It sums the
filesystem-reported size of each included path and does not account for physical
storage savings from hardlinks, clones, or similar sharing.

The final `Total size` is derived from the included file inventory. If two
distributions claim the same installed file, that file is counted once in the
global total; `--breakdown` uses that same canonical global inventory rather
than adding distribution rows together. Missing RECORD files, missing installed
files, malformed metadata, and similar conditions produce an incomplete-analysis
warning rather than being silently treated as a complete result.

The total does not include:

- the Python interpreter or the virtual environment's base files;
- the `uv` cache;
- files not owned by an installed distribution's RECORD or conservative
  metadata fallback.

`--bin` is a presentation option. It moves RECORD-owned script files from the
package table into a separate `Binaries in .venv/bin` table; it never changes
the final global total or scans unowned virtual-environment boilerplate. For an
existing-prefix scan, the equivalent heading is `Binaries in prefix`.
Sizes use binary units: `KiB`, `MiB`, and `GiB` are powers of 1024.

### Current limitations

- Results depend on the selected Python version and platform, and on extras and
  dependency resolution. Compare results only when those conditions match.
- Multiple requested packages are installed into one environment. The current
  resolver normally installs a shared dependency once. `--explain` identifies
  direct, transitive, and shared installed dependencies and their paths;
  `--breakdown` describes global category and role totals; and
  `--contributions` provides a non-split, observed root-set byte view.
- Text output is intended for interactive use. For a versioned record with the
  measurement context needed for comparison, use `--json`.

### Installation safety

The default installer is wheel-only: it passes `--no-build` to `uv pip install`
and does not permit source builds. If no compatible wheel is available, the
command fails without running that distribution's build backend. It may reuse a
compatible wheel that was already built in the `uv` cache; the guarantee is that
this invocation does not build an sdist.

Use `--allow-build` only as an explicit permission to let `uv` build from
source when needed. A temporary virtual environment isolates the install
destination; it is not a security sandbox. When builds are allowed, third-party
build code runs with the current user's permissions and may access the
filesystem or network outside that environment. Use it only for packages and
package indexes you trust.

The JSON `context.build_policy` records the permission selected for the run
(`wheel-only` or `allow-build`). It does not claim which distributions actually
built; the tool does not infer that from `uv` diagnostics or cache contents.

Packages are installed into the command's temporary virtual environment, not
directly into an existing user or system Python environment.

## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment using uv:
```bash
make sync
```

To run the tests:
```bash
make test
```

To run all formatting and linting, type check:
```bash
make check
```

this also runs [cog](https://cog.readthedocs.io/en/latest/) on README.md and updates the help message inside it.
