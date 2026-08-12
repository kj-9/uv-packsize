"""Click entry point for temporary-environment package-size analysis."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from uv_packsize.analysis import AnalysisContextError, analyze_installed_environment
from uv_packsize.baseline import (
    MAX_BASELINE_INTEGER,
    BaselineError,
    analysis_result_to_baseline,
    load_baseline,
)
from uv_packsize.baseline_write import (
    BaselineWriteError,
    render_fresh_baseline,
    render_project_lock_baseline,
    write_baseline,
)
from uv_packsize.budget import (
    BudgetEvaluation,
    BudgetEvaluationError,
    BudgetPolicy,
    IncompleteBudgetPolicy,
    evaluate_budget,
)
from uv_packsize.budget_config import BudgetPolicyConfigError
from uv_packsize.budget_config_source import (
    BudgetPolicySourceError,
    load_budget_policy,
)
from uv_packsize.budget_render import render_budget_report
from uv_packsize.comparison_json_render import render_comparison_json
from uv_packsize.dependency_paths import explain_dependency_paths
from uv_packsize.diff import IncompatibleComparisonError, compare_baselines
from uv_packsize.diff_render import render_diff_report
from uv_packsize.environment import (
    EnvironmentDiscoveryError,
    discover_installed_environment,
)
from uv_packsize.existing_prefix import (
    ExistingPrefixDiscoveryError,
    discover_existing_prefix,
)
from uv_packsize.explanation import render_explanation_sections
from uv_packsize.footprint import summarize_footprint
from uv_packsize.footprint_render import (
    render_footprint_sections,
)
from uv_packsize.installed_metadata import (
    InstalledMetadataAdapterError,
    build_installed_dependency_graph,
)
from uv_packsize.inventory import InventoryError
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import (
    BuildPolicy,
    CaseRule,
    PathFlavor,
    ProjectLockContext,
    normalize_distribution_name,
)
from uv_packsize.project_comparison_json_render import (
    render_project_lock_comparison_json,
)
from uv_packsize.project_lock_installer import (
    ProjectLockInstallError,
    install_validated_project_lock,
)
from uv_packsize.project_lock_json_render import render_project_lock_analysis_json
from uv_packsize.project_lock_reader import (
    ProjectLockInputError,
    _read_validated_project_lock,
)
from uv_packsize.render import render_analysis_report
from uv_packsize.rich_report import (
    project_rich_analysis,
    project_rich_comparison,
    render_rich_analysis_report,
    render_rich_comparison_report,
)
from uv_packsize.root_contribution_render import render_root_contribution_sections
from uv_packsize.root_contributions import summarize_root_contributions

_UV_VERSION = re.compile(
    r"uv\s+([0-9]+(?:\.[0-9]+)+(?:[-+][A-Za-z0-9.-]+)?)"
    r"(?:\s+\([A-Za-z0-9 ._+-]+\))?"
)


class UvCommandError(Exception):
    """A failed uv command with its diagnostic output preserved."""

    def __init__(self, command, exit_code, stdout, stderr):
        self.command = tuple(command)
        self.exit_code = exit_code
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        super().__init__(f"uv command failed with exit code {exit_code}")


class UvVersionError(ValueError):
    """The ``uv --version`` response was not a safe version value."""


class _BaselineClickError(click.ClickException):
    """A typed public boundary for safe baseline failures."""

    exit_code = 3


class _ComparisonClickError(click.ClickException):
    """A typed public boundary for safe comparison incompatibilities."""

    exit_code = 4


class _BudgetClickError(click.ClickException):
    """A typed public boundary for completed budget-policy violations."""

    exit_code = 5


def _project_input_failure_message(error: ProjectLockInputError) -> str:
    return (
        "Could not read project lock input "
        f"(code={error.reason.value}, field={error.field.value})."
    )


def _project_install_failure_message(error: ProjectLockInstallError) -> str:
    return f"Could not install project lock (reason={error.reason.value})."


def _baseline_failure_message(error: BaselineError) -> str:
    """Return a diagnostic containing only fixed baseline identifiers."""

    if error.field == "file":
        return f"Could not load baseline (code={error.code}, field=file)."
    return f"Could not validate baseline (code={error.code}, field={error.field})."


def _comparison_failure_message(error: IncompatibleComparisonError) -> str:
    """Return the fixed comparison reason without baseline contents."""

    return f"Baselines cannot be compared (reason={error.reason.value})."


def _baseline_write_failure_message(error: BaselineWriteError) -> str:
    """Return the deliberately path-free baseline publication diagnostic."""

    return f"Could not write baseline (code={error.code}, field={error.field})."


def _budget_source_failure_message(error: Exception) -> str:
    """Return a fixed diagnostic without source paths or configuration values."""

    if isinstance(error, BudgetPolicySourceError):
        return (
            "Could not load budget policy "
            f"(code={error.reason.value}, field={error.section.value})."
        )
    if isinstance(error, BudgetPolicyConfigError):
        field = "policy" if error.field is None else error.field.value
        return (
            "Could not validate budget policy "
            f"(code={error.reason.value}, field={field})."
        )
    raise TypeError("error must be an expected budget source failure")


def _run_uv(command):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise UvCommandError(command, 127, "", str(error)) from error

    if result.returncode != 0:
        raise UvCommandError(
            command,
            result.returncode,
            result.stdout,
            result.stderr,
        )
    return result


def _create_venv(venv_dir, python=None, *, err=False):
    click.echo("Creating virtual environment...", err=err)

    command = ["uv", "venv"]
    if python:
        command.extend(["--python", python])
    command.append(venv_dir)
    _run_uv(command)

    python_executable = os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(python_executable):  # For Windows
        python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
    return python_executable


def _install_package(
    python_executable,
    package_names,
    *,
    build_policy: BuildPolicy,
    err=False,
):
    """Install requirements according to the explicit build permission."""
    package_count = len(package_names)
    package_label = "package" if package_count == 1 else "packages"
    possessive = "its" if package_count == 1 else "their"
    click.echo(
        f"Installing {package_count} requested {package_label} and {possessive} dependencies...",
        err=err,
    )
    install_command = [
        "uv",
        "pip",
        "install",
        "--python",
        python_executable,
    ]
    if build_policy is BuildPolicy.WHEEL_ONLY:
        install_command.append("--no-build")
    elif build_policy is not BuildPolicy.ALLOW_BUILD:
        raise TypeError("build_policy must be a BuildPolicy")
    install_command.extend(package_names)

    _run_uv(install_command)


def _uv_version() -> str:
    """Return a validated version from the installed ``uv`` executable."""

    result = _run_uv(["uv", "--version"])
    match = _UV_VERSION.fullmatch(result.stdout.strip())
    if match is None:
        raise UvVersionError("invalid uv version output")
    return match.group(1)


def _command_failure_message(error, *, build_policy: BuildPolicy | None = None):
    """Return a public summary without forwarding uv's untrusted diagnostics."""

    arguments = error.command[1:]
    if arguments[:1] == ("venv",):
        summary = "Could not create the virtual environment"
    elif arguments[:2] == ("pip", "install"):
        if build_policy is BuildPolicy.WHEEL_ONLY:
            return (
                "Could not install the requested packages with the wheel-only policy "
                f"(uv exit code {error.exit_code}). A compatible wheel may be "
                "unavailable; retry with --allow-build only if you trust the package "
                "source and its build backend."
            )
        summary = "Could not install the requested packages"
    elif arguments == ("--version",):
        summary = "Could not determine the uv version"
    else:
        summary = "uv command failed"

    return f"{summary} (uv exit code {error.exit_code})."


