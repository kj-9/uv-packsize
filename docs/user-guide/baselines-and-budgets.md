# Baselines and budgets

## Compare a baseline

Record a fresh package-request measurement, then compare the same kind of measurement:

```bash
uvx uv-packsize requests==2.32.5 --json > baseline.json
uvx uv-packsize requests==2.32.5 --baseline baseline.json
uvx uv-packsize requests==2.32.5 --baseline baseline.json --comparison-json
```

The default is a text diff; `--comparison-json` writes a versioned comparison document. Measurements must have compatible definitions and resolution contexts, including requirements, Python/platform fingerprints, build policy, and resolver conditions.

Comparisons are only supported within an input family: fresh-install schema v1 with v1, or project-lock schema v3 with v3. Existing-prefix schema v2 is not comparable yet. An incomplete but compatible comparison completes and labels its deltas as partial; an incompatible baseline exits with status 4.

## Write a baseline

For fresh-install or project/lock mode, save the same JSON emitted by `--json`:

```bash
uvx uv-packsize requests==2.32.5 --json --write-baseline baseline.json
```

Existing targets are left untouched unless replacement is explicit:

```bash
uvx uv-packsize requests==2.32.5 --json \
  --write-baseline baseline.json --overwrite-baseline
```

The atomic writer currently supports POSIX platforms only. On Windows and other unsupported platforms, use portable shell redirection: `uvx uv-packsize requests==2.32.5 --json > baseline.json`.

## Define a budget

```toml
[tool.uv-packsize.budget]
max_total_logical_bytes = 52428800
max_increase_logical_bytes = 1048576
incomplete_policy = "fail"
```

Pass the exact policy file; there is no automatic `pyproject.toml` discovery:

```bash
uvx uv-packsize requests==2.32.5 --budget-config pyproject.toml
uvx uv-packsize requests==2.32.5 --baseline baseline.json \
  --budget-config pyproject.toml --max-increase 524288
```

`--max-total` and `--max-increase` are non-negative byte limits on canonical global logical bytes. A command-line field overrides only that field from the file. An increase limit needs a compatible baseline.

A policy with a limit fails incomplete measurements by default. `--incomplete-policy allow-partial` suppresses only that incomplete-result violation; observed limits are still checked. A budget violation exits 5 and writes no standard output in JSON modes.
