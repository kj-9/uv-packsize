import ast
import json
import os
import subprocess
import venv
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

import uv_packsize.environment as environment_module
from uv_packsize.environment import (
    EnvironmentDiscoveryError,
    EnvironmentDiscoveryErrorCode,
    VenvProbe,
    build_installed_environment,
    detect_case_rule,
    discover_installed_environment,
)
from uv_packsize.models import BuildPolicy, CaseRule, PathFlavor

_MARKER_FIELDS = (
    "implementation_name",
    "implementation_version",
    "os_name",
    "platform_machine",
    "platform_python_implementation",
    "platform_release",
    "platform_system",
    "platform_version",
    "python_full_version",
    "python_version",
    "sys_platform",
)


def probe_for(
    prefix: Path,
    *,
    purelib: Path | None = None,
    platlib: Path | None = None,
    os_name: str = "posix",
) -> VenvProbe:
    purelib = purelib or prefix / "lib" / "python3.14" / "site-packages"
    platlib = platlib or purelib
    return VenvProbe(
        prefix=str(prefix),
        base_prefix=str(prefix.parent / "base-python"),
        executable=str(prefix / "bin" / "python"),
        implementation_name="cpython",
        implementation_version="3.14.0",
        os_name=os_name,
        platform_machine="test-machine",
        platform_python_implementation="CPython",
        platform_release="test-release",
        platform_system="TestOS",
        platform_version="test-version",
        python_full_version="3.14.0",
        python_version="3.14",
        sys_platform="test-platform",
        sysconfig_platform="test-platform",
        purelib=str(purelib),
        platlib=str(platlib),
    )


def test_build_environment_preserves_caller_context_and_deduplicates_layout(tmp_path):
    prefix = tmp_path / "venv"
    purelib = prefix / "lib" / "python3.14" / "site-packages"
    purelib.mkdir(parents=True)
    probe = probe_for(prefix, purelib=purelib)
    requirements = ("example[speed]>=1", "private-package @ https://token@example")

    environment = build_installed_environment(
        probe=probe,
        physical_prefix=prefix,
        physical_purelib=purelib,
        physical_platlib=purelib,
        purelib_case_rule=CaseRule.SENSITIVE,
        platlib_case_rule=CaseRule.SENSITIVE,
        requirements=requirements,
        uv_version="0.11.3",
        build_policy=BuildPolicy.ALLOW_BUILD,
        compile_bytecode=False,
        extras=("Speedups",),
        index_identifiers=("private-index",),
        resolution_strategy="lowest-direct",
    )

    assert environment.context.requirements == requirements
    assert environment.context.python_version == "3.14.0"
    assert environment.context.platform == "test-platform"
    assert environment.context.architecture == "test-machine"
    assert environment.context.uv_version == "0.11.3"
    assert environment.context.build_policy is BuildPolicy.ALLOW_BUILD
    assert environment.context.compile_bytecode is False
    assert environment.context.extras == ("speedups",)
    assert environment.context.index_identifiers == ("private-index",)
    assert environment.context.resolution_strategy == "lowest-direct"
    assert environment.marker_environment.as_mapping(extra="") == {
        "implementation_name": "cpython",
        "implementation_version": "3.14.0",
        "os_name": "posix",
        "platform_machine": "test-machine",
        "platform_python_implementation": "CPython",
        "platform_release": "test-release",
        "platform_system": "TestOS",
        "platform_version": "test-version",
        "python_full_version": "3.14.0",
        "python_version": "3.14",
        "sys_platform": "test-platform",
        "extra": "",
    }
    assert len(environment.layouts) == 1
    assert environment.layouts[0].physical_site_packages == purelib
    assert environment.layouts[0].path_flavor is PathFlavor.POSIX
    assert environment.layouts[0].case_rule is CaseRule.SENSITIVE