def _analysis_failure_message(error: Exception) -> str:
    """Produce a stable CLI diagnostic without filesystem or probe details."""

    if isinstance(error, EnvironmentDiscoveryError):
        return f"Could not inspect the temporary environment ({error.code.value})."
    if isinstance(error, AnalysisContextError):
        return f"Could not analyze the installed environment ({error.code.value})."
    if isinstance(error, InventoryError):
        code = getattr(error, "code", None)
        if code is not None:
            return f"Could not analyze installed files ({code.value})."
        return "Could not analyze installed files."
    raise TypeError("error must be an expected analysis failure")


def _prefix_analysis_failure_message(error: Exception) -> str:
    """Produce a fixed diagnostic for an existing-prefix inventory failure."""

    if isinstance(error, AnalysisContextError):
        return f"Could not analyze the existing prefix ({error.code.value})."
    if isinstance(error, InventoryError):
        code = getattr(error, "code", None)
        if code is not None:
            return f"Could not analyze existing prefix files ({code.value})."
        return "Could not analyze existing prefix files."
    raise TypeError("error must be an expected prefix analysis failure")


def _prefix_discovery_failure_message(error: ExistingPrefixDiscoveryError) -> str:
    """Return the stable public error without retaining a local path."""

    return f"Could not inspect the existing prefix ({error.code.value})."


def _host_path_flavor() -> PathFlavor:
    return PathFlavor.WINDOWS if os.name == "nt" else PathFlavor.POSIX


def _explanation_failure_message(error: Exception) -> str:
    """Return a fixed public diagnostic for safe explanation failures.

    Installed metadata and graph validation can carry untrusted package
    metadata or filesystem details in their implementation exceptions.  The
    CLI's opt-in presentation deliberately exposes neither.
    """

    if isinstance(error, (InstalledMetadataAdapterError, InventoryError, ValueError)):
        return "Could not explain installed dependencies."
    raise TypeError("error must be an expected explanation failure")


