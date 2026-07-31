import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from uv_packsize.json_render import (
    _requirement_projection,
    analysis_result_to_json_object,
    render_analysis_json,
)
from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    ExistingPrefixContext,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
    WarningCode,
    WarningTargetKind,
)

_ROOT = Path(__file__).parents[1]


def context(**overrides: Any) -> ResolutionContext:
    values: dict[str, Any] = {
        "requirements": (
            "Example_Pkg[Speed,docs]>=1; python_version >= '3.11'",
            "git+https://token@code.example/secret/repository.git#sha256=hidden",
            "../private/build.whl",
            "not a valid requirement @@@",
        ),
        "python_version": "3.14.0",
        "platform": "manylinux_2_28_x86_64",
        "architecture": "x86_64",
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
        "uv_version": "0.11.3",
        "build_policy": BuildPolicy.WHEEL_ONLY,
        "compile_bytecode": False,
        "extras": ("Docs", "speed"),
        "index_identifiers": ("internal-primary", "pypi"),
        "resolution_strategy": "highest",
    }
    values.update(overrides)
    return ResolutionContext(**values)


def file_entry(
    path: str,
    logical_bytes: int,
    **values: Any,
) -> FileEntry:
    return FileEntry(
        path=path,
        canonical_identity=values.get("canonical_identity", path),
        logical_bytes=logical_bytes,
        category=values["category"],
        origin=values["origin"],
        symlink_target=values.get("symlink_target"),
    )


def golden_result(*, reverse: bool = False) -> AnalysisResult:
    missing_record = AnalysisWarning(
        code=WarningCode.MISSING_RECORD,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity="zeta==2.0",
    )
    missing_file = AnalysisWarning(
        code=WarningCode.MISSING_FILE,
        target_kind=WarningTargetKind.FILE,
        target_identity="lib/欠落.py",
    )
    shared = file_entry(
        "lib/shared.py",
        7,
        category=FileCategory.PYTHON,
        origin=FileOrigin.RECORD,
    )
    alpha = DistributionResult(
        name="Alpha_Pkg",
        version="1.0",
        files=(
            file_entry(
                "bin/alpha-tool",
                5,
                category=FileCategory.SCRIPT,
                origin=FileOrigin.GENERATED,
            ),
            file_entry(
                "lib/alpha-pkg.dist-info/METADATA",
                2,
                category=FileCategory.METADATA,
                origin=FileOrigin.RECORD,
            ),
            file_entry(
                "lib/日本語.py",
                11,
                category=FileCategory.DATA,
                origin=FileOrigin.DISCOVERED,
            ),
            shared,
        ),
    )
    zeta = DistributionResult(
        name="zeta",
        version="2.0",
        files=(
            file_entry(
                "lib/zeta.so",
                13,
                category=FileCategory.NATIVE,
                origin=FileOrigin.FALLBACK,
            ),
            file_entry(
                "lib/zeta-link",
                3,
                category=FileCategory.OTHER,
                origin=FileOrigin.RECORD,
                symlink_target="../../credentials/never-render-this",
            ),
            shared,
        ),
        warnings=(missing_record,),
    )
    distributions = (zeta, alpha) if reverse else (alpha, zeta)
    warnings = (missing_file,) if reverse else (missing_file,)
    return AnalysisResult(
        context=context(), distributions=distributions, warnings=warnings
    )


def existing_prefix_result(
    *, reverse: bool = False, **overrides: Any
) -> AnalysisResult:
    values: dict[str, Any] = {
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
        "python_version": "3.13.2",
        "platform": "macosx",
        "architecture": None,
    }
    values.update(overrides)
    source = golden_result(reverse=reverse)
    return AnalysisResult(
        context=ExistingPrefixContext(**values),
        distributions=source.distributions,
    )


def test_render_analysis_json_matches_committed_v1_golden():
    expected = (_ROOT / "tests/golden/analysis-result-v1.json").read_text()

    assert render_analysis_json(golden_result()) == expected
    assert expected.endswith("\n")
    assert not expected.endswith("\n\n")


def test_render_analysis_json_matches_committed_v2_existing_prefix_golden():
    expected = (
        _ROOT / "tests/golden/analysis-result-v2-existing-prefix.json"
    ).read_text()

    empty_result = AnalysisResult(
        context=existing_prefix_result().context,
        distributions=(),
    )
    assert render_analysis_json(empty_result, schema_version=2) == expected
    assert expected.endswith("\n")
    assert not expected.endswith("\n\n")


