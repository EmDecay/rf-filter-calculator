"""Distribution metadata and archive-content regression tests."""

from __future__ import annotations

import os
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

from filter_lib import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "2.1.0"
RUNTIME_RESOURCES = (
    "filter_lib/shared/toroid_core_data.json",
    "filter_lib/wizard/styles.tcss",
)


@pytest.fixture(scope="module")
def project_config() -> dict:
    """Return the committed project metadata."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as config_file:
        return tomllib.load(config_file)


def test_version_has_one_authoritative_source(project_config: dict) -> None:
    """Setuptools must derive package metadata from the library version literal."""
    project = project_config["project"]

    assert "version" not in project
    assert project["dynamic"] == ["version"]
    assert project_config["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "filter_lib.__version__"
    }
    assert __version__ == EXPECTED_VERSION


def test_runtime_resources_are_explicit_package_data(project_config: dict) -> None:
    """Runtime-loaded JSON and Textual CSS must not depend on VCS discovery."""
    package_data = project_config["tool"]["setuptools"]["package-data"]

    assert package_data["filter_lib.shared"] == ["toroid_core_data.json"]
    assert package_data["filter_lib.wizard"] == ["styles.tcss"]


def test_license_uses_pep639_metadata(project_config: dict) -> None:
    """License metadata must use an SPDX expression without legacy classifiers."""
    project = project_config["project"]

    assert project["license"] == "GPL-3.0-only"
    assert project["license-files"] == ["LICENSE"]
    assert not any(value.startswith("License ::") for value in project["classifiers"])
    assert "setuptools>=77.0.3" in project_config["build-system"]["requires"]


def test_python_310_has_an_explicit_toml_reader(project_config: dict) -> None:
    """The oldest CI target must not rely on a transitive tomli dependency."""
    assert "tomli>=2.0; python_version < '3.11'" in project_config["dependency-groups"]["dev"]


def _distribution_directory() -> Path:
    """Resolve the explicit archive directory used by the artifact test job."""
    configured = os.environ.get("RF_FILTER_DIST_DIR")
    if configured is None:
        pytest.skip("set RF_FILTER_DIST_DIR to test built wheel and sdist archives")

    dist_dir = Path(configured).resolve()
    assert dist_dir.is_dir(), f"distribution directory does not exist: {dist_dir}"
    return dist_dir


def _single_artifact(dist_dir: Path, pattern: str) -> Path:
    matches = sorted(dist_dir.glob(pattern))
    assert len(matches) == 1, f"expected one {pattern} artifact, found: {matches}"
    return matches[0]


def _assert_core_metadata(metadata_text: str) -> None:
    metadata = Parser().parsestr(metadata_text)

    assert metadata["Version"] == EXPECTED_VERSION == __version__
    assert metadata["License-Expression"] == "GPL-3.0-only"
    assert "LICENSE" in metadata.get_all("License-File", [])
    assert not any(value.startswith("License ::") for value in metadata.get_all("Classifier", []))


def test_built_archives_contain_metadata_license_and_runtime_resources() -> None:
    """The wheel and sdist must each be self-contained runtime artifacts."""
    dist_dir = _distribution_directory()
    wheel = _single_artifact(dist_dir, "*.whl")
    sdist = _single_artifact(dist_dir, "*.tar.gz")

    with zipfile.ZipFile(wheel) as wheel_archive:
        wheel_names = set(wheel_archive.namelist())
        for resource in RUNTIME_RESOURCES:
            assert resource in wheel_names

        metadata_names = [name for name in wheel_names if name.endswith(".dist-info/METADATA")]
        assert len(metadata_names) == 1
        _assert_core_metadata(wheel_archive.read(metadata_names[0]).decode("utf-8"))
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in wheel_names)

    with tarfile.open(sdist, mode="r:gz") as sdist_archive:
        sdist_names = set(sdist_archive.getnames())
        for resource in RUNTIME_RESOURCES:
            assert any(name.endswith(f"/{resource}") for name in sdist_names)

        metadata_names = [
            name for name in sdist_names if name.count("/") == 1 and name.endswith("/PKG-INFO")
        ]
        assert len(metadata_names) == 1
        metadata_file = sdist_archive.extractfile(metadata_names[0])
        assert metadata_file is not None
        _assert_core_metadata(metadata_file.read().decode("utf-8"))
        assert any(name.endswith("/LICENSE") for name in sdist_names)
