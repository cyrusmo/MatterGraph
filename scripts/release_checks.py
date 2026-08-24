#!/usr/bin/env python3
"""Deterministic checks used before and after publishing MatterGraph packages."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import re
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from email.message import Message
from email.parser import Parser
from importlib import metadata
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_PACKAGES = {
  "mattergraph",
  "mattergraph-api",
  "mattergraph-benchmarks",
  "mattergraph-connectors",
  "mattergraph-core",
  "mattergraph-sim",
}
REGISTRIES = {
  "pypi": "https://pypi.org",
  "testpypi": "https://test.pypi.org",
}
REPORT_HOSTS = {
  "pypi": "files.pythonhosted.org",
  "testpypi": "test-files.pythonhosted.org",
}
REPOSITORY_URL = "https://github.com/cyrusmo/MatterGraph"


class ReleaseCheckError(RuntimeError):
  """Raised when a release invariant is violated."""


def normalize_name(value: str) -> str:
  return re.sub(r"[-_.]+", "-", value).lower()


@dataclass(frozen=True)
class ArtifactMetadata:
  path: Path
  kind: str
  message: Message
  raw: str


def _read_wheel(path: Path) -> ArtifactMetadata:
  with zipfile.ZipFile(path) as archive:
    names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
    if len(names) != 1:
      raise ReleaseCheckError(f"{path.name}: expected one wheel METADATA, found {len(names)}")
    raw = archive.read(names[0]).decode("utf-8")
  return ArtifactMetadata(path=path, kind="wheel", message=Parser().parsestr(raw), raw=raw)


def _read_sdist(path: Path) -> ArtifactMetadata:
  with tarfile.open(path, mode="r:gz") as archive:
    candidates = [
      member
      for member in archive.getmembers()
      if member.isfile() and member.name.endswith("/PKG-INFO")
    ]
    top_level = [member for member in candidates if member.name.count("/") == 1]
    selected = top_level or candidates
    if len(selected) != 1:
      raise ReleaseCheckError(
        f"{path.name}: expected one top-level PKG-INFO, found {len(selected)}"
      )
    stream = archive.extractfile(selected[0])
    if stream is None:
      raise ReleaseCheckError(f"{path.name}: could not read PKG-INFO")
    raw = stream.read().decode("utf-8")
  return ArtifactMetadata(path=path, kind="sdist", message=Parser().parsestr(raw), raw=raw)


def read_artifact(path: Path) -> ArtifactMetadata:
  if path.suffix == ".whl":
    return _read_wheel(path)
  if path.name.endswith(".tar.gz"):
    return _read_sdist(path)
  raise ReleaseCheckError(f"Unexpected release artifact: {path.name}")


def load_artifacts(dist: Path) -> list[ArtifactMetadata]:
  if not dist.is_dir():
    raise ReleaseCheckError(f"Artifact directory does not exist: {dist}")
  paths = sorted(path for path in dist.iterdir() if path.is_file())
  if len(paths) != 12:
    names = ", ".join(path.name for path in paths) or "<empty>"
    raise ReleaseCheckError(f"Expected exactly 12 artifacts in {dist}, found {len(paths)}: {names}")
  return [read_artifact(path) for path in paths]


def _validate_requirement(requirement: str, version: str, artifact: Path) -> None:
  lowered = requirement.lower()
  if " @ " in lowered or "file:" in lowered or "workspace:" in lowered:
    raise ReleaseCheckError(f"{artifact.name}: non-registry dependency is forbidden: {requirement}")
  match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
  if match is None:
    raise ReleaseCheckError(f"{artifact.name}: malformed Requires-Dist: {requirement}")
  if normalize_name(match.group(1)) in EXPECTED_PACKAGES:
    compatible = re.search(rf"~=\s*{re.escape(version)}(?:\s|;|$)", requirement)
    if compatible is None:
      raise ReleaseCheckError(
        f"{artifact.name}: internal dependency must use ~={version}: {requirement}"
      )


def _validate_metapackage_extras(artifact: ArtifactMetadata) -> None:
  provided = set(artifact.message.get_all("Provides-Extra", []))
  if provided != {"all", "jarvis", "mp"}:
    raise ReleaseCheckError(
      f"{artifact.path.name}: expected extras all/jarvis/mp, found {sorted(provided)}"
    )
  connector_requirements = [
    requirement
    for requirement in artifact.message.get_all("Requires-Dist", [])
    if normalize_name(re.match(r"\s*([A-Za-z0-9_.-]+)", requirement).group(1))
    == "mattergraph-connectors"
  ]
  default_requirements = [
    requirement for requirement in connector_requirements if ";" not in requirement
  ]
  if len(default_requirements) != 1 or "[" in default_requirements[0].split(";", 1)[0]:
    raise ReleaseCheckError(
      f"{artifact.path.name}: default install must require connectors without optional extras"
    )
  for extra in ("all", "jarvis", "mp"):
    matching = [
      requirement
      for requirement in connector_requirements
      if f"[{extra}]" in requirement.lower()
      and re.search(rf"extra\s*==\s*['\"]{extra}['\"]", requirement)
    ]
    if len(matching) != 1:
      raise ReleaseCheckError(
        f"{artifact.path.name}: expected one connector requirement for extra {extra}"
      )


def check_artifacts(dist: Path, version: str) -> None:
  artifacts = load_artifacts(dist)
  observed: dict[tuple[str, str], Path] = {}
  for artifact in artifacts:
    message = artifact.message
    name = normalize_name(message.get("Name", ""))
    if name not in EXPECTED_PACKAGES:
      raise ReleaseCheckError(f"{artifact.path.name}: unexpected distribution name {name!r}")
    key = (name, artifact.kind)
    if key in observed:
      raise ReleaseCheckError(
        f"Duplicate {artifact.kind} for {name}: {observed[key].name}, {artifact.path.name}"
      )
    observed[key] = artifact.path
    expected_fields = {
      "Metadata-Version": "2.4",
      "Version": version,
      "Requires-Python": ">=3.10",
      "License-Expression": "Apache-2.0",
    }
    for field, expected in expected_fields.items():
      actual = message.get(field)
      if actual != expected:
        raise ReleaseCheckError(
          f"{artifact.path.name}: {field} must be {expected!r}, found {actual!r}"
        )
    for requirement in message.get_all("Requires-Dist", []):
      _validate_requirement(requirement, version, artifact.path)
    if name == "mattergraph":
      _validate_metapackage_extras(artifact)

  expected_keys = {
    (name, kind) for name in EXPECTED_PACKAGES for kind in ("wheel", "sdist")
  }
  if set(observed) != expected_keys:
    missing = sorted(expected_keys - set(observed))
    raise ReleaseCheckError(f"Missing expected artifact types: {missing}")
  print(f"Validated 12 MatterGraph {version} artifacts with Core Metadata 2.4.")


def split_artifacts(dist: Path, members: Path, metapackage: Path) -> None:
  artifacts = load_artifacts(dist)
  for destination in (members, metapackage):
    if destination.exists() and any(destination.iterdir()):
      raise ReleaseCheckError(f"Split destination must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
  for artifact in artifacts:
    name = normalize_name(artifact.message.get("Name", ""))
    destination = metapackage if name == "mattergraph" else members
    shutil.copy2(artifact.path, destination / artifact.path.name)
  member_count = len(list(members.iterdir()))
  metapackage_count = len(list(metapackage.iterdir()))
  if (member_count, metapackage_count) != (10, 2):
    raise ReleaseCheckError(
      f"Expected 10 member and 2 metapackage artifacts, found {member_count} and "
      f"{metapackage_count}"
    )
  print("Split 10 member artifacts and 2 metapackage artifacts.")


def check_registry(index: str, version: str) -> None:
  base_url = REGISTRIES[index]
  failures: list[str] = []
  for name in sorted(EXPECTED_PACKAGES):
    url = f"{base_url}/pypi/{name}/json"
    try:
      with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
        payload = json.load(response)
    except urllib.error.HTTPError as error:
      if error.code == 404:
        print(f"{index}: {name} is available for first publication")
        continue
      raise ReleaseCheckError(f"{index}: HTTP {error.code} checking {name}") from error
    except urllib.error.URLError as error:
      raise ReleaseCheckError(f"{index}: could not check {name}: {error.reason}") from error

    info = payload.get("info", {})
    project_urls = list((info.get("project_urls") or {}).values())
    project_urls.extend([info.get("home_page"), info.get("project_url")])
    normalized_urls = {str(value).rstrip("/").lower() for value in project_urls if value}
    if REPOSITORY_URL.lower() not in normalized_urls:
      failures.append(f"{name} exists but does not identify {REPOSITORY_URL}")
      continue
    releases = payload.get("releases", {})
    if version in releases:
      failures.append(f"{name} already contains immutable version {version}")
      continue
    print(f"{index}: {name} is an existing MatterGraph project; {version} is available")
  if failures:
    raise ReleaseCheckError("Registry check failed:\n- " + "\n- ".join(failures))


def check_install_report(report_path: Path, index: str, version: str) -> None:
  payload = json.loads(report_path.read_text())
  found: dict[str, tuple[str, str]] = {}
  for item in payload.get("install", []):
    package_metadata = item.get("metadata", {})
    name = normalize_name(package_metadata.get("name", ""))
    if name not in EXPECTED_PACKAGES:
      continue
    package_version = str(package_metadata.get("version", ""))
    url = str(item.get("download_info", {}).get("url", ""))
    found[name] = (package_version, url)
  missing = EXPECTED_PACKAGES - set(found)
  if missing:
    raise ReleaseCheckError(f"Install report is missing MatterGraph packages: {sorted(missing)}")
  expected_host = REPORT_HOSTS[index]
  for name, (package_version, url) in sorted(found.items()):
    if package_version != version:
      raise ReleaseCheckError(f"{name}: expected version {version}, found {package_version}")
    host = urlparse(url).hostname
    if host != expected_host:
      raise ReleaseCheckError(f"{name}: expected download from {expected_host}, found {url}")
  print(f"Verified all six MatterGraph {version} downloads originated from {expected_host}.")


def smoke_installed(version: str, mode: str) -> None:
  for distribution in sorted(EXPECTED_PACKAGES):
    actual = metadata.version(distribution)
    if actual != version:
      raise ReleaseCheckError(f"{distribution}: expected {version}, found {actual}")

  for module in (
    "mattergraph",
    "mattergraph_api",
    "mattergraph_benchmarks",
    "mattergraph_connectors",
    "mattergraph_sim",
  ):
    importlib.import_module(module)

  import httpx
  from mattergraph import Material
  from mattergraph_api.main import app

  material = Material(material_id="release-smoke", formula="AlN")
  restored = Material.model_validate_json(material.model_dump_json())
  if restored != material:
    raise ReleaseCheckError("Material JSON round-trip changed the record")
  async def request_health() -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mattergraph.test") as client:
      return await client.get("/health")

  response = asyncio.run(request_health())
  if response.status_code != 200 or response.json() != {"status": "ok"}:
    raise ReleaseCheckError(f"API health smoke failed: {response.status_code} {response.text}")

  optional_distributions = ("mp-api", "jarvis-tools")
  installed_optional = {
    package for package in optional_distributions if _distribution_is_installed(package)
  }
  if mode == "default" and installed_optional:
    raise ReleaseCheckError(
      f"Lightweight install unexpectedly contains optional SDKs: {sorted(installed_optional)}"
    )
  if mode == "all":
    missing_optional = set(optional_distributions) - installed_optional
    if missing_optional:
      raise ReleaseCheckError(f"[all] install is missing SDKs: {sorted(missing_optional)}")
    importlib.import_module("mp_api")
    importlib.import_module("jarvis")
  print(f"Installed-package smoke passed for mattergraph {version} ({mode}).")


def _distribution_is_installed(name: str) -> bool:
  try:
    metadata.version(name)
  except metadata.PackageNotFoundError:
    return False
  return True


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description=__doc__)
  subparsers = parser.add_subparsers(dest="command", required=True)

  artifacts = subparsers.add_parser("artifacts", help="validate built wheels and sdists")
  artifacts.add_argument("--dist", type=Path, default=Path("dist"))
  artifacts.add_argument("--version", default="0.1.0")

  split = subparsers.add_parser("split", help="split member and metapackage artifacts")
  split.add_argument("--dist", type=Path, default=Path("dist"))
  split.add_argument("--members", type=Path, default=Path("dist-members"))
  split.add_argument("--metapackage", type=Path, default=Path("dist-meta"))

  registry = subparsers.add_parser("registry", help="check project ownership and version space")
  registry.add_argument("--index", choices=sorted(REGISTRIES), required=True)
  registry.add_argument("--version", default="0.1.0")

  report = subparsers.add_parser("report", help="verify pip download provenance")
  report.add_argument("--report", type=Path, required=True)
  report.add_argument("--index", choices=sorted(REPORT_HOSTS), required=True)
  report.add_argument("--version", default="0.1.0")

  smoke = subparsers.add_parser("smoke", help="exercise installed distributions")
  smoke.add_argument("--version", default="0.1.0")
  smoke.add_argument("--mode", choices=("default", "all"), required=True)
  return parser


def main() -> int:
  args = build_parser().parse_args()
  try:
    if args.command == "artifacts":
      check_artifacts(args.dist, args.version)
    elif args.command == "split":
      split_artifacts(args.dist, args.members, args.metapackage)
    elif args.command == "registry":
      check_registry(args.index, args.version)
    elif args.command == "report":
      check_install_report(args.report, args.index, args.version)
    elif args.command == "smoke":
      smoke_installed(args.version, args.mode)
  except (ReleaseCheckError, json.JSONDecodeError) as error:
    print(f"release check failed: {error}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
