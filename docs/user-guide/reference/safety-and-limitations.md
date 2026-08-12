# Safety and limitations

## Installation safety

Package-request and project/lock measurement use a private temporary environment, not an existing user or system Python environment. The temporary install location is removed after completion.

The default is wheel-only: `uv-packsize` passes `--no-build` to `uv pip install` or private `uv sync`. If no compatible wheel is available, it fails without running that distribution's build backend. A compatible wheel already built in uv's cache can be reused; the guarantee is that this invocation does not build an sdist.

Use `--allow-build` only as explicit permission for source builds:

```bash
uvx uv-packsize --allow-build package-without-a-wheel
```

A temporary environment is not a security sandbox. Third-party build code runs with the current user's permissions and may access the filesystem or network outside that environment. Trust both the package source and its index before enabling this option.

The JSON context records `wheel-only` or `allow-build`. It does not claim which distributions actually built.

## Interpretation limits

- Logical bytes do not describe physical storage savings from hardlinks, clones, or similar sharing.
- Multiple requested packages share an environment. Use `--explain`, `--breakdown`, and `--contributions` to understand the observed graph; do not treat each package row as an independent installation.
- Dependency paths, roles, and root contributions come from installed Core Metadata. They describe the observed installation, not resolver decisions or a hypothetical uninstall.
- Existing-prefix analysis is read-only but cannot eliminate time-of-check/time-of-use races. Scan a prefix that is not being modified.
- Locked-project analysis supports a conservative subset and rejects unsupported sources instead of guessing. It measures locked dependencies, not the local root project's source tree.

Use JSON and its context and completeness fields when a result will become a durable record or comparison input.
