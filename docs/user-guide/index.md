# uv-packsize

Measure the installed logical size of a Python package and its dependencies with [uv](https://docs.astral.sh/uv/).

```bash
uvx uv-packsize requests
```

The command creates an isolated temporary environment, installs the requested dependency set, and prints a report like this:

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

This is an actual report rendered from a fixed test fixture. Your package names, resolved dependencies, and sizes will differ.

## Choose a measurement mode

| Mode | Use it when | Baseline and budget | Start here |
| --- | --- | --- | --- |
| Package requests | You want to measure one or more requirements now. | Supported for compatible fresh-install results. | [Measure packages](measuring-packages.md) |
| Locked project | You want the dependencies selected by explicit `pyproject.toml` and `uv.lock` files. | Supported for compatible project-lock results. | [Measure a locked project](locked-projects.md) |
| Existing prefix | You want to inspect an already-installed environment without changing it. | Not supported yet. | [Inspect an existing environment](measuring-packages.md#inspect-an-existing-environment-with-prefix) |

## Common tasks

- [Get started](getting-started.md) — run it once or install it as a tool.
- [Measure packages](measuring-packages.md) — use text views, JSON, or an existing prefix.
- [Measure a locked project](locked-projects.md) — analyze explicit `pyproject.toml` and `uv.lock` inputs.
- [Compare a baseline or enforce a budget](baselines-and-budgets.md).
- [Add a CI check](ci.md).

The total is installed logical size, not a wheel download size or allocated disk usage. The Python interpreter, virtual-environment scaffolding, and uv cache are excluded. Source builds are disabled by default; see [Safety and limitations](reference/safety-and-limitations.md) before using `--allow-build`.
