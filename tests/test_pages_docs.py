"""Regression checks for the MkDocs user documentation and its deployment."""

import re
import subprocess
import sys
from pathlib import Path

from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
)
from uv_packsize.rich_report import project_rich_analysis, render_rich_analysis_report

PROJECT_ROOT = Path(__file__).parent.parent
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "pages.yml"
MKDOCS_CONFIG = PROJECT_ROOT / "mkdocs.yml"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
LOCKFILE = PROJECT_ROOT / "uv.lock"
HOME_PAGE = PROJECT_ROOT / "docs" / "user-guide" / "index.md"
GUIDE_DIR = PROJECT_ROOT / "docs" / "user-guide"
EXTRA_CSS = (
    PROJECT_ROOT / "docs" / "user-guide" / "assets" / "stylesheets" / "extra.css"
)
SAMPLE_RICH_REPORT = (
    PROJECT_ROOT / "tests" / "fixtures" / "docs" / "sample-rich-analysis-report.txt"
)


def test_pages_workflow_builds_strict_mkdocs_then_deploys_with_least_privilege():
    workflow = PAGES_WORKFLOW.read_text()

    assert "docs/user-guide/**" in workflow
    assert "mkdocs.yml" in workflow
    assert "uv run --locked mkdocs build --strict" in workflow
    assert "path: ${{ runner.temp }}/site" in workflow
    assert "needs: build" in workflow
    assert "actions/configure-pages@v6" in workflow
    assert "actions/upload-pages-artifact@v5" in workflow
    assert "actions/deploy-pages@v5" in workflow
    assert workflow.count("astral-sh/setup-uv@v7") == 1
    for legacy in (
        "astral-sh/setup-uv@v6",
        "actions/configure-pages@v5",
        "actions/upload-pages-artifact@v4",
        "actions/deploy-pages@v4",
    ):
        assert legacy not in workflow
    assert "contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert workflow.index("    permissions:\n      pages: write") > workflow.index(
        "  deploy:\n"
    )
    assert "pull_request" not in workflow


def test_mkdocs_configuration_covers_the_user_guide():
    config = MKDOCS_CONFIG.read_text()

    for expected in [
        "theme:\n  name: material",
        "emoji_index: !!python/name:material.extensions.emoji.twemoji",
        "Getting started: getting-started.md",
        "Measuring packages: measuring-packages.md",
        "Locked projects: locked-projects.md",
        "Baselines and budgets: baselines-and-budgets.md",
        "CI integration: ci.md",
        "Measurement contract: reference/measurement-contract.md",
        "Safety and limitations: reference/safety-and-limitations.md",
    ]:
        assert expected in config
    assert "- navigation.tabs" not in config


def test_docs_layout_keeps_sidebar_navigation_on_desktop_and_a_mobile_drawer():
    config = MKDOCS_CONFIG.read_text()
    stylesheet = EXTRA_CSS.read_text()

    assert "- navigation.sections" in config
    assert "@media screen and (min-width: 76.25em)" in stylesheet
    assert ".md-grid" in stylesheet
    assert ".md-content" in stylesheet


def test_mkdocs_material_is_locked_with_the_project_version():
    project = PYPROJECT.read_text()
    lock = LOCKFILE.read_text()

    project_version = re.search(
        r'^version = "(?P<version>[^"]+)"$', project, re.MULTILINE
    )
    root_package = lock.split('[[package]]\nname = "uv-packsize"', maxsplit=1)[1]

    assert project_version is not None
    assert '"mkdocs-material",' in project
    assert '[[package]]\nname = "mkdocs-material"' in lock
    assert f'version = "{project_version["version"]}"' in root_package
    assert '{ name = "mkdocs-material" },' in root_package


def test_user_guide_builds_without_strict_warnings(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "--site-dir",
            str(tmp_path / "site"),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "site" / "index.html").is_file()


