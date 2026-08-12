"""Regression checks for the static user documentation and its deployment."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "pages.yml"
PAGES_INDEX = PROJECT_ROOT / "docs" / "site" / "index.html"


def test_pages_workflow_deploys_only_static_user_docs_with_required_permissions():
    workflow = PAGES_WORKFLOW.read_text()

    assert "path: docs/site" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "pull_request" not in workflow


def test_user_docs_promote_direct_uvx_usage_and_safe_project_boundaries():
    page = PAGES_INDEX.read_text()

    for expected in [
        "uvx uv-packsize requests",
        "uv tool install uv-packsize",
        "--project pyproject.toml",
        "--lockfile uv.lock",
        "--allow-build",
        "local root project is deliberately not built or measured",
    ]:
        assert expected in page
