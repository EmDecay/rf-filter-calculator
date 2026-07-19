"""Smoke-test an installed wheel from outside the source checkout.

This file intentionally uses only the standard library. It creates a fresh
virtual environment, installs the supplied wheel with its dependencies, and
runs every product probe from an unrelated temporary working directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import venv
from pathlib import Path

EXPECTED_VERSION = "2.1.0"


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run a smoke command and include captured output in any failure."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        rendered = " ".join(command)
        raise RuntimeError(
            f"command failed ({result.returncode}): {rendered}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _reject_json_constant(value: str) -> None:
    """Reject non-standard NaN and Infinity tokens in CLI JSON."""
    raise ValueError(f"non-standard JSON constant: {value}")


def _venv_executable(environment: Path, name: str) -> Path:
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    return scripts / f"{name}{suffix}"


def _probe_installed_package(python: Path, *, cwd: Path, env: dict[str, str]) -> dict:
    probe = textwrap.dedent(
        f"""
        import json
        import sys
        from importlib import import_module
        from importlib.metadata import distribution, version
        from importlib.resources import files
        from importlib.util import find_spec
        from pathlib import Path

        import filter_lib
        from filter_lib.shared.toroid_core_data import list_cores

        expected_version = {EXPECTED_VERSION!r}
        package_path = Path(filter_lib.__file__).resolve()
        environment_path = Path(sys.prefix).resolve()
        assert package_path.is_relative_to(environment_path), (package_path, environment_path)
        assert filter_lib.__version__ == expected_version
        assert version("rf-filter-calculator") == expected_version

        metadata = distribution("rf-filter-calculator").metadata
        assert metadata["License-Expression"] == "GPL-3.0-only"
        assert "LICENSE" in (metadata.get_all("License-File") or [])
        assert not any(
            classifier.startswith("License ::")
            for classifier in (metadata.get_all("Classifier") or [])
        )

        core_resource = files("filter_lib.shared").joinpath("toroid_core_data.json")
        core_manifest = json.loads(core_resource.read_text(encoding="utf-8"))
        assert core_manifest
        loaded_cores = list_cores()
        loaded_names = [core.name for core in loaded_cores]
        assert loaded_cores
        assert len(loaded_names) == len(set(loaded_names))

        css_resource = files("filter_lib.wizard").joinpath("styles.tcss")
        assert css_resource.read_text(encoding="utf-8").strip()

        spice_module_available = find_spec("filter_lib.shared.spice_export") is not None
        if spice_module_available:
            import_module("filter_lib.shared.spice_export")

        print(json.dumps({{
            "version": filter_lib.__version__,
            "loaded_core_count": len(loaded_cores),
            "package_path": str(package_path),
            "spice_module": spice_module_available,
        }}))
        """
    )
    result = _run([str(python), "-c", probe], cwd=cwd, env=env)
    return json.loads(result.stdout)


def _probe_cli(filter_calc: Path, *, cwd: Path, env: dict[str, str]) -> bool:
    version_result = _run([str(filter_calc), "--version"], cwd=cwd, env=env)
    assert version_result.stdout.strip().endswith(EXPECTED_VERSION)

    command = [
        str(filter_calc),
        "lowpass",
        "butterworth",
        "pi",
        "10MHz",
        "--components",
        "3",
        "--no-match",
        "--no-toroids",
        "--format",
        "json",
    ]
    calculation = _run(command, cwd=cwd, env=env)
    payload = json.loads(calculation.stdout, parse_constant=_reject_json_constant)
    assert isinstance(payload, dict) and payload

    help_result = _run([str(filter_calc), "lowpass", "--help"], cwd=cwd, env=env)
    spice_available = bool(re.search(r"--format[^\n]*\bspice\b", help_result.stdout))
    if spice_available:
        spice_command = [
            str(filter_calc),
            "lowpass",
            "butterworth",
            "pi",
            "10MHz",
            "--components",
            "3",
            "--format",
            "spice",
        ]
        spice_result = _run(spice_command, cwd=cwd, env=env)
        spice_deck = spice_result.stdout
        assert re.search(r"(?im)^\.ac\s", spice_deck)
        assert re.search(r"(?im)^\.end\s*$", spice_deck)
        assert not re.search(r"(?i)(?<![a-z])(?:nan|[+-]?inf(?:inity)?)(?![a-z])", spice_deck)

    return spice_available


def _probe_wizard(python: Path, *, cwd: Path, env: dict[str, str]) -> None:
    probe = textwrap.dedent(
        """
        import asyncio

        from filter_lib.wizard.app import FilterWizardApp

        async def main():
            app = FilterWizardApp()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                assert any(
                    type(screen).__name__ == "WelcomeScreen"
                    for screen in app.screen_stack
                )

        asyncio.run(main())
        """
    )
    _run([str(python), "-c", probe], cwd=cwd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, help="Path to the wheel artifact to install")
    args = parser.parse_args()

    wheel = args.wheel.resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        parser.error(f"wheel does not exist or is not a .whl file: {wheel}")

    with tempfile.TemporaryDirectory(prefix="rf-filter-wheel-smoke-") as temporary:
        smoke_root = Path(temporary)
        environment = smoke_root / "environment"
        work_dir = smoke_root / "work"
        work_dir.mkdir()
        venv.EnvBuilder(
            with_pip=False,
            clear=True,
            symlinks=os.name != "nt",
        ).create(environment)

        python = _venv_executable(environment, "python")
        filter_calc = _venv_executable(environment, "filter-calc")
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONHOME", None)
        clean_env.pop("PYTHONPATH", None)
        clean_env["PYTHONNOUSERSITE"] = "1"
        clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        clean_env["PIP_NO_CACHE_DIR"] = "1"

        uv_executable = shutil.which("uv", path=clean_env.get("PATH"))
        if uv_executable is not None:
            install_command = [
                uv_executable,
                "pip",
                "install",
                "--python",
                str(python),
                "--no-cache",
                str(wheel),
            ]
        else:
            _run([str(python), "-m", "ensurepip", "--upgrade"], cwd=work_dir, env=clean_env)
            install_command = [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-input",
                str(wheel),
            ]
        _run(install_command, cwd=work_dir, env=clean_env)
        package_details = _probe_installed_package(python, cwd=work_dir, env=clean_env)
        spice_available = _probe_cli(filter_calc, cwd=work_dir, env=clean_env)
        _probe_wizard(python, cwd=work_dir, env=clean_env)

    print(
        "wheel smoke passed: "
        f"version={package_details['version']}, "
        f"loaded_cores={package_details['loaded_core_count']}, "
        f"spice_module={'imported' if package_details['spice_module'] else 'not exposed'}, "
        f"spice_cli={'tested' if spice_available else 'not exposed'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