@click.command()
@click.version_option()
@click.argument("package_names", nargs=-1, required=False)
@click.option(
    "--prefix",
    type=click.Path(path_type=Path),
    help="Analyze an existing prefix without running or changing it.",
)
@click.option(
    "--project",
    type=click.Path(path_type=Path),
    help="Analyze one explicit pyproject.toml with an explicit uv.lock.",
)
@click.option(
    "--lockfile",
    type=click.Path(path_type=Path),
    help="Explicit uv.lock used with --project.",
)
@click.option(
    "--workspace-member",
    help="Select the explicit workspace member by normalized package name.",
)
@click.option(
    "--group",
    "dependency_groups",
    multiple=True,
    help="Include one explicit dependency group (repeatable).",
)
@click.option(
    "--all-groups",
    is_flag=True,
    help="Include all validated dependency groups.",
)
@click.option(
    "--extra",
    "extras",
    multiple=True,
    help="Include one explicit extra (repeatable).",
)
@click.option(
    "--baseline",
    type=click.Path(path_type=Path),
    help="Read a baseline JSON file and report its diff from a fresh or project analysis.",
)
@click.option(
    "--write-baseline",
    "write_baseline_path",
    type=click.Path(path_type=Path),
    help="Atomically write the fresh or project analysis JSON to PATH.",
)
@click.option(
    "--overwrite-baseline",
    is_flag=True,
    help="Replace an existing --write-baseline target explicitly.",
)
@click.option(
    "--site-packages",
    "site_packages_relative",
    multiple=True,
    metavar="REL",
    help="Relative site-packages directory inside --prefix (repeatable).",
)
@click.option(
    "--case-rule",
    type=click.Choice([rule.value for rule in CaseRule]),
    help="Target filesystem case rule required with --prefix.",
)
@click.option(
    "--bin",
    is_flag=True,
    help="Text output only: display RECORD-owned scripts separately without changing the total.",
)
@click.option(
    "--allow-build",
    is_flag=True,
    help="Allow source builds during installation; disabled by default.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Write the versioned analysis result as JSON to stdout.",
)
@click.option(
    "--comparison-json",
    is_flag=True,
    help="Write the versioned baseline comparison result as JSON to stdout.",
)
@click.option(
    "--report",
    "report_format",
    type=click.Choice(["standard", "rich"]),
    default="standard",
    hidden=True,
)
@click.option(
    "--budget-config",
    type=click.Path(path_type=Path),
    help="Read budget policy from [tool.uv-packsize.budget] in PATH.",
)
@click.option(
    "--max-total",
    type=click.IntRange(min=0, max=MAX_BASELINE_INTEGER),
    metavar="BYTES",
    help="Maximum canonical global logical size in bytes.",
)
@click.option(
    "--max-increase",
    type=click.IntRange(min=0, max=MAX_BASELINE_INTEGER),
    metavar="BYTES",
    help="Maximum canonical global logical-size increase in bytes.",
)
@click.option(
    "--incomplete-policy",
    type=click.Choice([policy.value for policy in IncompleteBudgetPolicy]),
    help="Budget handling for incomplete measurements.",
)
@click.option(
    "--explain",
    is_flag=True,
    help=(
        "Text output only: show installed-metadata dependency paths and attribution. "
        "Unavailable with --prefix or --project."
    ),
)
@click.option(
    "--breakdown",
    is_flag=True,
    help=(
        "Text output only: show global file-category and dependency-role sizes. "
        "Unavailable with --prefix or --project."
    ),
)
@click.option(
    "--contributions",
    is_flag=True,
    help=(
        "Text output only: show non-split requested-root byte contributions. "
        "Unavailable with --prefix or --project."
    ),
)
@click.option(
    "-p",
    "--python",
    "python_version",
    help="Specify the Python version for the virtual environment.",
)
def cli(  # noqa: PLR0912, PLR0913, PLR0915
    package_names,
    prefix,
    project,
    lockfile,
    workspace_member,
    dependency_groups,
    all_groups,
    extras,
    baseline,
    write_baseline_path,
    overwrite_baseline,
    site_packages_relative,
    case_rule,
    bin,
    json_output,
    comparison_json,
    report_format,
    budget_config,
    max_total,
    max_increase,
    incomplete_policy,
    explain,
    breakdown,
    contributions,
    allow_build,
    python_version,
):
    """Report the size of a Python package and its dependencies using uv."""
    project_mode = project is not None or lockfile is not None
    _validate_project_lock_options(
        project=project,
        lockfile=lockfile,
        package_names=package_names,
        prefix=prefix,
        site_packages_relative=site_packages_relative,
        case_rule=case_rule,
        workspace_member=workspace_member,
        dependency_groups=dependency_groups,
        all_groups=all_groups,
        extras=extras,
        explain=explain,
        breakdown=breakdown,
        contributions=contributions,
    )
    if comparison_json and baseline is None:
        raise click.UsageError("--comparison-json requires --baseline.")
    if overwrite_baseline and write_baseline_path is None:
        raise click.UsageError("--overwrite-baseline requires --write-baseline.")
    if write_baseline_path is not None:
        _validate_write_baseline_options(prefix=prefix, baseline=baseline)

    _validate_budget_prefix_options(
        prefix=prefix,
        budget_config=budget_config,
        max_total=max_total,
        max_increase=max_increase,
        incomplete_policy=incomplete_policy,
    )

    if baseline is not None:
        _validate_baseline_options(
            prefix=prefix,
            json_output=json_output,
            bin=bin,
            explain=explain,
            breakdown=breakdown,
            contributions=contributions,
        )
        _validate_baseline_fresh_usage(
            package_names=package_names,
            site_packages_relative=site_packages_relative,
            case_rule=case_rule,
            project_mode=project_mode,
        )
    policy = _load_effective_budget_policy(
        budget_config=budget_config,
        max_total=max_total,
        max_increase=max_increase,
        incomplete_policy=incomplete_policy,
    )
    if policy is not None and policy.max_increase_logical_bytes is not None:
        if baseline is None:
            raise click.UsageError("--max-increase requires --baseline.")

    if baseline is not None:
        try:
            comparison_baseline = load_baseline(baseline)
        except BaselineError as error:
            raise _BaselineClickError(_baseline_failure_message(error)) from None
    else:
        comparison_baseline = None

    if prefix is not None:
        _validate_prefix_options(
            package_names=package_names,
            site_packages_relative=site_packages_relative,
            case_rule=case_rule,
            allow_build=allow_build,
            python_version=python_version,
            explain=explain,
            breakdown=breakdown,
            contributions=contributions,
            json_output=json_output,
        )
        _run_prefix_analysis(
            prefix=prefix,
            site_packages_relative=site_packages_relative,
            case_rule=CaseRule(case_rule),
            bin=bin,
            json_output=json_output,
            report_format=report_format,
        )
        return

    if project_mode:
        _run_project_lock_analysis(
            project=project,
            lockfile=lockfile,
            workspace_member=workspace_member,
            dependency_groups=dependency_groups,
            all_groups=all_groups,
            extras=extras,
            baseline=comparison_baseline,
            write_baseline_path=write_baseline_path,
            overwrite_baseline=overwrite_baseline,
            json_output=json_output,
            comparison_json=comparison_json,
            allow_build=allow_build,
            python_version=python_version,
            policy=policy,
            bin=bin,
            report_format=report_format,
        )
        return

    if site_packages_relative or case_rule is not None:
        raise click.UsageError("--site-packages and --case-rule require --prefix.")
    if not package_names:
        raise click.UsageError("Missing argument 'PACKAGE_NAMES...'.")
    if not shutil.which("uv"):
        raise click.ClickException(
            "'uv' command not found. Please install it first. "
            "See https://github.com/astral-sh/uv for installation instructions."
        )

    package_count = len(package_names)
    package_label = "package" if package_count == 1 else "packages"
    compare_mode = comparison_baseline is not None
    write_mode = write_baseline_path is not None
    progress_to_stderr = json_output or compare_mode or write_mode
    click.echo(
        f"Calculating size for {package_count} requested {package_label}...",
        err=progress_to_stderr,
    )
    build_policy = BuildPolicy.ALLOW_BUILD if allow_build else BuildPolicy.WHEEL_ONLY

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        try:
            python_executable = _create_venv(
                venv_dir, python_version, err=progress_to_stderr
            )
            _install_package(
                python_executable,
                package_names,
                build_policy=build_policy,
                err=progress_to_stderr,
            )
            uv_version = _uv_version()
        except UvCommandError as error:
            raise click.ClickException(
                _command_failure_message(error, build_policy=build_policy)
            ) from None
        except UvVersionError:
            raise click.ClickException("Could not determine the uv version.") from None

        click.echo("Analyzing sizes...", err=progress_to_stderr)
        try:
            environment = discover_installed_environment(
                venv_path=Path(venv_dir),
                venv_python=Path(python_executable),
                requirements=tuple(package_names),
                uv_version=uv_version,
                build_policy=build_policy,
                compile_bytecode=False,
                extras=(),
                index_identifiers=(),
                resolution_strategy="highest",
            )
            result = analyze_installed_environment(
                context=environment.context,
                layouts=environment.layouts,
            )
        except (
            EnvironmentDiscoveryError,
            AnalysisContextError,
            InventoryError,
        ) as error:
            raise click.ClickException(_analysis_failure_message(error)) from None

        current_baseline = None
        diff = None
        if comparison_baseline is not None or policy is not None:
            try:
                current_baseline = analysis_result_to_baseline(result)
            except ValueError:
                raise click.ClickException(
                    "Could not evaluate the analysis result."
                ) from None

        if comparison_baseline is not None:
            click.echo("Comparing with baseline...", err=True)
            try:
                assert current_baseline is not None
                diff = compare_baselines(comparison_baseline, current_baseline)
            except IncompatibleComparisonError as error:
                raise _ComparisonClickError(
                    _comparison_failure_message(error)
                ) from None
            except ValueError:
                raise click.ClickException(
                    "Could not compare the analysis result."
                ) from None

        budget_evaluation = _evaluate_budget_policy(
            policy=policy,
            current_baseline=current_baseline,
            comparison=diff,
        )

        if comparison_baseline is not None:
            assert diff is not None
            if comparison_json:
                if budget_evaluation is not None and not budget_evaluation.passed:
                    _raise_budget_violation(budget_evaluation, json_output=True)
                try:
                    click.echo(render_comparison_json(diff), nl=False)
                except (TypeError, ValueError):
                    raise click.ClickException(
                        "Could not render comparison JSON."
                    ) from None
            else:
                report = _render_comparison_report(diff, report_format=report_format)
                if budget_evaluation is not None:
                    report = "\n\n".join(
                        (report, render_budget_report(budget_evaluation))
                    )
                click.echo(report)
                if budget_evaluation is not None and not budget_evaluation.passed:
                    _raise_budget_violation(budget_evaluation, json_output=False)
            return

        # JSON v1 remains a strict compatibility boundary.  In particular, do
        # not inspect installed metadata when text-only options are combined
        # with JSON: this keeps stdout, stderr, and failures identical to
        # --json alone.
        if json_output:
            if budget_evaluation is not None and not budget_evaluation.passed:
                _raise_budget_violation(budget_evaluation, json_output=True)
            if write_mode:
                try:
                    payload = render_fresh_baseline(result)
                    write_baseline(
                        write_baseline_path, payload, overwrite=overwrite_baseline
                    )
                except BaselineWriteError as error:
                    raise _BaselineClickError(
                        _baseline_write_failure_message(error)
                    ) from None
                click.echo(payload.decode("utf-8"), nl=False)
            else:
                click.echo(render_analysis_json(result), nl=False)
        elif explain or breakdown or contributions:
            if explain:
                click.echo("Explaining dependencies...", err=write_mode)
            try:
                graph = build_installed_dependency_graph(result, environment)
                explained = explain_dependency_paths(result, graph)
            except (InstalledMetadataAdapterError, InventoryError, ValueError) as error:
                raise click.ClickException(
                    _explanation_failure_message(error)
                ) from None
            # Footprint aggregation is an internal invariant boundary, not an
            # installed-metadata adapter boundary.  Do not turn its failures
            # into a sanitized user-facing metadata error.
            footprint = summarize_footprint(explained) if breakdown else None
            contributions_result = (
                summarize_root_contributions(explained) if contributions else None
            )
            sections = []
            graph_warning_rendered = False
            if explain:
                sections.extend(render_explanation_sections(explained))
                graph_warning_rendered = True
            if breakdown:
                assert footprint is not None
                sections.extend(
                    render_footprint_sections(
                        footprint,
                        include_graph_warning_summary=not graph_warning_rendered,
                    )
                )
                graph_warning_rendered = True
            if contributions:
                assert contributions_result is not None
                sections.extend(
                    render_root_contribution_sections(
                        contributions_result,
                        include_graph_warning_summary=not graph_warning_rendered,
                    )
                )
            report = "\n\n".join(
                (
                    _render_primary_analysis_report(
                        result,
                        report_format=report_format,
                        show_scripts=bin,
                    ),
                    *sections,
                )
            )
            if budget_evaluation is not None:
                report = "\n\n".join((report, render_budget_report(budget_evaluation)))
            if budget_evaluation is not None and not budget_evaluation.passed:
                click.echo(report)
                _raise_budget_violation(budget_evaluation, json_output=False)
            _write_fresh_baseline_if_requested(
                write_baseline_path, result, overwrite_baseline
            )
            click.echo(report)
        else:
            report = _render_primary_analysis_report(
                result,
                report_format=report_format,
                show_scripts=bin,
            )
            if budget_evaluation is not None:
                report = "\n\n".join((report, render_budget_report(budget_evaluation)))
            if budget_evaluation is not None and not budget_evaluation.passed:
                click.echo(report)
                _raise_budget_violation(budget_evaluation, json_output=False)
            _write_fresh_baseline_if_requested(
                write_baseline_path, result, overwrite_baseline
            )
            click.echo(report)

    click.echo("\nCalculation complete.", err=json_output or write_mode)