def test_home_page_embeds_a_tested_cli_report_example():
    result = _sample_analysis_result()
    report = render_rich_analysis_report(project_rich_analysis(result))

    assert SAMPLE_RICH_REPORT.read_text().rstrip() == report
    assert f"```text\n{report}\n```" in HOME_PAGE.read_text()


def test_measuring_guide_embeds_a_tested_rich_report_example():
    result = _sample_analysis_result()
    report = render_rich_analysis_report(project_rich_analysis(result))
    guide = (PROJECT_ROOT / "docs" / "user-guide" / "measuring-packages.md").read_text()

    assert SAMPLE_RICH_REPORT.read_text().rstrip() == report
    assert f"```text\n{report}\n```" in guide


def test_home_compares_measurement_modes_with_their_capabilities_and_links():
    home = HOME_PAGE.read_text()

    for expected in [
        "## Choose a measurement mode",
        "| Package requests |",
        "| Locked project |",
        "| Existing prefix |",
        "[Measure packages](measuring-packages.md)",
        "[Measure a locked project](locked-projects.md)",
        "measuring-packages.md#inspect-an-existing-environment-with-prefix",
        "baseline and budget",
    ]:
        assert expected.lower() in home.lower()


def test_guides_have_flow_searchable_controls_and_next_steps():
    measuring = (GUIDE_DIR / "measuring-packages.md").read_text()
    guides = {
        "getting-started.md": ["measuring-packages.md", "locked-projects.md"],
        "measuring-packages.md": [
            "baselines-and-budgets.md",
            "locked-projects.md",
        ],
        "locked-projects.md": ["baselines-and-budgets.md"],
        "baselines-and-budgets.md": ["ci.md"],
        "ci.md": ["reference/measurement-contract.md"],
    }

    for heading in [
        "--json",
        "--explain",
        "--bin",
        "--prefix",
        "--report",
        "--quiet",
        "--color",
    ]:
        assert any(
            line.startswith("## ") and heading in line
            for line in measuring.splitlines()
        )

    for filename, links in guides.items():
        guide = (GUIDE_DIR / filename).read_text()
        assert "## Next step" in guide
        for link in links:
            assert link in guide

    for expected in [
        "RECORD-owned scripts",
        "With `--report standard`, `--bin` moves RECORD-owned scripts from the package",
        "With `--report rich`, it leaves the\nprimary summary and Largest Distributions owned sizes unchanged",
        "Both layouts preserve the canonical global total,\nand `--bin` never changes JSON bytes",
        "`Binaries in prefix`",
        "schema v2 bytes",
    ]:
        assert expected in measuring


def test_baseline_and_ci_guides_state_compatibility_and_read_only_flow():
    baselines = (GUIDE_DIR / "baselines-and-budgets.md").read_text()
    ci = (GUIDE_DIR / "ci.md").read_text()

    assert '!!! note "Compatibility comes first"' in baselines
    assert "package-request baselines only with package-request" in baselines
    assert "project-lock baselines only with project-lock" in baselines
    assert "--project pyproject.toml --lockfile uv.lock" in baselines
    assert ci.startswith("# CI integration\n")
    for step in [
        "1. Generate and review a baseline",
        "2. Optionally add a budget policy",
        "3. In CI, compare against the committed baseline",
    ]:
        assert step in ci


def _sample_analysis_result() -> AnalysisResult:
    context = ResolutionContext(
        requirements=("sample",),
        python_version="3.12.4",
        platform="linux",
        architecture="x86_64",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
        uv_version="0.11.3",
        build_policy=BuildPolicy.WHEEL_ONLY,
        compile_bytecode=True,
    )
    file_entry = FileEntry(
        path="site-packages/sample.py",
        canonical_identity="site-packages/sample.py",
        logical_bytes=1536,
        category=FileCategory.PYTHON,
        origin=FileOrigin.RECORD,
    )
    return AnalysisResult(
        context=context,
        distributions=(
            DistributionResult(name="sample", version="1.0.0", files=(file_entry,)),
        ),
    )
