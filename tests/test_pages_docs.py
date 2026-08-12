"""Regression checks for the MkDocs user documentation and its deployment."""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "pages.yml"
MKDOCS_CONFIG = PROJECT_ROOT / "mkdocs.yml"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
LOCKFILE = PROJECT_ROOT / "uv.lock"


def test_pages_workflow_builds_strict_mkdocs_then_deploys_with_least_privilege():
    workflow = PAGES_WORKFLOW.read_text()

    assert "docs/user-guide/**" in workflow
    assert "mkdocs.yml" in workflow
    assert "uv run --locked mkdocs build --strict" in workflow
    assert "path: ${{ runner.temp }}/site" in workflow
    assert "needs: build" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
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
