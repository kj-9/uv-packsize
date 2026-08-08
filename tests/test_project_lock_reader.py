from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from uv_packsize import project_lock_reader
from uv_packsize.models import DependencyGroupSelection
from uv_packsize.project_lock_reader import (
    ProjectLockInputError,
    ProjectLockInputErrorReason,
    read_project_lock,
)

PROJECT = """\
[project]
name = "Example_Project"

[project.optional-dependencies]
speed = []

[dependency-groups]
test = []
"""

FIXTURE_ROOT = Path(__file__).parent / "golden" / "project-lock"

LOCK = """\
version = 1
revision = 3
requires-python = ">=3.10"

[options]
prerelease-mode = "disallow"

[[package]]
name = "example-project"
version = "1.0.0"
source = { editable = "." }

[package.optional-dependencies]
speed = [{ name = "speed-dep" }]

[package.dev-dependencies]
test = [{ name = "test-dep" }]

[[package]]
name = "speed-dep"
version = "1.0.0"
source = { registry = "https://index.example.invalid/simple" }

[[package]]
name = "test-dep"
version = "1.0.0"
source = { registry = "https://index.example.invalid/simple" }
"""

# Representative output of ``uv 0.11.3 lock --offline`` for a project whose
# dependencies are resolved from a local wheelhouse.  It deliberately carries
# path-valued lock internals, but the reader may only return its safe selection
# projection and content fingerprint.
CURRENT_UV_LOCK = """\
version = 1
revision = 3
requires-python = ">=3.10"

[[package]]
name = "uv-packsize-fixture-root-a"
version = "1.0.0"
source = { registry = "/locked-fixtures/wheelhouse" }
dependencies = [{ name = "uv-packsize-fixture-shared" }]
wheels = [{ path = "/locked-fixtures/wheelhouse/uv_packsize_fixture_root_a-1.0.0-py3-none-any.whl" }]

[[package]]
name = "uv-packsize-fixture-shared"
version = "1.0.0"
source = { registry = "/locked-fixtures/wheelhouse" }
wheels = [{ path = "/locked-fixtures/wheelhouse/uv_packsize_fixture_shared-1.0.0-py3-none-any.whl" }]

[[package]]
name = "example-project"
version = "1.0.0"
source = { virtual = "." }
dependencies = [{ name = "uv-packsize-fixture-root-a" }]

[package.optional-dependencies]
speed = [{ name = "uv-packsize-fixture-shared" }]

[package.dev-dependencies]
test = [{ name = "uv-packsize-fixture-shared" }]

[package.metadata]
requires-dist = [
    { name = "uv-packsize-fixture-root-a", specifier = "==1.0.0" },
    { name = "uv-packsize-fixture-shared", marker = "extra == 'speed'", specifier = "==1.0.0" },
]
provides-extras = ["speed"]

[package.metadata.requires-dev]
test = [{ name = "uv-packsize-fixture-shared", specifier = "==1.0.0" }]
"""

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def write_inputs(
    tmp_path: Path, project: str = PROJECT, lock: str = LOCK
) -> tuple[Path, Path]:
    project_path = tmp_path / "pyproject.toml"
    lock_path = tmp_path / "uv.lock"
    project_path.write_text(project)
    lock_path.write_text(lock)
    return project_path, lock_path


def test_minimal_network_free_fixture_is_accepted():
    value = read_project_lock(FIXTURE_ROOT / "pyproject.toml", FIXTURE_ROOT / "uv.lock")

    assert value.root_package == "example-project"
    assert value.dependency_group_selection is DependencyGroupSelection.NONE


def test_accepts_this_repositorys_standard_project_and_lock_shape():
    value = read_project_lock(
        REPOSITORY_ROOT / "pyproject.toml",
        REPOSITORY_ROOT / "uv.lock",
        all_groups=True,
    )

    assert value.root_package == "uv-packsize"
    assert value.dependency_group_selection is DependencyGroupSelection.ALL
    assert value.dependency_groups == ("dev",)


def test_accepts_current_uv_local_wheel_lock_shape_without_exposing_paths(tmp_path):
    project, lock = write_inputs(tmp_path, lock=CURRENT_UV_LOCK)

    value = read_project_lock(project, lock, dependency_groups=("test",))

    assert value.root_package == "example-project"
    assert value.dependency_groups == ("test",)
    assert value.extras == ()
    assert "/locked-fixtures" not in repr(value)
    assert ".whl" not in repr(value)


def test_reads_only_safe_selection_and_domain_separated_lock_identity(tmp_path):
    project, lock = write_inputs(tmp_path)

    value = read_project_lock(
        project,
        lock,
        workspace_member="Example_Project",
        dependency_groups=("Test",),
        extras=("Speed",),
    )

    assert value.root_package == "example-project"
    assert value.workspace_member == "example-project"
    assert value.dependency_group_selection is DependencyGroupSelection.EXPLICIT
    assert value.dependency_groups == ("test",)
    assert value.extras == ("speed",)
    assert len(value.lock_identity) == 64
    assert value.lock_identity != sha256(lock.read_bytes()).hexdigest()
    assert "index.example.invalid" not in repr(value)
    assert str(lock) not in repr(value)


