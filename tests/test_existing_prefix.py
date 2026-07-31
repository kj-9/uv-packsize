import csv
import os
from pathlib import Path
from typing import cast

import pytest

from uv_packsize.analysis import analyze_installed_environment
from uv_packsize.existing_prefix import (
    ExistingPrefixDiscoveryError,
    ExistingPrefixDiscoveryErrorCode,
    ExistingPrefixEnvironment,
    _relative_parts,
    discover_existing_prefix,
)
from uv_packsize.inventory import InventoryLayout
from uv_packsize.models import CaseRule, ExistingPrefixContext, PathFlavor


def host_flavor() -> PathFlavor:
    return PathFlavor.WINDOWS if os.name == "nt" else PathFlavor.POSIX


def make_prefix(tmp_path: Path) -> tuple[Path, Path, Path]:
    prefix = tmp_path / "prefix"
    first = prefix / "lib" / "python3.14" / "site-packages"
    second = prefix / "lib" / "python3.14" / "plat-packages"
    first.mkdir(parents=True)
    second.mkdir()
    return prefix, first, second


def discover(prefix: Path, sites: tuple[str, ...], **overrides: object):
    values: dict[str, object] = {
        "prefix": prefix,
        "site_packages_relative": sites,
        "path_flavor": host_flavor(),
        "case_rule": CaseRule.SENSITIVE,
    }
    values.update(overrides)
    return discover_existing_prefix(**values)  # type: ignore[arg-type]


def assert_discovery_error(
    error: pytest.ExceptionInfo[ExistingPrefixDiscoveryError],
    code: ExistingPrefixDiscoveryErrorCode,
) -> None:
    assert error.value.code is code
    assert error.value.target in {"measurement-prefix", "path-flavor", "site-packages"}
    assert str(error.value) == f"{code.value}: {error.value.target}"
    assert repr(error.value) == (f"ExistingPrefixDiscoveryError({str(error.value)!r})")


def test_discovers_multiple_sites_in_deterministic_order_and_unknown_context(tmp_path):
    prefix, first, second = make_prefix(tmp_path)

    environment = discover(
        prefix,
        ("lib/python3.14/site-packages", "lib/python3.14/plat-packages"),
    )
    reordered = discover(
        prefix,
        ("lib/python3.14/plat-packages", "lib/python3.14/site-packages"),
    )

    assert environment.layouts == reordered.layouts
    assert environment.layouts == tuple(
        sorted(
            environment.layouts, key=lambda layout: str(layout.physical_site_packages)
        )
    )
    assert {layout.physical_site_packages for layout in environment.layouts} == {
        first,
        second,
    }
    assert environment.context == ExistingPrefixContext(
        path_flavor=host_flavor(), case_rule=CaseRule.SENSITIVE
    )
    assert environment.context.python_version is None
    assert environment.context.platform is None
    assert environment.context.architecture is None


def test_prefix_path_is_canonicalized_from_the_current_working_directory(
    tmp_path, monkeypatch
):
    prefix, site, _ = make_prefix(tmp_path)
    monkeypatch.chdir(tmp_path)

    environment = discover(Path("prefix"), ("lib/python3.14/site-packages",))

    assert environment.layouts[0].physical_prefix == prefix.resolve()
    assert environment.layouts[0].physical_site_packages == site.resolve()


def test_parent_symlink_is_canonicalized_before_it_can_be_replaced(tmp_path):
    target_parent = tmp_path / "target-parent"
    prefix, site, _ = make_prefix(target_parent)
    linked_parent = tmp_path / "linked-parent"
    try:
        linked_parent.symlink_to(target_parent, target_is_directory=True)
    except OSError:
        pytest.skip()

    environment = discover(linked_parent / "prefix", ("lib/python3.14/site-packages",))
    linked_parent.unlink()

    assert environment.layouts[0].physical_prefix == prefix.resolve()
    assert environment.layouts[0].physical_site_packages == site.resolve()


def test_prefix_requires_path_not_string(tmp_path):
    prefix, _, _ = make_prefix(tmp_path)
    with pytest.raises(TypeError, match="prefix must be a Path"):
        discover(cast(Path, str(prefix)), ("lib/python3.14/site-packages",))


def test_environment_repr_does_not_leak_prefix_paths(tmp_path):
    prefix = tmp_path / "super-secret-prefix"
    site = prefix / "lib" / "super-secret-site"
    site.mkdir(parents=True)

    environment = discover(prefix, ("lib/super-secret-site",))

    assert "super-secret" not in repr(environment)
    assert str(prefix) not in repr(environment)


def test_requires_host_native_path_flavor_before_accessing_prefix(tmp_path):
    unsupported = (
        PathFlavor.WINDOWS if host_flavor() is PathFlavor.POSIX else PathFlavor.POSIX
    )
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(
            tmp_path / "does-not-exist", ("site-packages",), path_flavor=unsupported
        )
    assert_discovery_error(
        error, ExistingPrefixDiscoveryErrorCode.HOST_PATH_FLAVOR_MISMATCH
    )


def test_preserves_explicit_case_rule_without_case_probe(tmp_path):
    prefix, _, _ = make_prefix(tmp_path)
    environment = discover(
        prefix, ("lib/python3.14/site-packages",), case_rule=CaseRule.INSENSITIVE
    )
    assert environment.context.case_rule is CaseRule.INSENSITIVE
    assert environment.layouts[0].case_rule is CaseRule.INSENSITIVE


