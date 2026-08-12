"""Regression coverage for the documented GitHub Actions workflow snippet."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
WORKFLOW_EXAMPLE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "github-actions"
    / "uv-packsize-project-lock.yml"
)


def test_project_lock_workflow_example_is_least_privilege_and_read_only():
    workflow = WORKFLOW_EXAMPLE.read_text()

    assert "permissions:\n  contents: read\n" in workflow
    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "actions/github-script" not in workflow
    assert "gh pr comment" not in workflow
    assert "--write-baseline" not in workflow
    assert "--overwrite-baseline" not in workflow
    assert workflow.count("uses: astral-sh/setup-uv@v7") == 1
    assert "astral-sh/setup-uv@v6" not in workflow


def test_project_lock_workflow_example_uses_explicit_safe_inputs_and_summary():
    workflow = WORKFLOW_EXAMPLE.read_text()

    command = (
        "uvx uv-packsize --project pyproject.toml "
        "--lockfile uv.lock --baseline .ci/uv-packsize-baseline.json "
        '--budget-config pyproject.toml --comparison-json > "$comparison_json"'
    )
    assert command in workflow
    assert 'temporary_directory="$(mktemp -d)"' in workflow
    assert 'comparison_json="$temporary_directory/comparison.json"' in workflow
    assert "trap 'rm -rf \"$temporary_directory\"' EXIT" in workflow
    assert 'python - "$comparison_json" >> "$GITHUB_STEP_SUMMARY"' in workflow

    expected_summary_fields = [
        "comparison['context']['input_kind']",
        "comparison['context']['lock_changed']",
        'comparison["baseline"]["totals"]["global_logical_bytes"]',
        'comparison["current"]["totals"]["global_logical_bytes"]',
        'comparison["changes"]["totals"]["global_logical_bytes_delta"]',
    ]
    for field in expected_summary_fields:
        assert field in workflow

    for unsafe_or_non_summary_field in [
        "comparison_context_fingerprint",
        "distributions",
        "requirements",
        "lock_identity",
    ]:
        assert unsafe_or_non_summary_field not in workflow


def test_readme_embeds_the_tested_workflow_example_verbatim():
    readme = (PROJECT_ROOT / "README.md").read_text()
    workflow = WORKFLOW_EXAMPLE.read_text().rstrip()

    assert f"```yaml\n{workflow}\n```" in readme


def test_user_guide_embeds_the_tested_workflow_example_verbatim():
    user_guide = (PROJECT_ROOT / "docs" / "user-guide" / "ci.md").read_text()
    workflow = WORKFLOW_EXAMPLE.read_text().rstrip()

    assert f"```yaml\n{workflow}\n```" in user_guide


def test_workflow_summary_script_reads_only_the_documented_safe_fields(tmp_path):
    workflow = WORKFLOW_EXAMPLE.read_text()
    script_start = "          import json\n"
    script_end = "          PY\n"
    script = "import json\n" + textwrap.dedent(
        workflow.partition(script_start)[2].partition(script_end)[0]
    )
    comparison_json = tmp_path / "comparison.json"
    comparison_json.write_text(
        json.dumps(
            {
                "context": {"input_kind": "project-lock", "lock_changed": True},
                "baseline": {"totals": {"global_logical_bytes": 100}},
                "current": {"totals": {"global_logical_bytes": 112}},
                "changes": {
                    "totals": {"global_logical_bytes_delta": 12},
                    "distributions": ["not summarized"],
                },
            }
        )
    )

    completed = subprocess.run(
        [sys.executable, "-c", script, str(comparison_json)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stderr == ""
    assert completed.stdout == (
        "## Dependency footprint\n\n"
        "- Input kind: `project-lock`\n"
        "- Lock changed: `True`\n"
        "- Baseline total: 100 bytes\n"
        "- Current total: 112 bytes\n"
        "- Change: +12 bytes\n"
    )