def test_all_groups_expands_the_verified_effective_group_set(tmp_path):
    project, lock = write_inputs(tmp_path)

    value = read_project_lock(project, lock, all_groups=True)

    assert value.dependency_group_selection is DependencyGroupSelection.ALL
    assert value.dependency_groups == ("test",)


@pytest.mark.parametrize("default_groups", ['["test"]', '"all"'])
def test_rejects_tool_uv_default_groups_without_reflecting_raw_input(
    tmp_path, default_groups
):
    project, lock = write_inputs(
        tmp_path,
        project=(
            PROJECT
            + "\n[tool.uv]\n"
            + f"default-groups = {default_groups}\n"
            + 'private-selection = "https://user:token@example.invalid/group"\n'
        ),
    )

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.INVALID_PROJECT
    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)


def test_accepts_unrelated_tool_uv_settings(tmp_path):
    project, lock = write_inputs(
        tmp_path,
        project=PROJECT + "\n[tool.uv]\nmanaged = true\n",
    )

    value = read_project_lock(project, lock)

    assert value.dependency_group_selection is DependencyGroupSelection.NONE


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dependency_groups": ["test"]},
        {"extras": ["speed"]},
        {"all_groups": 1},
    ],
)
def test_rejects_noncanonical_selection_container_types(tmp_path, kwargs):
    project, lock = write_inputs(tmp_path)

    with pytest.raises(TypeError):
        read_project_lock(project, lock, **kwargs)


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        (
            {"dependency_groups": ("missing",)},
            ProjectLockInputErrorReason.INVALID_SELECTION,
        ),
        ({"extras": ("missing",)}, ProjectLockInputErrorReason.INVALID_SELECTION),
        ({"workspace_member": "other"}, ProjectLockInputErrorReason.INVALID_SELECTION),
        (
            {"dependency_groups": ("test", "Test")},
            ProjectLockInputErrorReason.AMBIGUOUS_SELECTION,
        ),
        (
            {"dependency_groups": ("test",), "all_groups": True},
            ProjectLockInputErrorReason.INVALID_SELECTION,
        ),
    ],
)
def test_rejects_invalid_or_ambiguous_selection_without_echoing_labels(
    tmp_path, kwargs, reason
):
    project, lock = write_inputs(tmp_path)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock, **kwargs)

    assert captured.value.reason is reason
    assert "missing" not in str(captured.value)
    assert "other" not in str(captured.value)


@pytest.mark.parametrize(
    "replacement",
    [
        "version = 2\nrevision = 3",
        "version = 1\nrevision = 4",
        "version = 1\nrevision = 3\npackage = []",
        LOCK.replace(
            'source = { registry = "https://index.example.invalid/simple" }',
            'source = { git = "https://token@example.invalid/repo" }',
        ),
        LOCK.replace(
            'source = { registry = "https://index.example.invalid/simple" }',
            'source = { editable = "../private-member" }',
        ),
        LOCK.replace('name = "speed-dep"', 'name = "test-dep"'),
    ],
)
def test_rejects_unsupported_or_ambiguous_lock_semantics_without_reflection(
    tmp_path, replacement
):
    project, lock = write_inputs(tmp_path, lock=replacement)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason in {
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputErrorReason.AMBIGUOUS_SELECTION,
    }
    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)


def test_rejects_project_and_lock_group_or_extra_mismatch(tmp_path):
    project, lock = write_inputs(
        tmp_path, lock=LOCK.replace("test = [{ name", "other = [{ name")
    )

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK


@pytest.mark.parametrize(
    ("project_text", "lock_text", "reason"),
    [
        (
            PROJECT.replace(
                'name = "Example_Project"',
                'name = "Example_Project"\ndynamic = ["optional-dependencies"]',
            ),
            LOCK,
            ProjectLockInputErrorReason.INVALID_PROJECT,
        ),
        (
            PROJECT + '\n[build-system]\nrequires = []\nunknown = "not-supported"\n',
            LOCK,
            ProjectLockInputErrorReason.INVALID_PROJECT,
        ),
        (
            PROJECT,
            LOCK.replace(
                'prerelease-mode = "disallow"',
                'prerelease-mode = "disallow"\nunknown = "not-supported"',
            ),
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ),
        (
            PROJECT,
            LOCK.replace(
                'test = [{ name = "test-dep" }]\n\n[[package]]',
                'test = [{ name = "test-dep" }]\n\n'
                "[package.metadata.requires-dev]\n"
                'other = [{ name = "test-dep" }]\n\n[[package]]',
            ),
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ),
    ],
)
def test_rejects_unknown_or_conflicting_selection_semantics(
    tmp_path, project_text, lock_text, reason
):
    project, lock = write_inputs(tmp_path, project=project_text, lock=lock_text)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is reason
    assert "not-supported" not in str(captured.value)


