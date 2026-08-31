from __future__ import annotations

import importlib.util
import json
import sys
from email.message import Message
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "release_checks.py"
SPEC = importlib.util.spec_from_file_location("mattergraph_release_checks", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release_checks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_checks
SPEC.loader.exec_module(release_checks)

EXPECTED_PACKAGES = release_checks.EXPECTED_PACKAGES
ReleaseCheckError = release_checks.ReleaseCheckError
_validate_requirement = release_checks._validate_requirement
check_install_report = release_checks.check_install_report
normalize_name = release_checks.normalize_name
select_artifacts = release_checks.select_artifacts


def _write_report(path: Path, host: str) -> None:
  payload = {
    "install": [
      {
        "metadata": {"name": name, "version": "0.1.1"},
        "download_info": {"url": f"https://{host}/packages/{name}-0.1.1.whl"},
      }
      for name in sorted(EXPECTED_PACKAGES)
    ]
  }
  path.write_text(json.dumps(payload))


def test_install_report_requires_all_packages_from_target_index(tmp_path: Path) -> None:
  report = tmp_path / "install-report.json"
  _write_report(report, "test-files.pythonhosted.org")

  check_install_report(report, "testpypi", "0.1.1")


def test_install_report_rejects_wrong_package_origin(tmp_path: Path) -> None:
  report = tmp_path / "install-report.json"
  _write_report(report, "files.pythonhosted.org")

  with pytest.raises(ReleaseCheckError, match="test-files.pythonhosted.org"):
    check_install_report(report, "testpypi", "0.1.1")


@pytest.mark.parametrize(
  "requirement",
  [
    "mattergraph-core",
    "mattergraph-core>=0.1.1",
    "mattergraph-core @ file:///tmp/mattergraph-core",
  ],
)
def test_internal_requirements_must_use_compatible_registry_versions(requirement: str) -> None:
  with pytest.raises(ReleaseCheckError):
    _validate_requirement(requirement, "0.1.1", Path("artifact.whl"))


def test_distribution_names_use_pep_503_normalization() -> None:
  assert normalize_name("MatterGraph_API") == "mattergraph-api"


def test_select_artifacts_isolates_one_wheel_and_sdist(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  dist = tmp_path / "dist"
  dist.mkdir()
  artifacts = []
  for package in sorted(EXPECTED_PACKAGES):
    for kind, suffix in (("wheel", ".whl"), ("sdist", ".tar.gz")):
      path = dist / f"{package}-0.1.1{suffix}"
      path.write_text(f"{package}-{kind}")
      message = Message()
      message["Name"] = package
      artifacts.append(
        release_checks.ArtifactMetadata(path=path, kind=kind, message=message, raw="")
      )
  monkeypatch.setattr(release_checks, "load_artifacts", lambda _: artifacts)

  output = tmp_path / "publish-dist"
  select_artifacts(dist, "MatterGraph_API", output)

  assert sorted(path.name for path in output.iterdir()) == [
    "mattergraph-api-0.1.1.tar.gz",
    "mattergraph-api-0.1.1.whl",
  ]


def test_select_artifacts_rejects_unknown_package(tmp_path: Path) -> None:
  with pytest.raises(ReleaseCheckError, match="Unknown MatterGraph package"):
    select_artifacts(tmp_path / "dist", "not-mattergraph", tmp_path / "publish-dist")


def test_testpypi_install_does_not_mix_dependency_indexes() -> None:
  workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "release.yml").read_text()

  assert "--extra-index-url" not in workflow
  assert "--index-url https://pypi.org/simple/" in workflow
  assert "--index-url https://test.pypi.org/simple/" in workflow
  assert "--no-deps" in workflow
  assert "verify_existing" in workflow
  for package in EXPECTED_PACKAGES:
    assert f'"{package}==0.1.1"' in workflow
