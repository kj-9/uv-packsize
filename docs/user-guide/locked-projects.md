# Locked projects

Measure dependencies selected by one explicit `pyproject.toml` and `uv.lock`:

```bash
uvx uv-packsize \
  --project pyproject.toml \
  --lockfile uv.lock \
  --json > analysis.json
```

This mode does not discover a project from the working directory. It reads and validates the two supplied files, stages those exact contents in a private temporary directory, and runs a locked sync there.

## Select groups and extras

No dependency groups are selected by default:

```bash
uvx uv-packsize --project pyproject.toml --lockfile uv.lock --group test
uvx uv-packsize --project pyproject.toml --lockfile uv.lock --all-groups --extra docs
```

`--group` is repeatable; `--group` and `--all-groups` are mutually exclusive. Extras are repeatable. Group and extra names are normalized package names and must be declared consistently in both explicit inputs. In the supported single-root subset, `--workspace-member NAME` selects that member.

## Scope and boundaries

The local root project is deliberately not installed or measured. Its source tree and build configuration cannot be reproduced safely from lockfile bytes alone, and measuring it could execute local build code. This mode reports selected locked dependencies only.

Project/lock mode supports a conservative subset. Local-path, VCS, and unsupported workspace dependency sources are rejected rather than approximated. Positional package requirements, `--prefix`, prefix-layout options, `--explain`, `--breakdown`, and `--contributions` cannot be combined with it.

Project/lock analysis emits analysis-result schema v3. Its opaque `lock_identity` can correlate identical lock contents but does not expose the lock, paths, sources, URLs, credentials, or opaque uv identifiers. Treat it as correlation metadata when sharing results.

For a concise text view, add `--report rich`:

```bash
uvx uv-packsize --project pyproject.toml --lockfile uv.lock --report rich
```

The rich primary summary identifies the input as `project-lock` and reports the
selected build policy, completeness, totals, and five largest distributions
without showing versions or lock identity. When comparing a compatible
baseline, it also reports whether the opaque lock identity changed without
displaying the identity itself. This statement applies to the primary summary;
any appended legacy section keeps its existing disclosure contract.

Use a baseline from the same input family; see [Baselines and budgets](baselines-and-budgets.md).
