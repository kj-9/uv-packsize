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
```

Comparison writes only the text diff report to standard output; progress and
errors go to standard error. The baseline file is never modified. The two
measurements must use the same measurement definition and resolution context
(including requirements, Python/platform fingerprints, build policy, and
resolver conditions). Existing-prefix schema v2 baselines are deliberately not
comparable yet.

The report shows both the deduplicated global logical-size change and the
distribution-owned aggregate change. They can differ when multiple
distributions own the same installed file: global totals count each canonical
file once, while distribution totals retain ownership. Incomplete but
comparable inputs still exit successfully and label their deltas as partial.

Comparison does not offer JSON output yet, so `--baseline` is mutually
exclusive with `--json`, `--prefix`, `--bin`, `--explain`, `--breakdown`, and
`--contributions`. A completed comparison (including an incomplete one) exits
0; regular install or analysis failures exit 1; invalid usage exits 2;
baseline load or validation failures exit 3; and incompatible baselines exit
4.

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
