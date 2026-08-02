import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from uv_packsize.baseline import (
    BaselineError,
    BaselineProjectLockContext,
    analysis_result_to_baseline,
    parse_baseline_json,
)
from uv_packsize.diff import (
    IncompatibleComparisonError,
    compare_baselines,
    project_lock_changed,
)
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DependencyGroupSelection,
    PathFlavor,
    ProjectLockContext,
)
from uv_packsize.project_comparison_json_render import (
    project_lock_comparison_to_json_object,
)
from uv_packsize.project_lock_json_render import (
    project_lock_analysis_to_json_object,
    render_project_lock_analysis_json,
)


def context(**overrides):
    values = {
        "root_package": "Example_Project",
        "workspace_member": None,
        "dependency_group_selection": DependencyGroupSelection.ALL,
        "dependency_groups": (),
        "extras": ("Speed", "docs"),
        "python_version": "3.14.0",
        "platform": "linux",
        "architecture": "x86_64",
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
        "uv_version": "0.11.3",
        "build_policy": BuildPolicy.WHEEL_ONLY,
        "compile_bytecode": False,
        "resolution_strategy": "highest",
        "lock_identity": "a" * 64,
    }
    values.update(overrides)
    return ProjectLockContext(**values)


def result(**overrides):
    return AnalysisResult(context=context(**overrides), distributions=())


def test_project_context_normalizes_effective_selection_and_rejects_invalid_modes():
    value = context(
        dependency_group_selection=DependencyGroupSelection.EXPLICIT,
        dependency_groups=("Test_Group", "docs"),
        extras=("Docs", "speed"),
    )

    assert value.root_package == "example-project"
    assert value.dependency_groups == ("docs", "test-group")
    assert value.extras == ("docs", "speed")
    assert context().dependency_groups == ()  # all + empty is meaningful
    with pytest.raises(ValueError):
        context(
            dependency_group_selection=DependencyGroupSelection.NONE,
            dependency_groups=("dev",),
        )
    with pytest.raises(ValueError):
        context(
            dependency_group_selection=DependencyGroupSelection.EXPLICIT,
            dependency_groups=(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("python_version", "/private/project/python"),
        ("platform", "https://token@example.invalid/linux"),
        ("architecture", "x86_64@credential"),
        ("uv_version", "file:///private/uv"),
        ("resolution_strategy", "https://user:token@example.invalid"),
    ],
)
def test_project_context_rejects_path_url_and_credential_like_observations(
    field, value
):
    with pytest.raises(ValueError) as captured:
        context(**{field: value})

    assert value not in str(captured.value)


def test_v3_projection_round_trips_to_baseline_without_paths_or_raw_lock_data():
    source = result()
    rendered = render_project_lock_analysis_json(source)
    document = json.loads(rendered)

    assert document == project_lock_analysis_to_json_object(source)
    assert list(document) == [
        "schema_version",
        "measurement",
        "context",
        "distributions",
        "warnings",
        "duplicate_ownerships",
        "completeness",
        "totals",
    ]
    assert document["schema_version"] == 3
    assert document["context"]["lock_identity"] == "a" * 64
    assert parse_baseline_json(rendered) == analysis_result_to_baseline(source)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("python_version", "/private/project/python"),
        ("platform", "https://token@example.invalid/linux"),
        ("architecture", "x86_64@credential"),
        ("uv_version", "file:///private/uv"),
        ("resolution_strategy", "https://user:token@example.invalid"),
    ],
)
def test_v3_baseline_decoder_rejects_unsafe_project_observations(field, value):
    document = project_lock_analysis_to_json_object(result())
    context_document = cast(dict[str, object], document["context"])
    context_document[field] = value

    with pytest.raises(BaselineError) as captured:
        parse_baseline_json(json.dumps(document))

    assert value not in str(captured.value)


def test_v3_and_comparison_v2_schemas_are_self_contained_and_keep_strict_defs():
    root = Path(__file__).parents[1]
    analysis_schema = json.loads(
        (root / "schemas" / "analysis-result-v3.schema.json").read_text()
    )
    comparison_schema = json.loads(
        (root / "schemas" / "comparison-result-v2.schema.json").read_text()
    )

    def references(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "$ref":
                    yield item
                yield from references(item)
        elif isinstance(value, list):
            for item in value:
                yield from references(item)

    assert all(reference.startswith("#/") for reference in references(analysis_schema))
    assert all(
        reference.startswith("#/") for reference in references(comparison_schema)
    )
    assert analysis_schema["$defs"]["warning"]["properties"]["code"]["enum"]
    assert analysis_schema["$defs"]["distribution"]["additionalProperties"] is False
    assert comparison_schema["$defs"]["side"]["additionalProperties"] is False
    assert comparison_schema["$defs"]["distribution"]["oneOf"]
    assert comparison_schema["$defs"]["nonreconciliation"]["allOf"]
    context_schema = analysis_schema["$defs"]["context"]
    assert context_schema["additionalProperties"] is False
    assert len(context_schema["allOf"]) == 2


def test_project_lock_comparison_excludes_identity_from_compatibility_and_reports_change():
    before = analysis_result_to_baseline(result(lock_identity="a" * 64))
    current = analysis_result_to_baseline(result(lock_identity="b" * 64))
    diff = compare_baselines(before, current)
    document = project_lock_comparison_to_json_object(diff)

    assert project_lock_changed(before, current) is True
    assert document["schema_version"] == 2
    comparison_context = cast(dict[str, object], document["context"])
    assert comparison_context["input_kind"] == "project-lock"
    assert comparison_context["lock_changed"] is True
    assert "a" * 64 not in json.dumps(document)
    with pytest.raises(IncompatibleComparisonError):
        compare_baselines(
            before,
            replace(
                current,
                project_lock_context=replace(
                    cast(BaselineProjectLockContext, current.project_lock_context),
                    extras=("other",),
                ),
            ),
        )
