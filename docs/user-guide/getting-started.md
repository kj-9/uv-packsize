# Getting started

## Run it once

Use `uvx` to run the latest stable release without installing it permanently:

```bash
uvx uv-packsize requests
```

Pass one or more package requirements. Quote a requirement when your shell would otherwise interpret its characters:

```bash
uvx uv-packsize 'iniconfig==2.0.0' six
```

The report lists installed distributions and a deduplicated global total.

## Install it as a tool

For repeated use:

```bash
uv tool install uv-packsize
uv-packsize requests
```

`pip install uv-packsize` also works.

## Pick a Python version

Python can change what is resolved and measured. Make it explicit when recording or comparing results:

```bash
uvx uv-packsize --python 3.12 requests==2.32.5
```

The command uses a temporary environment and removes it when finished; it does not install requested packages into your active Python environment.

## Next step

- [Measure packages](measuring-packages.md) for package requests and output options.
- [Measure a locked project](locked-projects.md) for explicit `pyproject.toml` and `uv.lock` inputs.
