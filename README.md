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
  --bin              Include the size of binaries in the .venv/bin directory.
  -p, --python TEXT  Specify the Python version for the virtual environment.
  --help             Show this message and exit.

```
<!-- [[[end]]] -->

You can also use:
```bash
python -m uv_packsize --help
```

If virtual environment creation or package installation fails, the command exits
with status 1 and shows a concise `uv` diagnostic without a Python traceback.

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
Calculating size for iniconfig==2.0.0, six...
Creating virtual environment...
Installing iniconfig==2.0.0, six and its dependencies...
Analyzing sizes...

--- Package Sizes ---
Package                  Size
-------------------  --------
six                  37.25 KB
iniconfig            12.88 KB
-------------------  --------
Total Package Size   50.13 KB

Total size:          50.13 KB

Calculation complete.
```

## Measurement

`uv-packsize` creates a temporary virtual environment, installs all requested
packages and their resolved dependencies with `uv pip install`, and then scans
the installed distributions. The environment is removed after the command
finishes.

For each distribution, its `.dist-info/RECORD` file is the source of file
ownership. The default package total is the sum of the logical byte sizes
reported by the filesystem for existing `RECORD` paths that resolve inside the
environment's `site-packages`. Generated `.pyc` files matching recorded Python
source files are also included when present.

This is installed logical size: it is neither the compressed wheel or sdist
size nor the number of filesystem blocks allocated on disk. It sums the
filesystem-reported size of each included path and does not account for physical
storage savings from hardlinks, clones, or similar sharing.

The default total does not include:

- the Python interpreter or the virtual environment's base files;
- the `uv` cache;
- files recorded outside `site-packages`, including console scripts.

`--bin` separately scans regular, non-symlink files in the temporary
environment's Unix-style `bin` directory, excluding activation and other known
environment boilerplate scripts. It adds that separate binary total to the
reported overall total. It does not assign those files back to their owning
distributions.

### Current limitations

- `RECORD` paths outside `site-packages`, such as scripts, data, and headers,
  are currently skipped by the distribution analysis. Windows `Scripts` is not
  scanned by `--bin`.
- If a distribution has no `RECORD`, only files under its `.dist-info`
  directory are used as a fallback. The output does not currently report that
  the measurement is incomplete.
- A path listed in `RECORD` but missing from disk is silently skipped. Ownership
  duplicated across distributions is not globally deduplicated or reported as
  a warning.
- Values use a 1024-byte scale, but the current output labels them `KB` and
  `MB`. This known mismatch is planned to change to `KiB` and `MiB` in Phase 2.
- Results depend on the selected Python version and platform, and on extras and
  dependency resolution. Compare results only when those conditions match.
- Multiple requested packages are installed into one environment. The current
  resolver normally installs a shared dependency once, so it normally appears
  once in the combined total. The output does not distinguish direct,
  transitive, or shared dependencies, or attribute a shared dependency's size
  to individual root packages.
- The text output is not a reproducible analysis record. It does not preserve
  the resolved versions, Python and platform details, `uv` version, index and
  resolver settings, or whether the measurement was complete.

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