def test_build_environment_supports_windows_logical_layout_on_posix(tmp_path):
    prefix = tmp_path / "venv"
    purelib = prefix / "Lib" / "site-packages"
    platlib = prefix / "Lib" / "site-packages-native"
    purelib.mkdir(parents=True)
    platlib.mkdir()
    probe = probe_for(
        prefix,
        purelib=Path(r"C:\work\venv\Lib\site-packages"),
        platlib=Path(r"C:\work\venv\Lib\site-packages-native"),
        os_name="nt",
    )
    probe = VenvProbe(
        prefix=r"C:\work\venv",
        base_prefix=r"C:\Python314",
        executable=r"C:\work\venv\Scripts\python.exe",
        implementation_name=probe.implementation_name,
        implementation_version=probe.implementation_version,
        os_name="nt",
        platform_machine="AMD64",
        platform_python_implementation=probe.platform_python_implementation,
        platform_release=probe.platform_release,
        platform_system="Windows",
        platform_version=probe.platform_version,
        python_full_version=probe.python_full_version,
        python_version=probe.python_version,
        sys_platform="win32",
        sysconfig_platform="win-amd64",
        purelib=probe.purelib,
        platlib=probe.platlib,
    )

    environment = build_installed_environment(
        probe=probe,
        physical_prefix=prefix,
        physical_purelib=purelib,
        physical_platlib=platlib,
        purelib_case_rule=CaseRule.INSENSITIVE,
        platlib_case_rule=CaseRule.INSENSITIVE,
        requirements=("example",),
        uv_version="0.11.3",
        build_policy=BuildPolicy.WHEEL_ONLY,
        compile_bytecode=True,
    )

    assert environment.context.path_flavor is PathFlavor.WINDOWS
    assert environment.context.case_rule is CaseRule.INSENSITIVE
    assert environment.marker_environment.os_name == "nt"
    assert environment.marker_environment.platform_machine == "AMD64"
    assert environment.marker_environment.sys_platform == "win32"
    assert [layout.logical_site_packages for layout in environment.layouts] == [
        r"C:\work\venv\Lib\site-packages",
        r"C:\work\venv\Lib\site-packages-native",
    ]


def test_discovery_probes_venv_python_once_and_each_site_directory(tmp_path):
    prefix = tmp_path / "venv"
    python = prefix / "bin" / "python"
    purelib = prefix / "lib" / "python3.14" / "site-packages"
    platlib = prefix / "lib" / "python3.14" / "platlib"
    python.parent.mkdir(parents=True)
    python.touch()
    purelib.mkdir(parents=True)
    platlib.mkdir()
    probe = probe_for(prefix, purelib=purelib, platlib=platlib)
    calls: list[Path] = []
    case_calls: list[Path] = []

    def runner(command: Path, script: str) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        assert "sysconfig.get_path" in script
        return subprocess.CompletedProcess(
            args=[str(command)],
            returncode=0,
            stdout=json.dumps(asdict(probe)).encode(),
            stderr=b"",
        )

    def case_probe(site: Path) -> CaseRule:
        case_calls.append(site)
        return CaseRule.SENSITIVE

    environment = discover_installed_environment(
        venv_path=prefix,
        venv_python=python,
        requirements=("example",),
        uv_version="0.11.3",
        build_policy=BuildPolicy.WHEEL_ONLY,
        compile_bytecode=True,
        probe_runner=runner,
        case_rule_probe=case_probe,
    )

    assert calls == [python]
    assert case_calls == [purelib, platlib]
    assert len(environment.layouts) == 2


@pytest.mark.parametrize("missing_field", _MARKER_FIELDS)
def test_probe_mapping_requires_each_explicit_marker_field(missing_field):
    values = asdict(probe_for(Path("/logical/venv")))
    del values[missing_field]

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        VenvProbe.from_mapping(values)

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_PROBE


@pytest.mark.parametrize(
    ("field", "value"),
    (("platform_release", ""), ("sys_platform", "\0")),
)
def test_probe_mapping_rejects_malformed_marker_fields(field, value):
    values = asdict(probe_for(Path("/logical/venv")))
    values[field] = value

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        VenvProbe.from_mapping(values)

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_PROBE


def test_probe_mapping_accepts_pep440_prerelease_python_full_version():
    values = asdict(probe_for(Path("/logical/venv")))
    values["python_full_version"] = "3.14.0rc1"

    probe = VenvProbe.from_mapping(values)

    assert probe.python_full_version == "3.14.0rc1"
    assert probe.python_version == "3.14"


def test_probe_mapping_rejects_python_version_that_differs_from_full_release():
    values = asdict(probe_for(Path("/logical/venv")))
    values["python_full_version"] = "3.14.0rc1"
    values["python_version"] = "3.13"

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        VenvProbe.from_mapping(values)

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_PROBE


