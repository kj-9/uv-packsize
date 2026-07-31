from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    BuildPolicy,
    CaseRule,
    Completeness,
    DistributionResult,
    DuplicateOwnership,
    ExistingPrefixContext,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
    WarningCode,
    WarningTargetKind,
)


def context(**overrides: Any) -> ResolutionContext:
    values: dict[str, Any] = {
        "requirements": ("example>=1",),
        "python_version": "3.12.4",
        "platform": "linux",
        "architecture": "x86_64",
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
        "uv_version": "0.11.3",
        "build_policy": BuildPolicy.ALLOW_BUILD,
        "compile_bytecode": True,
    }
    values.update(overrides)
    return ResolutionContext(**values)


def existing_prefix_context(**overrides: Any) -> ExistingPrefixContext:
    values: dict[str, Any] = {
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
    }
    values.update(overrides)
    return ExistingPrefixContext(**values)


def file_entry(
    identity: str,
    logical_bytes: int,
    *,
    path: str | None = None,
    category: FileCategory = FileCategory.PYTHON,
) -> FileEntry:
    return FileEntry(
        path=path or identity,
        canonical_identity=identity,
        logical_bytes=logical_bytes,
        category=category,
        origin=FileOrigin.RECORD,
    )


def test_models_are_immutable_and_defensively_store_tuples():
    requirements = ["example"]
    files = [file_entry("site-packages/example.py", 10)]
    resolution = context(requirements=cast(Any, requirements))
    distribution = DistributionResult(
        name="Example_Pkg", version="1.0", files=cast(Any, files)
    )
    result = AnalysisResult(context=resolution, distributions=cast(Any, [distribution]))

    requirements.append("unexpected")
    files.append(file_entry("site-packages/other.py", 20))

    assert resolution.requirements == ("example",)
    assert distribution.name == "example-pkg"
    assert distribution.files == (file_entry("site-packages/example.py", 10),)
    assert result.distributions == (distribution,)
    with pytest.raises(FrozenInstanceError):
        cast(Any, distribution).name = "changed"


def test_existing_prefix_context_is_immutable_and_does_not_claim_resolution_inputs():
    observed = existing_prefix_context(
        python_version="3.12.4",
        platform="linux",
        architecture="x86_64",
    )

    assert observed.python_version == "3.12.4"
    assert observed.platform == "linux"
    assert observed.architecture == "x86_64"
    assert not hasattr(observed, "requirements")
    assert not hasattr(observed, "uv_version")
    assert hash(observed)
    with pytest.raises(FrozenInstanceError):
        cast(Any, observed).platform = "changed"


@pytest.mark.parametrize(
    ("field_name", "value", "error"),
    [
        ("python_version", "", ValueError),
        ("platform", " linux", ValueError),
        ("architecture", "x86_64 ", ValueError),
        ("python_version", "safe\0value", ValueError),
        ("platform", cast(Any, 3), ValueError),
        ("python_version", "/private/secret-prefix", ValueError),
        ("platform", "C:\\Users\\secret", ValueError),
        ("architecture", "C:secret", ValueError),
        ("architecture", "\\\\server\\secret", ValueError),
        ("python_version", "../secret", ValueError),
        ("platform", "./secret", ValueError),
        ("architecture", "~secret", ValueError),
        ("python_version", "safe/value", ValueError),
        ("platform", "safe\\value", ValueError),
    ],
)
def test_existing_prefix_context_validates_optional_observations(
    field_name, value, error
):
    with pytest.raises(error):
        existing_prefix_context(**{field_name: value})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("python_version", "3.12"),
        ("platform", "linux"),
        ("platform", "darwin"),
        ("platform", "win32"),
        ("architecture", "x86_64"),
        ("architecture", "arm64"),
        ("architecture", "AMD64"),
    ],
)
def test_existing_prefix_context_accepts_safe_optional_observations(field_name, value):
    observed = existing_prefix_context(**{field_name: value})

    assert getattr(observed, field_name) == value


@pytest.mark.parametrize("secret_path", ("/private/secret-prefix", "C:secret"))
def test_existing_prefix_context_path_rejection_does_not_echo_the_value(secret_path):
    with pytest.raises(ValueError) as error:
        existing_prefix_context(platform=secret_path)

    assert secret_path not in str(error.value)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("path_flavor", cast(Any, "posix"), "PathFlavor"),
        ("case_rule", cast(Any, "sensitive"), "CaseRule"),
    ],
)
def test_existing_prefix_context_requires_path_and_case_enums(
    field_name, value, message
):
    with pytest.raises(TypeError, match=message):
        existing_prefix_context(**{field_name: value})