def _write_fresh_baseline_if_requested(
    path: Path | None, result, overwrite: bool
) -> None:
    """Render and publish only after all text presentation has succeeded."""

    if path is None:
        return
    try:
        payload = render_fresh_baseline(result)
        write_baseline(path, payload, overwrite=overwrite)
    except BaselineWriteError as error:
        raise _BaselineClickError(_baseline_write_failure_message(error)) from None


def _render_primary_analysis_report(
    result,
    *,
    report_format: str,
    show_scripts: bool,
    binaries_title: str = "Binaries in .venv/bin",
) -> str:
    """Render one text primary report without changing the standard contract."""

    if report_format == "standard":
        return render_analysis_report(
            result, show_scripts=show_scripts, binaries_title=binaries_title
        )
    if report_format != "rich":
        raise ValueError("report_format must be a supported report format")
    try:
        report = render_rich_analysis_report(project_rich_analysis(result))
        if show_scripts:
            report = "\n\n".join(
                (report, _binary_section(result, binaries_title=binaries_title))
            )
        return report
    except (TypeError, ValueError):
        raise click.ClickException("Could not render rich report.") from None


def _render_comparison_report(diff, *, report_format: str) -> str:
    """Render one text comparison report without changing the standard contract."""

    if report_format == "standard":
        return render_diff_report(diff)
    if report_format != "rich":
        raise ValueError("report_format must be a supported report format")
    try:
        return render_rich_comparison_report(project_rich_comparison(diff))
    except (TypeError, ValueError):
        raise click.ClickException("Could not render rich report.") from None


