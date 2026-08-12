import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

import uv_packsize.baseline as baseline_module
from uv_packsize.baseline import (
    MAX_BASELINE_BYTES,
    BaselineError,
    BaselineLoadError,
    analysis_result_to_baseline,
    load_baseline,
    parse_baseline_json,
)
from uv_packsize.diff import compare_baselines
from uv_packsize.json_render import render_analysis_json
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


def _golden(version: int) -> dict[str, object]:
    name = (
        "analysis-result-v1.json"
        if version == 1
        else "analysis-result-v2-existing-prefix.json"
    )
    return json.loads((_ROOT / "tests" / "golden" / name).read_text())


def _parse(document: object):
    return parse_baseline_json(json.dumps(document))


def _projection_result(*, reverse: bool = False) -> AnalysisResult:
    context = ResolutionContext(
        requirements=(
            "Example[docs,Speed]>=1; python_version >= '3.11'",
            "git+https://token@example.invalid/private/repo.git",
            "../private/package.whl",
            "not a valid requirement @@@",
        ),
        python_version="3.14.0 private",
        platform="platform private",
        architecture="x86_64 private",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
        uv_version="0.11.3 private",
        build_policy=BuildPolicy.ALLOW_BUILD,
        compile_bytecode=False,
        extras=("Docs", "speed"),
        index_identifiers=("internal-primary", "pypi"),
        resolution_strategy="highest private",
    )
    shared = FileEntry(
        path="lib/shared.py",
        canonical_identity="lib/shared.py",
        logical_bytes=7,
        category=FileCategory.PYTHON,
        origin=FileOrigin.RECORD,
    )
    alpha = DistributionResult(
        name="Alpha_Pkg",
        version="1.0",
        files=(
            FileEntry(
                path="lib/alpha.py",
                canonical_identity="lib/alpha.py",
                logical_bytes=5,
                category=FileCategory.PYTHON,
                origin=FileOrigin.RECORD,
            ),
            shared,
        ),
    )
    zeta = DistributionResult(
        name="zeta",
        version="2.0",
        files=(shared,),
        warnings=(
            AnalysisWarning(
                code=WarningCode.MISSING_RECORD,
                target_kind=WarningTargetKind.DISTRIBUTION,
                target_identity="zeta==2.0",
            ),
        ),
    )
    return AnalysisResult(
        context=context,
        distributions=(zeta, alpha) if reverse else (alpha, zeta),
        warnings=(
            AnalysisWarning(
                code=WarningCode.MISSING_FILE,
                target_kind=WarningTargetKind.FILE,
                target_identity="private/missing.py",
            ),
        ),
    )


def test_analysis_result_to_baseline_matches_public_v1_json_projection():
    result = _projection_result()

    expected = parse_baseline_json(render_analysis_json(result))
    projected = analysis_result_to_baseline(result)

    assert projected == expected
    assert hash(projected) == hash(expected)
    assert projected.global_logical_bytes == 12
    assert sum(item.logical_bytes for item in projected.distributions) == 19
    assert projected.warnings.completeness == "incomplete"
    assert projected.warnings.warning_code_counts == (
        ("duplicate-ownership", 1),
        ("missing-file", 1),
        ("missing-record", 1),
    )
    assert projected.duplicate_ownership.present is True
    assert projected.duplicate_ownership.count == 1


def test_analysis_result_to_baseline_is_deterministic_and_never_renders_json(
    monkeypatch,
):
    expected = analysis_result_to_baseline(_projection_result())

    def fail_render(*args, **kwargs):
        raise AssertionError("JSON serialization must not be used for projection")

    monkeypatch.setattr("uv_packsize.json_render.render_analysis_json", fail_render)
    assert analysis_result_to_baseline(_projection_result(reverse=True)) == expected