def test_analysis_accepts_existing_prefix_context_and_remains_deterministic():
    first = DistributionResult(name="z-dist", version="1", files=())
    second = DistributionResult(name="a-dist", version="1", files=())
    observed = existing_prefix_context()

    forward = AnalysisResult(context=observed, distributions=(first, second))
    reverse = AnalysisResult(context=observed, distributions=(second, first))

    assert forward == reverse
    assert hash(forward) == hash(reverse)
    assert forward.context is observed


def test_distribution_total_is_derived_from_deterministically_ordered_files():
    distribution = DistributionResult(
        name="Example.Pkg",
        version="1.0",
        files=(
            file_entry("z.py", 7),
            file_entry("a.py", 5),
        ),
    )

    assert [file.canonical_identity for file in distribution.files] == ["a.py", "z.py"]
    assert distribution.total_logical_bytes == 12
    assert "total_logical_bytes" not in distribution.__dataclass_fields__


def test_global_total_deduplicates_shared_ownership_and_explains_it():
    shared_a = file_entry("site-packages/shared.py", 40, path="Shared.py")
    shared_b = file_entry("site-packages/shared.py", 40, path="shared.py")
    first = DistributionResult(
        name="first",
        version="1",
        files=(shared_a, file_entry("site-packages/first.py", 10)),
    )
    second = DistributionResult(
        name="second",
        version="2",
        files=(shared_b, file_entry("site-packages/second.py", 20)),
    )

    result = AnalysisResult(context=context(), distributions=(second, first))

    assert first.total_logical_bytes == 50
    assert second.total_logical_bytes == 60
    assert result.total_logical_bytes == 70
    assert result.warnings == (
        AnalysisWarning(
            code=WarningCode.DUPLICATE_OWNERSHIP,
            target_kind=WarningTargetKind.FILE,
            target_identity="site-packages/shared.py",
        ),
    )
    assert result.duplicate_ownerships == (
        DuplicateOwnership(
            canonical_identity="site-packages/shared.py",
            owners=("first", "second"),
        ),
    )
    owners = {
        distribution.name
        for distribution in result.distributions
        if any(
            file.canonical_identity == "site-packages/shared.py"
            for file in distribution.files
        )
    }
    assert owners == {"first", "second"}
    assert result.completeness is Completeness.COMPLETE


def test_same_global_identity_with_different_sizes_is_rejected():
    first = DistributionResult(
        name="first", version="1", files=(file_entry("shared", 40),)
    )
    second = DistributionResult(
        name="second", version="1", files=(file_entry("shared", 41),)
    )

    with pytest.raises(ValueError, match="same canonical identity"):
        AnalysisResult(context=context(), distributions=(first, second))


def test_same_global_identity_with_different_categories_is_rejected():
    first = DistributionResult(
        name="first", version="1", files=(file_entry("shared", 40),)
    )
    second = DistributionResult(
        name="second",
        version="1",
        files=(file_entry("shared", 40, category=FileCategory.DATA),),
    )

    with pytest.raises(ValueError, match="same canonical identity"):
        AnalysisResult(context=context(), distributions=(first, second))


def test_same_global_identity_with_different_symlink_targets_is_rejected():
    first_file = FileEntry(
        path="shared",
        canonical_identity="shared",
        logical_bytes=40,
        category=FileCategory.PYTHON,
        origin=FileOrigin.RECORD,
        symlink_target="target-a",
    )
    second_file = FileEntry(
        path="shared",
        canonical_identity="shared",
        logical_bytes=40,
        category=FileCategory.PYTHON,
        origin=FileOrigin.RECORD,
        symlink_target="target-b",
    )

    with pytest.raises(ValueError, match="same canonical identity"):
        AnalysisResult(
            context=context(),
            distributions=(
                DistributionResult(name="first", version="1", files=(first_file,)),
                DistributionResult(name="second", version="1", files=(second_file,)),
            ),
        )


def test_duplicate_identity_within_distribution_is_rejected():
    with pytest.raises(ValueError, match="duplicate canonical identities"):
        DistributionResult(
            name="example",
            version="1",
            files=(
                file_entry("shared", 40, path="first"),
                file_entry("shared", 40, path="second"),
            ),
        )


def test_duplicate_normalized_distribution_name_is_rejected():
    first = DistributionResult(name="Example_Pkg", version="1", files=())
    second = DistributionResult(name="example.pkg", version="2", files=())

    with pytest.raises(ValueError, match="duplicate distribution names"):
        AnalysisResult(context=context(), distributions=(first, second))