def _binary_section(result, *, binaries_title: str) -> str:
    """Reuse the established binary table without including the standard primary."""

    sections = render_analysis_report(
        result, show_scripts=True, binaries_title=binaries_title
    ).split("\n\n")
    heading = f"--- {binaries_title} ---"
    for section in sections:
        if section.startswith(heading):
            return section
    raise ValueError("could not isolate the binary report section")


def _validate_budget_prefix_options(  # noqa: PLR0913
    *,
    prefix: Path | None,
    budget_config: Path | None,
    max_total: int | None,
    max_increase: int | None,
    incomplete_policy: str | None,
) -> None:
    """Reject policy inputs for existing-prefix analysis before config I/O."""

    if prefix is None:
        return
    for specified, option in (
        (budget_config is not None, "--budget-config"),
        (max_total is not None, "--max-total"),
        (max_increase is not None, "--max-increase"),
        (incomplete_policy is not None, "--incomplete-policy"),
    ):
        if specified:
            raise click.UsageError(f"{option} cannot be used with --prefix.")


def _load_effective_budget_policy(  # noqa: PLR0913
    *,
    budget_config: Path | None,
    max_total: int | None,
    max_increase: int | None,
    incomplete_policy: str | None,
) -> BudgetPolicy | None:
    """Read one explicit source and apply only explicitly supplied CLI fields."""

    try:
        source_policy = (
            None if budget_config is None else load_budget_policy(budget_config)
        )
    except (BudgetPolicySourceError, BudgetPolicyConfigError) as error:
        raise _BaselineClickError(_budget_source_failure_message(error)) from None

    cli_policy_specified = any(
        value is not None for value in (max_total, max_increase, incomplete_policy)
    )
    if source_policy is None and not cli_policy_specified:
        return None

    base = BudgetPolicy() if source_policy is None else source_policy
    try:
        return BudgetPolicy(
            max_total_logical_bytes=(
                base.max_total_logical_bytes if max_total is None else max_total
            ),
            max_increase_logical_bytes=(
                base.max_increase_logical_bytes
                if max_increase is None
                else max_increase
            ),
            incomplete_policy=(
                base.incomplete_policy
                if incomplete_policy is None
                else IncompleteBudgetPolicy(incomplete_policy)
            ),
        )
    except (TypeError, ValueError):
        raise click.ClickException("Could not evaluate budget policy input.") from None


