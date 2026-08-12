# Measuring packages

## Measure a package set

```bash
uvx uv-packsize apache-airflow==3.0.0
uvx uv-packsize 'iniconfig==2.0.0' six
```

All requested packages and their resolved dependencies are installed together in one temporary environment. A shared dependency is installed once and counted once in the global total.

## Explain a total

Add text-only views when you need more context:

```bash
uvx uv-packsize requests --explain
uvx uv-packsize requests --breakdown
uvx uv-packsize 'package-a' 'package-b' --contributions
```

- `--explain` shows observed dependency paths and direct, transitive, and shared attribution from installed Core Metadata. It is not resolver provenance.
- `--breakdown` shows deduplicated global bytes by file category and, when the metadata graph is complete, dependency role.
- `--contributions` shows exclusive, shared, and closure bytes per requested root. A closure is not a hypothetical uninstall calculation, and closures must not be summed.

These options affect only the text presentation and do not change a JSON result.

## Save JSON

```bash
uvx uv-packsize requests==2.32.5 --json > analysis.json
```

On success, standard output is exactly one JSON document. Progress and sanitized operational errors go to standard error. Check `schema_version` and `context.input_kind` before interpreting a saved result.

## Inspect an existing environment

`--prefix` is read-only: it does not run Python, invoke uv, or change the prefix. Supply every site-packages directory relative to the prefix and declare its filesystem case rule:

```bash
uvx uv-packsize --prefix .venv \
  --site-packages lib/python3.12/site-packages \
  --case-rule sensitive --json > prefix-analysis.json
```

`--site-packages` can be repeated. Prefix scans use a distinct schema and do not support comparisons or budgets. Scan a stable prefix because a concurrent change can race validation and inventory collection.

`--bin` moves RECORD-owned scripts into a separate text table without changing the global total or JSON bytes.