def test_analysis_result_to_baseline_handles_empty_fresh_analysis():
    source = AnalysisResult(
        context=ResolutionContext(
            requirements=("example",),
            python_version="3.14",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.WINDOWS,
            case_rule=CaseRule.INSENSITIVE,
            uv_version="0.11",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
        ),
        distributions=(),
    )

    assert analysis_result_to_baseline(source) == parse_baseline_json(
        render_analysis_json(source)
    )


def test_analysis_result_to_baseline_rejects_non_fresh_and_forged_inputs():
    secret = "private-token"

    class DerivedAnalysisResult(AnalysisResult):
        pass

    existing = AnalysisResult(
        context=ExistingPrefixContext(
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            platform=secret,
        ),
        distributions=(),
    )
    derived = DerivedAnalysisResult(
        context=_projection_result().context,
        distributions=(),
    )

    for value in (existing, derived, cast(Any, object())):
        with pytest.raises(TypeError) as captured:
            analysis_result_to_baseline(value)
        assert secret not in str(captured.value)


def test_distribution_only_warning_summary_is_comparable_and_matches_projection():
    result = AnalysisResult(
        context=ResolutionContext(
            requirements=("example",),
            python_version="3.14",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            uv_version="0.11",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        distributions=(
            DistributionResult(
                name="example",
                version="1",
                files=(),
                warnings=(
                    AnalysisWarning(
                        code=WarningCode.MISSING_RECORD,
                        target_kind=WarningTargetKind.DISTRIBUTION,
                        target_identity="example==1",
                    ),
                ),
            ),
        ),
    )

    parsed = parse_baseline_json(render_analysis_json(result))
    assert parsed.warnings.warning_code_counts == (("missing-record", 1),)
    assert parsed.warnings.completeness == "incomplete"
    assert compare_baselines(parsed, parsed).completeness.value == "incomplete"
    assert analysis_result_to_baseline(result) == parsed


def test_parse_baseline_accepts_committed_v1_and_v2_goldens_with_safe_projection():
    v1 = _parse(_golden(1))
    v2 = _parse(_golden(2))

    assert (v1.schema_version, v1.input_kind, v1.global_logical_bytes) == (
        1,
        "fresh-install",
        41,
    )
    assert [
        (item.name, item.version, item.logical_bytes) for item in v1.distributions
    ] == [
        ("alpha-pkg", "1.0", 25),
        ("zeta", "2.0", 23),
    ]
    assert v1.warnings.warning_code_counts == (
        ("duplicate-ownership", 1),
        ("missing-file", 1),
        ("missing-record", 1),
    )
    assert v1.duplicate_ownership.present is True
    assert v1.resolution_context is not None
    assert v1.existing_prefix_context is None
    assert (v2.schema_version, v2.input_kind, v2.global_logical_bytes) == (
        2,
        "existing-prefix",
        0,
    )
    assert v2.resolution_context is None
    assert v2.existing_prefix_context is not None


def test_v1_free_form_context_is_fingerprinted_not_retained_or_rendered():
    document = _golden(1)
    context = cast(dict[str, Any], document["context"])
    secret_platform = "private-platform-token"
    context["platform"] = secret_platform
    result = _parse(document)
    comparison_context = result.resolution_context
    assert comparison_context is not None
    assert not hasattr(comparison_context, "platform")
    assert secret_platform not in repr(result)

    different = deepcopy(document)
    different_context = cast(dict[str, Any], different["context"])
    different_context["platform"] = secret_platform + "x"
    different_result = _parse(different)
    assert different_result.resolution_context is not None
    assert (
        comparison_context.platform_fingerprint
        != different_result.resolution_context.platform_fingerprint
    )


def test_v2_nullable_observations_are_fingerprinted_or_preserved_as_none():
    document = _golden(2)
    context = cast(dict[str, Any], document["context"])
    private_platform = "private-platform-token\tobserved"
    context["platform"] = private_platform
    result = _parse(document)
    comparison_context = result.existing_prefix_context
    assert comparison_context is not None
    assert comparison_context.python_version_fingerprint is not None
    assert comparison_context.architecture_fingerprint is None
    assert comparison_context.platform_fingerprint is not None
    assert not hasattr(comparison_context, "platform")
    assert private_platform not in repr(result)

    different = deepcopy(document)
    different_context = cast(dict[str, Any], different["context"])
    different_context["platform"] = private_platform + "x"
    different_result = _parse(different)
    assert different_result.existing_prefix_context is not None
    assert (
        comparison_context.platform_fingerprint
        != different_result.existing_prefix_context.platform_fingerprint
    )


def test_parse_baseline_is_deterministic_and_deeply_immutable():
    left = _parse(_golden(1))
    document = _golden(1)
    distributions = document["distributions"]
    assert isinstance(distributions, list)
    distributions.reverse()
    right = _parse(document)

    assert left == right
    with pytest.raises(AttributeError):
        left.distributions += ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update({"unexpected": True}),
        lambda document: document.update({"schema_version": True}),
        lambda document: document.update({"schema_version": "1"}),
        lambda document: document.update({"schema_version": 99}),
        lambda document: document.update({"measurement": "bytes"}),
        lambda document: document["measurement"].update({"unit": "KiB"}),  # type: ignore[index]
        lambda document: document["context"].update({"unknown": "value"}),  # type: ignore[index]
        lambda document: document["totals"].update({"global_logical_bytes": -1}),  # type: ignore[index]
        lambda document: document["totals"].update({"global_logical_bytes": True}),  # type: ignore[index]
        lambda document: document["distributions"][1].update({"name": "alpha_pkg"}),  # type: ignore[index]
        lambda document: document["distributions"][0]["totals"].update(
            {"logical_bytes": 999}
        ),  # type: ignore[index]
        lambda document: document["duplicate_ownerships"].clear(),  # type: ignore[index]
    ],
)
def test_parse_baseline_rejects_schema_and_semantic_boundary_violations(mutate):
    document = deepcopy(_golden(1))
    mutate(document)

    with pytest.raises(BaselineError):
        _parse(document)


