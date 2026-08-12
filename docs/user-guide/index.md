<div class="landing-hero" markdown>

<p class="landing-kicker">Python dependency footprint</p>

# Know what your dependencies cost.

Measure the installed logical size of Python packages and their dependencies with [uv](https://docs.astral.sh/uv/). `uv-packsize` installs an isolated dependency set, attributes its files to distributions, and turns the result into a reviewable record.

[Get started](getting-started.md){ .md-button .md-button--primary }
[View the source](https://github.com/kj-9/uv-packsize){ .md-button }

</div>

<div class="grid cards" markdown>

-   :material-scale-balance: **Measure installed bytes**

    Report installed logical size—not a wheel download size or allocated disk usage. The Python interpreter, virtual-environment scaffolding, and uv cache are excluded.

-   :material-file-search-outline: **Explain the total**

    Inspect distributions, file categories, dependency paths, and root contributions to understand why a footprint changed.

-   :material-shield-check-outline: **Keep CI honest**

    Compare a locked project with a baseline and fail a build when a reviewed size budget is exceeded.

</div>

!!! tip "Start with one command"

    ```bash
    uvx uv-packsize requests
    ```

    Use [`uv tool install uv-packsize`](getting-started.md#install-it-as-a-tool) when you want a persistent command.

## From a quick check to a repeatable policy

<div class="landing-journey" markdown>

1.  **[Measure a package](measuring-packages.md)** to see its installed footprint.
2.  **[Analyze a locked project](locked-projects.md)** to measure the dependencies your project actually selected.
3.  **[Record a baseline and budget](baselines-and-budgets.md)** to make growth visible in CI.

</div>

Source builds are disabled by default. Read [Safety and limitations](reference/safety-and-limitations.md) before using `--allow-build`.