def test_existing_prefix_json_preserves_known_and_unknown_observations():
    document = analysis_result_to_json_object(
        existing_prefix_result(
            python_version=None,
            platform="linux-x86_64",
            architecture="x86_64",
        ),
        schema_version=2,
    )

    assert document["context"] == {
        "input_kind": "existing-prefix",
        "requirements": [],
        "python_version": None,
        "platform": "linux-x86_64",
        "architecture": "x86_64",
        "path_flavor": "posix",
        "case_rule": "sensitive",
        "uv_version": None,
        "build_policy": None,
        "compile_bytecode": None,
        "extras": [],
        "index_identifiers": [],
        "resolution_strategy": None,
    }


def test_json_is_byte_stable_for_model_input_permutations():
    assert render_analysis_json(golden_result()) == render_analysis_json(
        golden_result(reverse=True)
    )


def test_schema_v2_is_byte_stable_for_model_input_permutations():
    assert render_analysis_json(
        existing_prefix_result(), schema_version=2
    ) == render_analysis_json(existing_prefix_result(reverse=True), schema_version=2)


def test_json_represents_empty_results_and_derived_totals():
    result = AnalysisResult(
        context=context(requirements=("example",)), distributions=()
    )
    document = analysis_result_to_json_object(result)

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
    assert document["distributions"] == []
    assert document["warnings"] == []
    assert document["duplicate_ownerships"] == []
    assert document["completeness"] == "complete"
    assert document["totals"] == {
        "global_logical_bytes": 0,
        "distribution_logical_bytes": 0,
    }

    populated = analysis_result_to_json_object(golden_result())
    assert populated["totals"] == {
        "global_logical_bytes": 41,
        "distribution_logical_bytes": 48,
    }


