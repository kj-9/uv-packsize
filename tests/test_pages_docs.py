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
from uv_packsize.render import render_analysis_report
from uv_packsize.rich_report import project_rich_analysis, render_rich_analysis_report

PROJECT_ROOT = Path(__file__).parent.parent
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "pages.yml"
MKDOCS_CONFIG = PROJECT_ROOT / "mkdocs.yml"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
LOCKFILE = PROJECT_ROOT / "uv.lock"
HOME_PAGE = PROJECT_ROOT / "docs" / "user-guide" / "index.md"
SAMPLE_REPORT = (
    PROJECT_ROOT / "tests" / "fixtures" / "docs" / "sample-analysis-report.txt"
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
    report = render_analysis_report(result)

    assert SAMPLE_REPORT.read_text().rstrip() == report
    assert f"```text\n{report}\n```" in HOME_PAGE.read_text()


def test_measuring_guide_embeds_a_tested_rich_report_example():
    result = _sample_analysis_result()
    report = render_rich_analysis_report(project_rich_analysis(result))
    guide = (PROJECT_ROOT / "docs" / "user-guide" / "measuring-packages.md").read_text()

    assert SAMPLE_RICH_REPORT.read_text().rstrip() == report
    assert f"```text\n{report}\n```" in guide


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