def _evaluate_budget_policy(
    *,
    policy: BudgetPolicy | None,
    current_baseline,
    comparison,
) -> BudgetEvaluation | None:
    """Evaluate the effective policy after fresh analysis and comparison succeed."""

    if policy is None:
        return None
    assert current_baseline is not None
    try:
        return evaluate_budget(current_baseline, policy, comparison=comparison)
    except (BudgetEvaluationError, TypeError, ValueError):
        raise click.ClickException("Could not evaluate size budget.") from None


def _raise_budget_violation(evaluation: BudgetEvaluation, *, json_output: bool) -> None:
    """Fail a completed policy decision without exposing new JSON contracts."""

    if json_output:
        click.echo(render_budget_report(evaluation), err=True)
    raise _BudgetClickError("Size budget was exceeded.")


def _validate_write_baseline_options(
    *, prefix: Path | None, baseline: Path | None
) -> None:
    """Reject non-fresh modes before any baseline or external I/O."""

    if prefix is not None:
        raise click.UsageError("--prefix cannot be used with --write-baseline.")
    if baseline is not None:
        raise click.UsageError("--baseline cannot be used with --write-baseline.")


def _validate_baseline_options(  # noqa: PLR0913
    *,
    prefix: Path | None,
    json_output: bool,
    bin: bool,
    explain: bool,
    breakdown: bool,
    contributions: bool,
) -> None:
    """Reject comparison-incompatible options before file or process I/O."""

    for enabled, option in (
        (prefix is not None, "--prefix"),
        (json_output, "--json"),
        (bin, "--bin"),
        (explain, "--explain"),
        (breakdown, "--breakdown"),
        (contributions, "--contributions"),
    ):
        if enabled:
            raise click.UsageError(f"{option} cannot be used with --baseline.")


def _validate_baseline_fresh_usage(
    *,
    package_names: tuple[str, ...],
    site_packages_relative: tuple[str, ...],
    case_rule: str | None,
    project_mode: bool,
) -> None:
    """Apply fresh-input usage checks before reading a comparison baseline."""

    if site_packages_relative or case_rule is not None:
        raise click.UsageError("--site-packages and --case-rule require --prefix.")
    if not package_names and not project_mode:
        raise click.UsageError("Missing argument 'PACKAGE_NAMES...'.")


def _validate_project_lock_options(  # noqa: PLR0913
    *,
    project: Path | None,
    lockfile: Path | None,
    package_names: tuple[str, ...],
    prefix: Path | None,
    site_packages_relative: tuple[str, ...],
    case_rule: str | None,
    workspace_member: str | None,
    dependency_groups: tuple[str, ...],
    all_groups: bool,
    extras: tuple[str, ...],
    explain: bool,
    breakdown: bool,
    contributions: bool,
) -> None:
    """Guard project mode completely before file, config, or process I/O."""

    project_mode = project is not None or lockfile is not None
    selection_specified = bool(
        workspace_member is not None or dependency_groups or all_groups or extras
    )
    if not project_mode:
        if selection_specified:
            raise click.UsageError(
                "--workspace-member, --group, --all-groups, and --extra require "
                "--project and --lockfile."
            )
        return
    if project is None or lockfile is None:
        raise click.UsageError("--project and --lockfile must be used together.")
    if package_names:
        raise click.UsageError("PACKAGE_NAMES cannot be used with --project.")
    if prefix is not None:
        raise click.UsageError("--prefix cannot be used with --project.")
    if site_packages_relative or case_rule is not None:
        raise click.UsageError("--site-packages and --case-rule require --prefix.")
    if dependency_groups and all_groups:
        raise click.UsageError("--group cannot be used with --all-groups.")
    for enabled, option in (
        (explain, "--explain"),
        (breakdown, "--breakdown"),
        (contributions, "--contributions"),
    ):
        if enabled:
            raise click.UsageError(f"{option} cannot be used with --project.")
    _validate_project_lock_selector(workspace_member, "--workspace-member")
    for group in dependency_groups:
        _validate_project_lock_selector(group, "--group")
    for extra in extras:
        _validate_project_lock_selector(extra, "--extra")