@pytest.mark.parametrize(
    ("releaselevel", "serial", "expected"),
    (
        ("alpha", 2, "3.14.0a2"),
        ("beta", 3, "3.14.0b3"),
        ("candidate", 1, "3.14.0c1"),
        ("final", 0, "3.14.0"),
    ),
)
def test_probe_script_formats_implementation_prereleases(
    releaselevel, serial, expected
):
    # Packaging's implementation_version formatter uses releaselevel[0], so
    # a candidate is ``c1`` here while platform.python_version() reports the
    # PEP 440-equivalent ``rc1`` used for python_full_version.
    parsed_script = ast.parse(environment_module._PROBE_SCRIPT)
    formatter_definition = next(
        node
        for node in parsed_script.body
        if isinstance(node, ast.FunctionDef) and node.name == "format_full_version"
    )
    formatter_module = ast.Module(body=[formatter_definition], type_ignores=[])
    namespace = {}
    exec(compile(formatter_module, "<probe-script>", "exec"), namespace)

    actual = namespace["format_full_version"](
        SimpleNamespace(
            major=3,
            minor=14,
            micro=0,
            releaselevel=releaselevel,
            serial=serial,
        )
    )

    assert actual == expected


def test_probe_invokes_the_venv_python_in_isolated_mode(monkeypatch):
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout=b"", stderr=b""
        )

    monkeypatch.setattr(environment_module.subprocess, "run", run)

    environment_module._run_probe(Path("venv-python"), "pass")

    assert calls == [["venv-python", "-I", "-c", "pass"]]


def test_venv_identity_accepts_an_in_venv_hardlink_alias(tmp_path):
    prefix = tmp_path / "venv"
    python = prefix / "bin" / "python"
    alias = prefix / "bin" / "python-alias"
    python.parent.mkdir(parents=True)
    python.touch()
    os.link(python, alias)

    environment_module._validate_venv_identity(
        expected_prefix=prefix,
        invoked_python=alias,
        probe=probe_for(prefix),
    )


def test_venv_identity_rejects_an_outside_hardlink_alias(tmp_path):
    prefix = tmp_path / "venv"
    python = prefix / "bin" / "python"
    alias = tmp_path / "outside-python"
    python.parent.mkdir(parents=True)
    python.touch()
    os.link(python, alias)

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        environment_module._validate_venv_identity(
            expected_prefix=prefix,
            invoked_python=alias,
            probe=probe_for(prefix),
        )

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_VENV


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics only")
def test_venv_identity_accepts_windows_case_variants(tmp_path):
    prefix = tmp_path / "venv"
    python = prefix / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    probe = VenvProbe(
        prefix=str(prefix).upper(),
        base_prefix=str(tmp_path / "base-python"),
        executable=str(python).upper(),
        implementation_name="cpython",
        implementation_version="3.14.0",
        os_name="nt",
        platform_machine="AMD64",
        platform_python_implementation="CPython",
        platform_release="test-release",
        platform_system="Windows",
        platform_version="test-version",
        python_full_version="3.14.0",
        python_version="3.14",
        sys_platform="win32",
        sysconfig_platform="win-amd64",
        purelib=str(prefix / "Lib" / "site-packages"),
        platlib=str(prefix / "Lib" / "site-packages"),
    )

    environment_module._validate_venv_identity(
        expected_prefix=prefix,
        invoked_python=python,
        probe=probe,
    )


def test_discovery_reads_an_actual_temporary_venv(tmp_path):
    prefix = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(prefix)

    environment = discover_installed_environment(
        venv_path=prefix,
        requirements=("example",),
        uv_version="0.11.3",
        build_policy=BuildPolicy.WHEEL_ONLY,
        compile_bytecode=True,
    )

    assert environment.context.python_version
    assert environment.context.platform
    assert environment.context.architecture
    assert environment.layouts
    assert environment.marker_environment.python_full_version == (
        environment.context.python_version
    )
    assert environment.marker_environment.python_version == ".".join(
        environment.context.python_version.split(".")[:2]
    )
    assert set(environment.marker_environment.as_mapping(extra="")) == {
        *_MARKER_FIELDS,
        "extra",
    }
    assert all(layout.physical_prefix == prefix for layout in environment.layouts)


