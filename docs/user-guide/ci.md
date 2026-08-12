# CI

For a locked project, commit a reviewed baseline and optional budget policy, then run a read-only comparison:

```bash
uvx uv-packsize \
  --project pyproject.toml --lockfile uv.lock \
  --baseline .ci/uv-packsize-baseline.json \
  --budget-config pyproject.toml \
  --comparison-json > comparison.json
```

The command does not create or refresh the baseline. Keep baseline updates as separate, reviewed changes.

## GitHub Actions example

```yaml
name: Dependency footprint

on:
  pull_request:
  push:

permissions:
  contents: read

jobs:
  dependency-footprint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Set up uv
        uses: astral-sh/setup-uv@v6
        with:
          version: "0.11.3"
      - name: Compare locked dependency footprint
        shell: bash
        run: |
          temporary_directory="$(mktemp -d)"
          trap 'rm -rf "$temporary_directory"' EXIT
          comparison_json="$temporary_directory/comparison.json"
          uvx uv-packsize --project pyproject.toml --lockfile uv.lock --baseline .ci/uv-packsize-baseline.json --budget-config pyproject.toml --comparison-json > "$comparison_json"
          python - "$comparison_json" >> "$GITHUB_STEP_SUMMARY" <<'PY'
          import json
          import sys

          with open(sys.argv[1], encoding="utf-8") as comparison_file:
              comparison = json.load(comparison_file)

          baseline_total = comparison["baseline"]["totals"]["global_logical_bytes"]
          current_total = comparison["current"]["totals"]["global_logical_bytes"]
          global_delta = comparison["changes"]["totals"]["global_logical_bytes_delta"]
          print("## Dependency footprint")
          print()
          print(f"- Input kind: `{comparison['context']['input_kind']}`")
          print(f"- Lock changed: `{comparison['context']['lock_changed']}`")
          print(f"- Baseline total: {baseline_total} bytes")
          print(f"- Current total: {current_total} bytes")
          print(f"- Change: {global_delta:+d} bytes")
          PY
```

This needs only `contents: read`, no secrets, write permissions, PR comments, or automatic baseline updates. The comparison JSON is private temporary data and the summary exposes only fixed schema fields and byte totals, not requirements, paths, or lock contents.