def _validate_project_lock_selector(value: str | None, option: str) -> None:
    """Reject unsafe selector syntax before reading project/lock inputs."""

    if value is None:
        return
    try:
        normalize_distribution_name(value)
    except (TypeError, ValueError):
        raise click.UsageError(f"{option} must be a safe package name.") from None


def _project_lock_context(selection, environment, *, build_policy: BuildPolicy):
    """Project a probed temporary prefix into the safe schema-v3 context."""

    observed = environment.context
    return ProjectLockContext(
        root_package=selection.root_package,
        workspace_member=selection.workspace_member,
        dependency_group_selection=selection.dependency_group_selection,
        dependency_groups=selection.dependency_groups,
        extras=selection.extras,
        python_version=observed.python_version,
        platform=observed.platform,
        architecture=observed.architecture,
        path_flavor=observed.path_flavor,
        case_rule=observed.case_rule,
        uv_version=observed.uv_version,
        build_policy=build_policy,
        compile_bytecode=False,
        resolution_strategy="highest",
        lock_identity=selection.lock_identity,
    )


def _run_project_lock_analysis(  # noqa: PLR0912, PLR0913, PLR0915
    *,
    project: Path | None,
    lockfile: Path | None,
    workspace_member: str | None,
    dependency_groups: tuple[str, ...],
    all_groups: bool,
    extras: tuple[str, ...],
    baseline,
    write_baseline_path: Path | None,
    overwrite_baseline: bool,
    json_output: bool,
    comparison_json: bool,
    allow_build: bool,
    python_version: str | None,
    policy: BudgetPolicy | None,
    bin: bool,
    report_format: str,
) -> None:
    """Run the project-lock path without reopening validated input bytes."""

    assert project is not None and lockfile is not None
    try:
        snapshot = _read_validated_project_lock(
            project,
            lockfile,
            workspace_member=workspace_member,
            dependency_groups=dependency_groups,
            all_groups=all_groups,
            extras=extras,
        )
    except ProjectLockInputError as error:
        raise _BaselineClickError(_project_input_failure_message(error)) from None
    if not shutil.which("uv"):
        raise click.ClickException(
            "'uv' command not found. Please install it first. "
            "See https://github.com/astral-sh/uv for installation instructions."
        )

    write_mode = write_baseline_path is not None
    # Project-lock failures must never contaminate stdout, including text mode.
    progress_to_stderr = True
    click.echo(
        "Calculating size for the selected project lock...", err=progress_to_stderr
    )
    build_policy = BuildPolicy.ALLOW_BUILD if allow_build else BuildPolicy.WHEEL_ONLY
    try:
        uv_version = _uv_version()
    except UvCommandError as error:
        raise click.ClickException(
            _command_failure_message(error, build_policy=build_policy)
        ) from None
    except UvVersionError:
        raise click.ClickException("Could not determine the uv version.") from None

    click.echo("Installing the selected project lock...", err=progress_to_stderr)

    def collect_inventory(target: Path):
        click.echo("Analyzing sizes...", err=progress_to_stderr)
        environment = discover_installed_environment(
            venv_path=target,
            # The environment adapter currently constructs a fresh context as
            # an internal probe value. Its non-empty requirement invariant is
            # satisfied with the validated root name, then immediately
            # replaced by the dedicated ProjectLockContext below.
            requirements=(snapshot.selection.root_package,),
            uv_version=uv_version,
            build_policy=build_policy,
            compile_bytecode=False,
            extras=(),
            index_identifiers=(),
            resolution_strategy="highest",
        )
        context = _project_lock_context(
            snapshot.selection, environment, build_policy=build_policy
        )
        return analyze_installed_environment(
            context=context, layouts=environment.layouts
        )

    try:
        result = install_validated_project_lock(
            snapshot,
            build_policy=build_policy,
            collect_inventory=collect_inventory,
            python_version=python_version,
        )
    except ProjectLockInstallError as error:
        raise click.ClickException(_project_install_failure_message(error)) from None
    except (EnvironmentDiscoveryError, AnalysisContextError, InventoryError) as error:
        raise click.ClickException(_analysis_failure_message(error)) from None

    current_baseline = None
    diff = None
    if baseline is not None or policy is not None:
        try:
            current_baseline = analysis_result_to_baseline(result)
        except ValueError:
            raise click.ClickException(
                "Could not evaluate the analysis result."
            ) from None
    if baseline is not None:
        click.echo("Comparing with baseline...", err=True)
        try:
            assert current_baseline is not None
            diff = compare_baselines(baseline, current_baseline)
        except IncompatibleComparisonError as error:
            raise _ComparisonClickError(_comparison_failure_message(error)) from None
        except ValueError:
            raise click.ClickException(
                "Could not compare the analysis result."
            ) from None

    budget_evaluation = _evaluate_budget_policy(
        policy=policy, current_baseline=current_baseline, comparison=diff
    )
    if baseline is not None:
        assert diff is not None
        if comparison_json:
            if budget_evaluation is not None and not budget_evaluation.passed:
                _raise_budget_violation(budget_evaluation, json_output=True)
            try:
                click.echo(render_project_lock_comparison_json(diff), nl=False)
            except (TypeError, ValueError):
                raise click.ClickException(
                    "Could not render comparison JSON."
                ) from None
        else:
            report = _render_comparison_report(diff, report_format=report_format)
            if budget_evaluation is not None:
                report = "\n\n".join((report, render_budget_report(budget_evaluation)))
            click.echo(report)
            if budget_evaluation is not None and not budget_evaluation.passed:
                _raise_budget_violation(budget_evaluation, json_output=False)
        return

    if json_output:
        if budget_evaluation is not None and not budget_evaluation.passed:
            _raise_budget_violation(budget_evaluation, json_output=True)
        if write_mode:
            _write_project_lock_baseline_if_requested(
                write_baseline_path, result, overwrite_baseline
            )
        click.echo(render_project_lock_analysis_json(result), nl=False)
    else:
        report = _render_primary_analysis_report(
            result,
            report_format=report_format,
            show_scripts=bin,
        )
        if budget_evaluation is not None:
            report = "\n\n".join((report, render_budget_report(budget_evaluation)))
        if budget_evaluation is not None and not budget_evaluation.passed:
            click.echo(report)
            _raise_budget_violation(budget_evaluation, json_output=False)
        _write_project_lock_baseline_if_requested(
            write_baseline_path, result, overwrite_baseline
        )
        click.echo(report)
    click.echo("\nCalculation complete.", err=progress_to_stderr)