@pytest.mark.parametrize("field", ["path", "canonical_identity"])
def test_file_entry_rejects_empty_identifiers(field):
    values: dict[str, Any] = {
        "path": "example.py",
        "canonical_identity": "example.py",
        "logical_bytes": 1,
        "category": FileCategory.PYTHON,
        "origin": FileOrigin.RECORD,
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        FileEntry(**values)


@pytest.mark.parametrize(
    "identity",
    [
        "/absolute/path",
        "C:/absolute/path",
        "a\\b",
        "a//b",
        "./a",
        "a/./b",
        "a/../b",
        "a/",
        "a\0b",
    ],
)
def test_file_entry_rejects_noncanonical_lexical_identity(identity):
    with pytest.raises(ValueError, match="canonical_identity"):
        file_entry(identity, 1, path="valid/path")


def test_file_entry_allows_whitespace_in_lexical_filename():
    entry = file_entry("site-packages/ file ", 1, path="site-packages/ file ")

    assert entry.path.endswith(" file ")


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/path",
        "C:/absolute/path",
        "a\\b",
        "a//b",
        "./a",
        "a/../b",
        "a\0b",
    ],
)
def test_file_entry_rejects_noncanonical_display_path(path):
    with pytest.raises(ValueError, match="path"):
        file_entry("valid/path", 1, path=path)


@pytest.mark.parametrize("logical_bytes", [-1, 1.5, True])
def test_file_entry_rejects_invalid_size(logical_bytes):
    with pytest.raises(ValueError, match="logical_bytes"):
        file_entry("example.py", cast(Any, logical_bytes))


@pytest.mark.parametrize("name", ["", " ", "---", "._-"])
def test_distribution_rejects_invalid_name(name):
    with pytest.raises(ValueError, match="name"):
        DistributionResult(name=name, version="1", files=())


def test_distribution_rejects_empty_version():
    with pytest.raises(ValueError, match="version"):
        DistributionResult(name="example", version=" ", files=())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"requirements": ()}, "requirements"),
        ({"requirements": ("",)}, "requirements"),
        ({"python_version": ""}, "python_version"),
        ({"platform": ""}, "platform"),
        ({"architecture": ""}, "architecture"),
        ({"uv_version": ""}, "uv_version"),
        ({"resolution_strategy": ""}, "resolution_strategy"),
        ({"extras": ("",)}, "extras"),
        ({"index_identifiers": ("",)}, "index_identifiers"),
    ],
)
def test_resolution_context_rejects_empty_values(overrides, message):
    with pytest.raises(ValueError, match=message):
        context(**overrides)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path_flavor", "posix", "PathFlavor"),
        ("case_rule", "sensitive", "CaseRule"),
    ],
)
def test_resolution_context_rejects_untyped_path_semantics(field, value, message):
    with pytest.raises(TypeError, match=message):
        context(**{field: value})


def test_resolution_context_preserves_requirements_and_canonicalizes_sets():
    resolution = context(
        requirements=("second", "first", "second"),
        extras=("Z_extra", "a-extra", "z.extra"),
        index_identifiers=("secondary", "primary", "secondary"),
        build_policy=BuildPolicy.WHEEL_ONLY,
    )

    assert resolution.requirements == ("second", "first", "second")
    assert resolution.extras == ("a-extra", "z-extra")
    assert resolution.index_identifiers == ("primary", "secondary")
    assert resolution.build_policy is BuildPolicy.WHEEL_ONLY


@pytest.mark.parametrize("field", ["requirements", "extras", "index_identifiers"])
def test_resolution_context_rejects_plain_string_collection(field):
    with pytest.raises(TypeError, match="tuple of strings"):
        context(**{field: cast(Any, "not-a-tuple")})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("python_version", " 3.12"),
        ("platform", "linux "),
        ("architecture", "x86\0_64"),
        ("uv_version", " 0.11.3"),
        ("resolution_strategy", "highest "),
    ],
)
def test_resolution_context_rejects_whitespace_and_nul(field, value):
    with pytest.raises(ValueError, match=field):
        context(**{field: value})


def test_warnings_are_typed_deduplicated_and_deterministically_sorted():
    missing_record = AnalysisWarning(
        code=WarningCode.MISSING_RECORD,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity="example==1",
    )
    missing_file = AnalysisWarning(
        code=WarningCode.MISSING_FILE,
        target_kind=WarningTargetKind.FILE,
        target_identity="a-file",
    )
    distribution = DistributionResult(
        name="example",
        version="1",
        files=(),
        warnings=(missing_record, missing_file, missing_record),
    )
    result = AnalysisResult(
        context=context(),
        distributions=(distribution,),
        warnings=(missing_record, missing_file, missing_record),
    )

    expected = (missing_file, missing_record)
    assert distribution.warnings == expected
    assert result.warnings == expected
    assert distribution.completeness is Completeness.INCOMPLETE
    assert result.completeness is Completeness.INCOMPLETE