def test_parse_baseline_rejects_schema_and_context_family_mismatch():
    v1 = _golden(1)
    v1_context = cast(dict[str, Any], v1["context"])
    v1_context["input_kind"] = "existing-prefix"
    v2 = _golden(2)
    v2_context = cast(dict[str, Any], v2["context"])
    v2_context["input_kind"] = "fresh-install"

    with pytest.raises(BaselineError):
        _parse(v1)
    with pytest.raises(BaselineError):
        _parse(v2)


def test_parse_baseline_diagnostics_do_not_reflect_raw_payload():
    secret = "token=private-value/should-not-appear"
    with pytest.raises(BaselineError) as captured:
        parse_baseline_json('{"schema_version": 1, "secret": "' + secret + '"}')

    assert secret not in str(captured.value)
    assert captured.value.field == "document"


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_version": 1, "schema_version": 1}',
        b'{"schema_version": 1, "measurement": {"kind": "x", "kind": "x"}}',
    ],
)
def test_parse_baseline_rejects_duplicate_json_keys_at_every_depth(payload):
    with pytest.raises(BaselineError, match="duplicate-key") as captured:
        parse_baseline_json(payload)

    assert captured.value.field == "document"


def test_parse_baseline_rejects_inconsistent_file_signature_and_ownership_warning():
    signature = _golden(1)
    distributions = cast(list[dict[str, Any]], signature["distributions"])
    distributions[1]["files"][0]["category"] = "data"
    ownership = _golden(1)
    warnings = cast(list[dict[str, Any]], ownership["warnings"])
    warnings[0]["target_identity"] = "lib/not-shared.py"
    local_warning = _golden(1)
    local_distributions = cast(list[dict[str, Any]], local_warning["distributions"])
    local_distributions[0]["warnings"] = [
        {
            "code": "duplicate-ownership",
            "target_kind": "file",
            "target_identity": "lib/shared.py",
        }
    ]

    for document in (signature, ownership, local_warning):
        with pytest.raises(BaselineError, match="inconsistent"):
            _parse(document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda requirement: requirement.update({"kind": "opaque", "name": "example"}),
        lambda requirement: requirement.update({"kind": "opaque", "extras": ["docs"]}),
        lambda requirement: requirement.update(
            {"kind": "direct-url", "has_specifier": True}
        ),
        lambda requirement: requirement.update({"kind": "named", "name": None}),
    ],
)
def test_parse_baseline_requires_serializer_representable_requirement_projection(
    mutate,
):
    document = _golden(1)
    context = cast(dict[str, Any], document["context"])
    requirement = cast(dict[str, Any], context["requirements"][0])
    mutate(requirement)

    with pytest.raises(BaselineError, match="inconsistent-requirement"):
        _parse(document)


