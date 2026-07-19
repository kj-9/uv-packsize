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
Usage: uv-packsize [OPTIONS] PACKAGE_NAMES...

  Report the size of a Python package and its dependencies using uv.

Options:
  --version          Show the version and exit.
  --bin              Text output only: display RECORD-owned scripts separately
                     without changing the total.
  --json             Write the versioned analysis result as JSON to stdout.
  -p, --python TEXT  Specify the Python version for the virtual environment.
  --help             Show this message and exit.

```
<!-- [[[end]]] -->

You can also use:
```bash
python -m uv_packsize --help
```

If virtual environment creation or package installation fails, the command exits
with status 1 and shows a concise failure summary with the `uv` exit code,
without a Python traceback or raw `uv` diagnostic output.

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
global total and the text report explains the difference from the distribution
rows. Missing RECORD files, missing installed files, malformed metadata, and
similar conditions produce an incomplete-analysis warning rather than being
silently treated as a complete result.

The total does not include:

- the Python interpreter or the virtual environment's base files;
- the `uv` cache;
- files not owned by an installed distribution's RECORD or conservative
  metadata fallback.

`--bin` is a presentation option. It moves RECORD-owned script files from the
package table into a separate `Binaries in .venv/bin` table; it never changes
the final global total or scans unowned virtual-environment boilerplate.
Sizes use binary units: `KiB`, `MiB`, and `GiB` are powers of 1024.

### Current limitations

- Results depend on the selected Python version and platform, and on extras and
  dependency resolution. Compare results only when those conditions match.
- Multiple requested packages are installed into one environment. The current
  resolver normally installs a shared dependency once. The output does not
  distinguish direct, transitive, or shared dependencies, or attribute a shared
  dependency's size to individual root packages.
- Text output is intended for interactive use. For a versioned record with the
  measurement context needed for comparison, use `--json`.

### Installation safety

The current installer is not wheel-only. If resolution selects an sdist,
including when no compatible wheel is available, `uv pip install` may build it
and execute third-party build backend code. The temporary virtual environment
isolates the install destination; it is not a security sandbox. Build code runs
with the current user's permissions and may access the filesystem or network
outside that environment. Run the tool only for packages and package indexes
you trust.

A wheel-only default is a roadmap target, not current behavior.

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