def test_distribution_incompleteness_propagates_without_copying_warning():
    warning = AnalysisWarning(
        code=WarningCode.MISSING_RECORD,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity="example==1",
    )
    distribution = DistributionResult(
        name="example", version="1", files=(), warnings=(warning,)
    )
    result = AnalysisResult(context=context(), distributions=(distribution,))

    assert result.warnings == ()
    assert result.completeness is Completeness.INCOMPLETE


def test_distribution_warning_must_target_its_distribution():
    for code in (
        WarningCode.INVALID_METADATA,
        WarningCode.MISSING_RECORD,
        WarningCode.MISSING_METADATA,
        WarningCode.INVALID_RECORD,
        WarningCode.INVALID_RECORD_PATH,
        WarningCode.FILESYSTEM_LAYOUT_ERROR,
        WarningCode.MISSING_RECORD_SELF_ENTRY,
        WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
    ):
        warning = AnalysisWarning(
            code=code,
            target_kind=WarningTargetKind.DISTRIBUTION,
            target_identity="other==1",
        )
        with pytest.raises(ValueError, match="must match its distribution"):
            DistributionResult(
                name="example", version="1", files=(), warnings=(warning,)
            )


def test_warning_rejects_free_form_code_and_empty_target():
    with pytest.raises(TypeError, match="WarningCode"):
        AnalysisWarning(
            code=cast(Any, "missing-file"),
            target_kind=WarningTargetKind.FILE,
            target_identity="file",
        )
    with pytest.raises(ValueError, match="target_identity"):
        AnalysisWarning(
            code=WarningCode.MISSING_FILE,
            target_kind=WarningTargetKind.FILE,
            target_identity="",
        )


def test_warning_rejects_wrong_target_shape():
    with pytest.raises(ValueError, match="requires a distribution target"):
        AnalysisWarning(
            code=WarningCode.MISSING_RECORD,
            target_kind=WarningTargetKind.FILE,
            target_identity="example",
        )


def test_duplicate_ownership_warning_cannot_be_supplied_by_caller():
    warning = AnalysisWarning(
        code=WarningCode.DUPLICATE_OWNERSHIP,
        target_kind=WarningTargetKind.FILE,
        target_identity="shared",
    )
    with pytest.raises(ValueError, match="derived by AnalysisResult"):
        DistributionResult(name="example", version="1", files=(), warnings=(warning,))
    with pytest.raises(ValueError, match="derived by AnalysisResult"):
        AnalysisResult(context=context(), distributions=(), warnings=(warning,))


def test_distribution_warning_target_name_is_normalized():
    warning = AnalysisWarning(
        code=WarningCode.MISSING_RECORD,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity="Example_Pkg==1",
    )

    assert warning.target_identity == "example-pkg==1"


def test_input_permutations_produce_equal_hashable_results():
    a_file = file_entry("a", 1)
    z_file = file_entry("z", 2)
    first_warning = AnalysisWarning(
        code=WarningCode.MISSING_FILE,
        target_kind=WarningTargetKind.FILE,
        target_identity="z",
    )
    second_warning = AnalysisWarning(
        code=WarningCode.MISSING_FILE,
        target_kind=WarningTargetKind.FILE,
        target_identity="a",
    )
    left = AnalysisResult(
        context=context(),
        distributions=(
            DistributionResult(name="z-dist", version="1", files=(z_file, a_file)),
            DistributionResult(name="a-dist", version="1", files=()),
        ),
        warnings=(first_warning, second_warning),
    )
    right = AnalysisResult(
        context=context(),
        distributions=(
            DistributionResult(name="a-dist", version="1", files=()),
            DistributionResult(name="z-dist", version="1", files=(a_file, z_file)),
        ),
        warnings=(second_warning, first_warning),
    )

    assert left == right
    assert hash(left) == hash(right)


def test_duplicate_ownership_relation_sorts_owners_and_is_hashable():
    relation = DuplicateOwnership(
        canonical_identity="shared",
        owners=("Z_Pkg", "a.pkg", "z-pkg"),
    )

    assert relation.owners == ("a-pkg", "z-pkg")
    assert hash(relation)


def test_symlink_target_is_separate_from_lexical_canonical_identity():
    identity = "lib/Example.py"
    entry = FileEntry(
        path="lib/Example.py",
        canonical_identity=identity,
        logical_bytes=0,
        category=FileCategory.OTHER,
        origin=FileOrigin.DISCOVERED,
        symlink_target="../shared/example.py",
    )

    assert entry.canonical_identity == identity
    assert entry.symlink_target == "../shared/example.py"