@pytest.mark.parametrize(
    "relative",
    (
        "Lib:stream",
        "Lib\x01site-packages",
        "Lib<name",
        "Lib.",
        "Lib ",
        "con",
        "PRN.txt",
        "aux.py",
        "com1",
        "LPT9.log",
    ),
)
def test_windows_relative_components_reject_unsafe_names_host_independently(relative):
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        _relative_parts(relative, PathFlavor.WINDOWS)
    assert_discovery_error(
        error, ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES
    )


@pytest.mark.parametrize(
    ("relative", "expected"),
    (
        ("Lib\\site-packages", ("Lib", "site-packages")),
        ("Lib\\python3.12\\site-packages", ("Lib", "python3.12", "site-packages")),
    ),
)
def test_windows_relative_components_accept_safe_native_paths_host_independently(
    relative, expected
):
    assert _relative_parts(relative, PathFlavor.WINDOWS) == expected


@pytest.mark.parametrize(
    "relative",
    (
        "",
        ".",
        "./site-packages",
        "../site-packages",
        "/site-packages",
        "a//b",
        "a/../b",
        "C:\\site-packages",
        "\\\\server\\share",
    ),
)
def test_rejects_malformed_or_non_native_site_paths(tmp_path, relative):
    prefix, _, _ = make_prefix(tmp_path)
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(prefix, (relative,))
    assert_discovery_error(
        error, ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES
    )


def test_rejects_prefix_site_and_intermediate_symlinks(tmp_path):
    prefix, site, _ = make_prefix(tmp_path)
    linked_prefix = tmp_path / "linked-prefix"
    linked_site = prefix / "linked-site"
    linked_intermediate = prefix / "linked-lib"
    try:
        linked_prefix.symlink_to(prefix, target_is_directory=True)
        linked_site.symlink_to(site, target_is_directory=True)
        linked_intermediate.symlink_to(prefix / "lib", target_is_directory=True)
    except OSError:
        pytest.skip()

    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(linked_prefix, ("lib/python3.14/site-packages",))
    assert_discovery_error(error, ExistingPrefixDiscoveryErrorCode.INVALID_PREFIX)
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(prefix, ("linked-site",))
    assert_discovery_error(error, ExistingPrefixDiscoveryErrorCode.SYMLINK_NOT_ALLOWED)
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(prefix, ("linked-lib/python3.14/site-packages",))
    assert_discovery_error(error, ExistingPrefixDiscoveryErrorCode.SYMLINK_NOT_ALLOWED)


def test_rejects_missing_nondirectory_and_duplicate_sites(tmp_path):
    prefix, _, _ = make_prefix(tmp_path)
    file_site = prefix / "file-site"
    file_site.write_text("not a directory")

    for relative, code in (
        ("missing", ExistingPrefixDiscoveryErrorCode.SITE_PACKAGES_NOT_FOUND),
        ("file-site", ExistingPrefixDiscoveryErrorCode.SITE_PACKAGES_NOT_DIRECTORY),
    ):
        with pytest.raises(ExistingPrefixDiscoveryError) as error:
            discover(prefix, (relative,))
        assert_discovery_error(error, code)
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(
            prefix,
            ("lib/python3.14/site-packages", "lib/python3.14/site-packages"),
        )
    assert_discovery_error(
        error, ExistingPrefixDiscoveryErrorCode.DUPLICATE_SITE_PACKAGES
    )


def test_case_rule_aliases_are_rejected_when_the_host_can_represent_them(tmp_path):
    prefix, _, _ = make_prefix(tmp_path)
    alternate = prefix / "LIB" / "python3.14" / "site-packages"
    try:
        alternate.mkdir(parents=True)
    except FileExistsError:
        pytest.skip()
    with pytest.raises(ExistingPrefixDiscoveryError) as error:
        discover(
            prefix,
            ("lib/python3.14/site-packages", "LIB/python3.14/site-packages"),
            case_rule=CaseRule.INSENSITIVE,
        )
    assert_discovery_error(
        error, ExistingPrefixDiscoveryErrorCode.DUPLICATE_SITE_PACKAGES
    )


def test_discovery_does_not_write_or_invoke_a_subprocess(tmp_path, monkeypatch):
    prefix, _, _ = make_prefix(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    def fail(*args, **kwargs):
        raise AssertionError("discovery must not write or execute")

    monkeypatch.setattr(Path, "mkdir", fail)
    monkeypatch.setattr(Path, "write_text", fail)
    monkeypatch.setattr(Path, "write_bytes", fail)
    environment = discover(prefix, ("lib/python3.14/site-packages",))

    assert len(environment.layouts) == 1
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_existing_environment_checks_layout_semantics(tmp_path):
    prefix, site, _ = make_prefix(tmp_path)
    layout = InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=site,
        logical_prefix=str(prefix),
        logical_site_packages=str(site),
        path_flavor=host_flavor(),
        case_rule=CaseRule.SENSITIVE,
    )
    with pytest.raises(ValueError, match="layouts must match"):
        ExistingPrefixEnvironment(
            context=ExistingPrefixContext(
                path_flavor=host_flavor(), case_rule=CaseRule.INSENSITIVE
            ),
            layouts=(layout,),
        )


def test_discovered_layout_connects_to_inventory_analysis(tmp_path):
    prefix, site, _ = make_prefix(tmp_path)
    dist_info = site / "example-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: example\nVersion: 1.0\n"
    )
    (site / "example.py").write_bytes(b"example")
    with (dist_info / "RECORD").open("w", newline="") as record:
        csv.writer(record).writerows(
            (("example.py", "", ""), ("example-1.0.dist-info/RECORD", "", ""))
        )

    environment = discover(prefix, ("lib/python3.14/site-packages",))
    result = analyze_installed_environment(
        context=environment.context, layouts=environment.layouts
    )
    assert [(item.name, item.version) for item in result.distributions] == [
        ("example", "1.0")
    ]
