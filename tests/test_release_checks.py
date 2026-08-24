from __future__ import annotations

import importlib.util
import json
import sys
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


def _write_report(path: Path, host: str) -> None:
  payload = {
    "install": [
      {
        "metadata": {"name": name, "version": "0.1.0"},
        "download_info": {"url": f"https://{host}/packages/{name}-0.1.0.whl"},
      }
      for name in sorted(EXPECTED_PACKAGES)
    ]
  }
  path.write_text(json.dumps(payload))


def test_install_report_requires_all_packages_from_target_index(tmp_path: Path) -> None:
  report = tmp_path / "install-report.json"
  _write_report(report, "test-files.pythonhosted.org")

  check_install_report(report, "testpypi", "0.1.0")


def test_install_report_rejects_wrong_package_origin(tmp_path: Path) -> None:
  report = tmp_path / "install-report.json"
  _write_report(report, "files.pythonhosted.org")

  with pytest.raises(ReleaseCheckError, match="test-files.pythonhosted.org"):
    check_install_report(report, "testpypi", "0.1.0")


@pytest.mark.parametrize(
  "requirement",
  [
    "mattergraph-core",
    "mattergraph-core>=0.1.0",
    "mattergraph-core @ file:///tmp/mattergraph-core",
  ],
)
def test_internal_requirements_must_use_compatible_registry_versions(requirement: str) -> None:
  with pytest.raises(ReleaseCheckError):
    _validate_requirement(requirement, "0.1.0", Path("artifact.whl"))


def test_distribution_names_use_pep_503_normalization() -> None:
  assert normalize_name("MatterGraph_API") == "mattergraph-api"