def _write_project_lock_baseline_if_requested(
    path: Path | None, result, overwrite: bool
) -> None:
    if path is None:
        return
    try:
        payload = render_project_lock_baseline(result)
        write_baseline(path, payload, overwrite=overwrite)
    except BaselineWriteError as error:
        raise _BaselineClickError(_baseline_write_failure_message(error)) from None


def _validate_prefix_options(  # noqa: PLR0913
    *,
    package_names: tuple[str, ...],
    site_packages_relative: tuple[str, ...],
    case_rule: str | None,
    allow_build: bool,
    python_version: str | None,
    explain: bool,
    breakdown: bool,
    contributions: bool,
    json_output: bool,
) -> None:
    """Reject mutually exclusive CLI modes before any external interaction."""

    if package_names:
        raise click.UsageError("PACKAGE_NAMES cannot be used with --prefix.")
    if allow_build:
        raise click.UsageError("--allow-build cannot be used with --prefix.")
    if python_version is not None:
        raise click.UsageError("--python cannot be used with --prefix.")
    if not site_packages_relative:
        raise click.UsageError("--site-packages is required with --prefix.")
    if case_rule is None:
        raise click.UsageError("--case-rule is required with --prefix.")
    # Text-only graph assertions require a resolving input, which a prefix
    # deliberately does not preserve.  JSON intentionally ignores all text
    # presentation flags, matching the established JSON option boundary.
    if not json_output and (explain or breakdown or contributions):
        unavailable = next(
            option
            for enabled, option in (
                (explain, "--explain"),
                (breakdown, "--breakdown"),
                (contributions, "--contributions"),
            )
            if enabled
        )
        raise click.UsageError(f"{unavailable} is unavailable with --prefix.")


def _run_prefix_analysis(  # noqa: PLR0913
    *,
    prefix: Path,
    site_packages_relative: tuple[str, ...],
    case_rule: CaseRule,
    bin: bool,
    json_output: bool,
    report_format: str,
) -> None:
    """Analyze an existing prefix without invoking uv or an interpreter."""

    click.echo("Analyzing existing prefix...", err=json_output)
    try:
        environment = discover_existing_prefix(
            prefix=prefix,
            site_packages_relative=site_packages_relative,
            path_flavor=_host_path_flavor(),
            case_rule=case_rule,
        )
    except ExistingPrefixDiscoveryError as error:
        raise click.ClickException(_prefix_discovery_failure_message(error)) from None

    try:
        result = analyze_installed_environment(
            context=environment.context,
            layouts=environment.layouts,
        )
    except (AnalysisContextError, InventoryError) as error:
        raise click.ClickException(_prefix_analysis_failure_message(error)) from None

    if json_output:
        click.echo(render_analysis_json(result, schema_version=2), nl=False)
    else:
        click.echo(
            _render_primary_analysis_report(
                result,
                report_format=report_format,
                show_scripts=bin,
                binaries_title="Binaries in prefix",
            )
        )
    click.echo("\nExisting prefix analysis complete.", err=json_output)