def test_discovery_rejects_non_venv_probe_without_leaking_paths_or_requirements(
    tmp_path,
):
    prefix = tmp_path / "venv"
    python = prefix / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    probe = probe_for(prefix)
    probe = VenvProbe(
        prefix=str(tmp_path / "outside"),
        base_prefix=probe.base_prefix,
        executable=probe.executable,
        implementation_name=probe.implementation_name,
        implementation_version=probe.implementation_version,
        os_name=probe.os_name,
        platform_machine=probe.platform_machine,
        platform_python_implementation=probe.platform_python_implementation,
        platform_release=probe.platform_release,
        platform_system=probe.platform_system,
        platform_version=probe.platform_version,
        python_full_version=probe.python_full_version,
        python_version=probe.python_version,
        sys_platform=probe.sys_platform,
        sysconfig_platform=probe.sysconfig_platform,
        purelib=probe.purelib,
        platlib=probe.platlib,
    )

    def runner(_: Path, __: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(asdict(probe)).encode(),
            stderr=b"",
        )

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        discover_installed_environment(
            venv_path=prefix,
            venv_python=python,
            requirements=("private @ https://token@example",),
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
            probe_runner=runner,
        )

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_VENV
    assert str(prefix) not in str(raised.value)
    assert "token" not in str(raised.value)


def test_discovery_rejects_valid_json_with_non_numeric_python_version(tmp_path):
    prefix = tmp_path / "venv"
    python = prefix / "bin" / "python"
    probe = probe_for(prefix)

    def runner(_: Path, __: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "prefix": probe.prefix,
                    "base_prefix": probe.base_prefix,
                    "executable": probe.executable,
                    "implementation_name": probe.implementation_name,
                    "implementation_version": probe.implementation_version,
                    "os_name": probe.os_name,
                    "platform_machine": probe.platform_machine,
                    "platform_python_implementation": probe.platform_python_implementation,
                    "platform_release": probe.platform_release,
                    "platform_system": probe.platform_system,
                    "platform_version": probe.platform_version,
                    "python_full_version": "version-token",
                    "python_version": probe.python_version,
                    "sys_platform": probe.sys_platform,
                    "sysconfig_platform": probe.sysconfig_platform,
                    "purelib": probe.purelib,
                    "platlib": probe.platlib,
                }
            ).encode(),
            stderr=b"",
        )

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        discover_installed_environment(
            venv_path=prefix,
            venv_python=python,
            requirements=("private @ https://token@example",),
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
            probe_runner=runner,
        )

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_PROBE
    assert "version-token" not in str(raised.value)
    assert "token" not in str(raised.value)


def test_build_rejects_different_site_case_rules(tmp_path):
    prefix = tmp_path / "venv"
    purelib = prefix / "lib" / "python3.14" / "site-packages"
    purelib.mkdir(parents=True)

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        build_installed_environment(
            probe=probe_for(prefix, purelib=purelib),
            physical_prefix=prefix,
            physical_purelib=purelib,
            physical_platlib=purelib,
            purelib_case_rule=CaseRule.SENSITIVE,
            platlib_case_rule=CaseRule.INSENSITIVE,
            requirements=("example",),
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
        )

    assert raised.value.code is EnvironmentDiscoveryErrorCode.CASE_RULE_MISMATCH


def test_case_rule_probe_removes_its_directory(tmp_path):
    assert detect_case_rule(tmp_path) in {CaseRule.SENSITIVE, CaseRule.INSENSITIVE}
    assert list(tmp_path.iterdir()) == []


def test_invalid_probe_error_is_sanitized(tmp_path):
    prefix = tmp_path / "venv"
    python = prefix / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    def runner(_: Path, __: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"{invalid-private-token", stderr=b""
        )

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        discover_installed_environment(
            venv_path=prefix,
            venv_python=python,
            requirements=("private @ https://token@example",),
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
            probe_runner=runner,
        )

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_PROBE
    assert "token" not in str(raised.value)
    assert str(prefix) not in str(raised.value)


def test_discovery_rejects_malformed_utf8_probe_output(tmp_path):
    def runner(_: Path, __: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"\xff", stderr=b""
        )

    with pytest.raises(EnvironmentDiscoveryError) as raised:
        discover_installed_environment(
            venv_path=tmp_path / "venv",
            venv_python=tmp_path / "venv" / "bin" / "python",
            requirements=("private @ https://token@example",),
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
            probe_runner=runner,
        )

    assert raised.value.code is EnvironmentDiscoveryErrorCode.INVALID_PROBE
    assert "token" not in str(raised.value)