def test_parse_baseline_rejects_unknown_build_policy():
    document = _golden(1)
    context = cast(dict[str, Any], document["context"])
    context["build_policy"] = "anything-goes"

    with pytest.raises(BaselineError, match="context.build_policy"):
        _parse(document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda warning: warning.update({"target_kind": "distribution"}),
        lambda warning: warning.update({"target_identity": "/not/a/path"}),
    ],
)
def test_parse_baseline_enforces_warning_code_target_kind_and_path_invariants(mutate):
    document = _golden(1)
    warnings = cast(list[dict[str, Any]], document["warnings"])
    mutate(warnings[1])

    with pytest.raises(BaselineError):
        _parse(document)


def test_parse_baseline_enforces_distribution_warning_owner_identity():
    document = _golden(1)
    distributions = cast(list[dict[str, Any]], document["distributions"])
    distributions[1]["warnings"][0]["target_identity"] = "alpha-pkg==1.0"

    with pytest.raises(BaselineError, match="inconsistent-warning"):
        _parse(document)


def test_parse_baseline_rejects_malformed_and_bounded_input():
    with pytest.raises(BaselineError, match="unsupported-encoding"):
        parse_baseline_json(b"\xff")
    with pytest.raises(BaselineError, match="size-limit"):
        parse_baseline_json(b" " * (MAX_BASELINE_BYTES + 1))
    with pytest.raises(BaselineError, match="unsupported-encoding"):
        parse_baseline_json(_golden(2).__repr__().encode("utf-16"))
    with pytest.raises(BaselineError, match="unsupported-encoding"):
        parse_baseline_json(b"\xef\xbb\xbf{}")
    with pytest.raises(BaselineError, match="integer-limit"):
        parse_baseline_json(b'{"schema_version": ' + b"9" * 5000 + b"}")


@pytest.mark.parametrize("as_bytes", [False, True])
def test_parse_baseline_rejects_json_escaped_lone_surrogates(as_bytes):
    document = _golden(1)
    context = cast(dict[str, Any], document["context"])
    context["platform"] = "\ud800"
    payload = json.dumps(document)
    if as_bytes:
        payload = payload.encode("utf-8")

    with pytest.raises(BaselineError, match="invalid-value"):
        parse_baseline_json(payload)


def test_load_baseline_keeps_file_paths_and_os_errors_out_of_diagnostics(tmp_path):
    missing = tmp_path / "credential-token-do-not-render.json"
    with pytest.raises(BaselineLoadError) as captured:
        load_baseline(missing)

    assert "credential-token" not in str(captured.value)
    assert captured.value.code == "read-failed"

    source = _ROOT / "tests" / "golden" / "analysis-result-v2-existing-prefix.json"
    assert load_baseline(source).schema_version == 2


