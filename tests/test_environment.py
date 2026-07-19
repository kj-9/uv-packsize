import json
import os
import subprocess
import venv
from pathlib import Path

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
        python_version="3.14.0",
        sysconfig_platform="test-platform",
        machine="test-machine",
        os_name=os_name,
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
        python_version=probe.python_version,
        sysconfig_platform="win-amd64",
        machine="AMD64",
        os_name="nt",
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
            stdout=json.dumps(
                probe.__dict__
                if hasattr(probe, "__dict__")
                else {
                    "prefix": probe.prefix,
                    "base_prefix": probe.base_prefix,
                    "executable": probe.executable,
                    "python_version": probe.python_version,
                    "sysconfig_platform": probe.sysconfig_platform,
                    "machine": probe.machine,
                    "os_name": probe.os_name,
                    "purelib": probe.purelib,
                    "platlib": probe.platlib,
                }
            ).encode(),
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
        python_version="3.14.0",
        sysconfig_platform="win-amd64",
        machine="AMD64",
        os_name="nt",
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
        python_version=probe.python_version,
        sysconfig_platform=probe.sysconfig_platform,
        machine=probe.machine,
        os_name=probe.os_name,
        purelib=probe.purelib,
        platlib=probe.platlib,
    )

    def runner(_: Path, __: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "prefix": probe.prefix,
                    "base_prefix": probe.base_prefix,
                    "executable": probe.executable,
                    "python_version": probe.python_version,
                    "sysconfig_platform": probe.sysconfig_platform,
                    "machine": probe.machine,
                    "os_name": probe.os_name,
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
                    "python_version": "version-token",
                    "sysconfig_platform": probe.sysconfig_platform,
                    "machine": probe.machine,
                    "os_name": probe.os_name,
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
