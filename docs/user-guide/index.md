# uv-packsize

Measure the installed logical size of a Python package and its dependencies with [uv](https://docs.astral.sh/uv/).

```bash
uvx uv-packsize requests
```

The command creates an isolated temporary environment, installs the requested dependency set, and prints a report like this:

```text
--- Package Sizes ---
Package                 Size
------------------  --------
sample              1.50 KiB
------------------  --------
Total Package Size  1.50 KiB

Total size:  1.50 KiB
```

This is an actual report rendered from a fixed test fixture. Your package names, resolved dependencies, and sizes will differ.

## Common tasks

- [Get started](getting-started.md) — run it once or install it as a tool.
- [Measure packages](measuring-packages.md) — use text views, JSON, or an existing prefix.
- [Measure a locked project](locked-projects.md) — analyze explicit `pyproject.toml` and `uv.lock` inputs.
- [Compare a baseline or enforce a budget](baselines-and-budgets.md).
- [Add a CI check](ci.md).

The total is installed logical size, not a wheel download size or allocated disk usage. The Python interpreter, virtual-environment scaffolding, and uv cache are excluded. Source builds are disabled by default; see [Safety and limitations](reference/safety-and-limitations.md) before using `--allow-build`.