@pytest.mark.parametrize(
    "replacement",
    [
        LOCK + '\nunknown = "https://user:token@example.invalid/top-level"\n',
        LOCK.replace(
            'version = "1.0.0"\nsource = { editable = "." }',
            'version = "1.0.0"\nunknown = "https://user:token@example.invalid/package"\nsource = { editable = "." }',
            1,
        ),
        LOCK.replace(
            '{ name = "test-dep" }',
            '{ name = "test-dep", unknown = "https://user:token@example.invalid/dependency" }',
        ),
        LOCK.replace('{ name = "test-dep" }', '{ version = "1.0.0" }'),
        LOCK.replace('source = { editable = "." }', 'source = { editable = ".." }'),
        LOCK.replace(
            'source = { registry = "https://index.example.invalid/simple" }',
            'source = { registry = "https://index.example.invalid/simple", unknown = "secret" }',
        ),
    ],
)
def test_rejects_unknown_or_incomplete_closed_subset_without_reflection(
    tmp_path, replacement
):
    project, lock = write_inputs(tmp_path, lock=replacement)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK
    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)


@pytest.mark.parametrize(
    "replacement",
    [
        CURRENT_UV_LOCK.replace(
            'source = { virtual = "." }', 'source = { virtual = "../project" }'
        ),
        CURRENT_UV_LOCK.replace(
            'wheels = [{ path = "/locked-fixtures/wheelhouse/uv_packsize_fixture_root_a-1.0.0-py3-none-any.whl" }]',
            'wheels = [{ path = "/locked-fixtures/wheelhouse/uv_packsize_fixture_root_a-1.0.0-py3-none-any.whl", hash = "sha256:secret" }]',
        ),
        CURRENT_UV_LOCK.replace('specifier = "==1.0.0"', 'specifier = ""', 1),
    ],
)
def test_rejects_unknown_or_invalid_current_uv_lock_variants_without_reflection(
    tmp_path, replacement
):
    project, lock = write_inputs(tmp_path, lock=replacement)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK
    assert "/locked-fixtures" not in str(captured.value)
    assert "secret" not in str(captured.value)


@pytest.mark.parametrize(
    "project_text",
    [
        PROJECT + '\nunknown = "https://user:token@example.invalid/top-level"\n',
        PROJECT.replace(
            'name = "Example_Project"',
            'name = "Example_Project"\nunknown = "https://user:token@example.invalid/project"',
        ),
        PROJECT.replace('name = "Example_Project"\n', ""),
    ],
)
def test_rejects_unknown_or_incomplete_project_subset_without_reflection(
    tmp_path, project_text
):
    project, lock = write_inputs(tmp_path, project=project_text)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.INVALID_PROJECT
    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)


def test_rejects_symlink_and_non_regular_inputs_without_paths(tmp_path):
    project, lock = write_inputs(tmp_path)
    linked = tmp_path / "linked.lock"
    linked.symlink_to(lock)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, linked)

    assert captured.value.reason is ProjectLockInputErrorReason.NOT_REGULAR_FILE
    assert str(linked) not in str(captured.value)
    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, tmp_path)
    assert captured.value.reason is ProjectLockInputErrorReason.NOT_REGULAR_FILE


def test_rejects_symlinked_parent_components_without_paths(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    project, lock = write_inputs(inputs)
    linked_parent = tmp_path / "linked-inputs"
    linked_parent.symlink_to(inputs, target_is_directory=True)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(linked_parent / project.name, linked_parent / lock.name)

    assert captured.value.reason is ProjectLockInputErrorReason.NOT_REGULAR_FILE
    assert str(linked_parent) not in str(captured.value)


def test_rejects_file_replaced_between_identity_check_and_open(tmp_path, monkeypatch):
    project, lock = write_inputs(tmp_path)
    replacement = tmp_path / "replacement.lock"
    replacement.write_text(LOCK)
    original_open = project_lock_reader.os.open

    def replace_then_open(path, flags):
        if Path(path) == lock:
            replacement.replace(lock)
        return original_open(path, flags)

    monkeypatch.setattr(project_lock_reader.os, "open", replace_then_open)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.CHANGED_FILE
    assert str(lock) not in str(captured.value)


def test_rejects_in_place_rewrite_observable_after_read(tmp_path, monkeypatch):
    project, lock = write_inputs(tmp_path)
    original_read = project_lock_reader.os.read
    mutated = False

    def read_then_rewrite(descriptor, size):
        nonlocal mutated
        chunk = original_read(descriptor, size)
        if (
            chunk
            and not mutated
            and project_lock_reader.os.fstat(descriptor).st_ino == lock.stat().st_ino
        ):
            mutated = True
            lock.write_text(LOCK.replace('version = "1.0.0"', 'version = "1.0.1"'))
        return chunk

    monkeypatch.setattr(project_lock_reader.os, "read", read_then_rewrite)

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert captured.value.reason is ProjectLockInputErrorReason.CHANGED_FILE
    assert str(lock) not in str(captured.value)


def test_rejects_raw_secret_like_toml_in_all_failures(tmp_path):
    project, lock = write_inputs(
        tmp_path,
        lock='version = 1\nrevision = 3\nsecret = "https://user:token@example.invalid"',
    )

    with pytest.raises(ProjectLockInputError) as captured:
        read_project_lock(project, lock)

    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)