def test_json_never_leaks_requirement_or_symlink_secrets():
    rendered = render_analysis_json(golden_result())

    for secret in (
        "token@code.example",
        "secret/repository.git",
        "sha256=hidden",
        "../private/build.whl",
        "not a valid requirement",
        "credentials/never-render-this",
    ):
        assert secret not in rendered
    assert '"is_symlink": true' in rendered
    assert "symlink_target" not in rendered


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        (
            "Example[Z_extra,a-extra]>=1; python_version < '3.13'",
            {
                "input_index": 4,
                "kind": "named",
                "name": "example",
                "extras": ["a-extra", "z-extra"],
                "has_specifier": True,
                "has_marker": True,
            },
        ),
        (
            "private @ https://user:pass@example.invalid/a?token=x#sha256=y",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "file:///private/secret.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": None,
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ ../private/secret.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ ~/private/secret.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ ~\\private\\secret.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ \\\\server\\share\\secret.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ file:/tmp/project.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ file://localhost/tmp/project.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ file://server/share/project.whl",
            {
                "input_index": 4,
                "kind": "local-path",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ git+file:///tmp/repository",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ hg+file:///tmp/repository",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ svn+file:///tmp/repository",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ bzr+file:///tmp/repository",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ git+https://github.com/example/project.git",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ ssh://git@example.invalid/project.git",
            {
                "input_index": 4,
                "kind": "direct-url",
                "name": "private",
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ relative/project.whl; python_version >= '3.10'",
            {
                "input_index": 4,
                "kind": "opaque",
                "name": None,
                "extras": [],
                "has_specifier": False,
                "has_marker": True,
            },
        ),
        (
            "private @ C:relative\\project.whl",
            {
                "input_index": 4,
                "kind": "opaque",
                "name": None,
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "private @ https:missing-slashes",
            {
                "input_index": 4,
                "kind": "opaque",
                "name": None,
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
        (
            "??? not parseable ???",
            {
                "input_index": 4,
                "kind": "opaque",
                "name": None,
                "extras": [],
                "has_specifier": False,
                "has_marker": False,
            },
        ),
    ],
)
def test_requirement_projection_is_safe_and_non_reversible(requirement, expected):
    projection = _requirement_projection(4, requirement)

    assert projection == expected
    assert requirement not in json.dumps(projection)


@pytest.mark.parametrize(
    "identifier",
    [
        "https://user:pass@example.invalid/simple",
        "../private-index",
        "/private-index",
        "user@private",
        ".private",
        "private/index",
        "éxample",
        "a" * 65,
    ],
)
def test_context_rejects_unsafe_index_identifiers(identifier):
    with pytest.raises(ValueError, match="ASCII symbolic aliases"):
        context(index_identifiers=(identifier,))


def test_context_accepts_bounded_ascii_index_aliases():
    resolved = context(index_identifiers=("Pypi", "internal.index-1", "a" * 64))

    assert resolved.index_identifiers == ("Pypi", "a" * 64, "internal.index-1")


def test_committed_schema_is_closed_and_matches_the_v1_golden_shape():
    schema = json.loads((_ROOT / "schemas/analysis-result-v1.schema.json").read_text())
    golden = json.loads((_ROOT / "tests/golden/analysis-result-v1.json").read_text())

    assert schema["additionalProperties"] is False
    assert schema["required"] == list(golden)
    assert set(schema["properties"]) == set(golden)
    assert schema["properties"]["schema_version"] == {"const": 1}
    assert schema["$defs"]["requirement"]["additionalProperties"] is False
    assert schema["$defs"]["file"]["additionalProperties"] is False
    assert schema["$defs"]["distribution"]["additionalProperties"] is False
    assert schema["$defs"]["context"]["properties"]["path_flavor"]["enum"] == [
        "posix",
        "windows",
    ]
    assert schema["$defs"]["file"]["properties"]["category"]["enum"] == [
        "python",
        "native",
        "data",
        "metadata",
        "script",
        "other",
    ]


def test_committed_v2_schema_is_closed_self_contained_and_matches_golden_shape():
    schema_path = _ROOT / "schemas/analysis-result-v2.schema.json"
    schema = json.loads(schema_path.read_text())
    golden = json.loads(
        (_ROOT / "tests/golden/analysis-result-v2-existing-prefix.json").read_text()
    )

    assert schema["additionalProperties"] is False
    assert schema["required"] == list(golden)
    assert set(schema["properties"]) == set(golden)
    assert schema["properties"]["schema_version"] == {"const": 2}
    assert "analysis-result-v1" not in schema_path.read_text()
    context_schema = schema["$defs"]["context"]
    assert context_schema["additionalProperties"] is False
    assert context_schema["properties"]["input_kind"] == {"const": "existing-prefix"}
    assert context_schema["properties"]["requirements"] == {
        "type": "array",
        "maxItems": 0,
    }
    assert context_schema["properties"]["extras"] == {
        "type": "array",
        "maxItems": 0,
    }
    safe_observation = schema["$defs"]["safeObservation"]
    assert safe_observation["type"] == "string"
    assert safe_observation["minLength"] == 1
    observation_pattern = re.compile(safe_observation["pattern"])
    for field_name in ("python_version", "platform", "architecture"):
        assert context_schema["properties"][field_name] == {
            "anyOf": [
                {"$ref": "#/$defs/safeObservation"},
                {"type": "null"},
            ]
        }
    for value in ("3.13.2", "manylinux_2_28_x86_64", "arm64", "glibc 2.39"):
        assert observation_pattern.fullmatch(value)
    for value in (
        "/private/prefix",
        "prefix\\site-packages",
        "~/.venv",
        "C:relative-prefix",
        "C:\\absolute-prefix",
        " leading",
        "trailing ",
        "unsafe\0observation",
    ):
        assert observation_pattern.fullmatch(value) is None
    for field_name in (
        "uv_version",
        "build_policy",
        "compile_bytecode",
        "resolution_strategy",
    ):
        assert context_schema["properties"][field_name] == {"const": None}
    for unsafe_field in (
        "prefix",
        "site_packages",
        "venv",
        "executable",
        "config",
        "credentials",
    ):
        assert unsafe_field not in context_schema["properties"]


def test_json_renderer_requires_an_analysis_result():
    with pytest.raises(TypeError, match="AnalysisResult"):
        analysis_result_to_json_object(cast(Any, "not a result"))


def test_schema_v1_explicitly_rejects_existing_prefix_context():
    result = AnalysisResult(
        context=ExistingPrefixContext(
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
        ),
        distributions=(),
    )

    with pytest.raises(TypeError, match="schema v1 requires a ResolutionContext"):
        analysis_result_to_json_object(result)
    with pytest.raises(TypeError, match="schema v1 requires a ResolutionContext"):
        render_analysis_json(result)


def test_schema_v2_explicitly_rejects_resolution_context():
    with pytest.raises(TypeError, match="schema v2 requires an ExistingPrefixContext"):
        analysis_result_to_json_object(golden_result(), schema_version=2)
    with pytest.raises(TypeError, match="schema v2 requires an ExistingPrefixContext"):
        render_analysis_json(golden_result(), schema_version=2)


@pytest.mark.parametrize("schema_version", [True, False, 0, 3, -1, "2", None])
def test_schema_version_selector_rejects_bool_and_unsupported_values(schema_version):
    with pytest.raises(ValueError, match="schema_version must be 1 or 2"):
        analysis_result_to_json_object(
            golden_result(), schema_version=cast(Any, schema_version)
        )
    with pytest.raises(ValueError, match="schema_version must be 1 or 2"):
        render_analysis_json(golden_result(), schema_version=cast(Any, schema_version))


def test_schema_version_one_remains_byte_identical_when_selected_explicitly():
    assert render_analysis_json(golden_result()) == render_analysis_json(
        golden_result(), schema_version=1
    )