def test_load_baseline_maps_close_failure_without_parsing_or_raw_cause(monkeypatch):
    source = _ROOT / "tests" / "golden" / "analysis-result-v2-existing-prefix.json"
    real_close = baseline_module.os.close
    parse_calls = 0

    def close_then_fail(descriptor: int) -> None:
        real_close(descriptor)
        raise OSError("private close detail")

    def unexpected_parse(_payload):
        nonlocal parse_calls
        parse_calls += 1
        raise AssertionError("parse must not run after close failure")

    monkeypatch.setattr(baseline_module.os, "close", close_then_fail)
    monkeypatch.setattr(baseline_module, "parse_baseline_json", unexpected_parse)

    with pytest.raises(BaselineLoadError) as captured:
        load_baseline(source)

    assert captured.value.code == "read-failed"
    assert captured.value.field == "file"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "private close detail" not in str(captured.value)
    assert parse_calls == 0


def test_load_baseline_body_error_wins_over_close_error(monkeypatch):
    source = _ROOT / "tests" / "golden" / "analysis-result-v2-existing-prefix.json"
    real_close = baseline_module.os.close
    body_failure = OSError("private body detail")

    def fail_body(_descriptor: int):
        raise body_failure

    def close_then_fail(descriptor: int) -> None:
        real_close(descriptor)
        raise OSError("private close detail")

    monkeypatch.setattr(baseline_module.os, "fstat", fail_body)
    monkeypatch.setattr(baseline_module.os, "close", close_then_fail)

    with pytest.raises(BaselineLoadError) as captured:
        load_baseline(source)

    assert captured.value.code == "read-failed"
    assert captured.value.__cause__ is body_failure


def test_load_baseline_open_failure_does_not_close(monkeypatch, tmp_path):
    source = tmp_path / "baseline.json"
    source.write_bytes(b"{}")
    close_calls = 0

    def fail_open(*_args):
        raise OSError("private open detail")

    def unexpected_close(_descriptor: int) -> None:
        nonlocal close_calls
        close_calls += 1

    monkeypatch.setattr(baseline_module.os, "open", fail_open)
    monkeypatch.setattr(baseline_module.os, "close", unexpected_close)

    with pytest.raises(BaselineLoadError) as captured:
        load_baseline(source)

    assert captured.value.code == "read-failed"
    assert close_calls == 0


def test_load_baseline_rejects_symlink_and_special_file_without_reading_them(tmp_path):
    source = _ROOT / "tests" / "golden" / "analysis-result-v2-existing-prefix.json"
    symlink = tmp_path / "baseline-link.json"
    symlink.symlink_to(source)
    with pytest.raises(BaselineLoadError, match="symlink"):
        load_baseline(symlink)

    if hasattr(os, "mkfifo"):
        fifo = tmp_path / "baseline.fifo"
        os.mkfifo(fifo)
        with pytest.raises(BaselineLoadError, match="not-regular-file"):
            load_baseline(fifo)


def test_load_baseline_detects_opened_file_race_and_supports_no_nofollow_fallback(
    monkeypatch,
):
    source = _ROOT / "tests" / "golden" / "analysis-result-v2-existing-prefix.json"
    original_fstat = baseline_module.os.fstat

    def changed_fstat(descriptor: int) -> os.stat_result:
        values = list(original_fstat(descriptor))
        values[1] += 1
        return os.stat_result(values)

    monkeypatch.setattr(baseline_module.os, "fstat", changed_fstat)
    with pytest.raises(BaselineLoadError, match="changed-file"):
        load_baseline(source)

    monkeypatch.undo()
    original_open = baseline_module.os.open
    opened_flags: list[int] = []

    def capture_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes], flags: int
    ) -> int:
        opened_flags.append(flags)
        return original_open(path, flags)

    monkeypatch.delattr(baseline_module.os, "O_NOFOLLOW", raising=False)
    monkeypatch.setattr(baseline_module.os, "open", capture_open)
    assert load_baseline(source).schema_version == 2
    assert opened_flags
