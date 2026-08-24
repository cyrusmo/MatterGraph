# Releasing MatterGraph

MatterGraph publishes six synchronized distributions. A release is complete only after a fresh
installation from production PyPI passes; uploading files alone is not sufficient.

## One-time trusted-publisher setup

Confirm that all six names are available before configuring publishers:

```bash
python scripts/release_checks.py registry --index testpypi --version 0.1.0
python scripts/release_checks.py registry --index pypi --version 0.1.0
```

Create the GitHub environments `testpypi` and `pypi`. Protect `pypi` with a required reviewer.
On both PyPI and TestPyPI, register a pending trusted publisher for each distribution:

- PyPI project names: `mattergraph`, `mattergraph-core`, `mattergraph-connectors`,
  `mattergraph-benchmarks`, `mattergraph-sim`, and `mattergraph-api`
- GitHub owner: `cyrusmo`
- Repository: `MatterGraph`
- Workflow: `release.yml`
- Environment: `testpypi` on TestPyPI and `pypi` on PyPI

Pending publishers create a project during its first upload but do not reserve its name. Do not
leave a long gap between the successful TestPyPI rehearsal and the production release. MatterGraph
does not use long-lived upload tokens.

## Rehearse on TestPyPI

Run the `Release` workflow manually. Manual dispatch always targets TestPyPI. The workflow:

1. Runs tests and builds all packages using `build-constraints.txt`.
2. Requires exactly twelve Core Metadata 2.4 artifacts and runs Twine validation.
3. Installs local artifacts on Python 3.10 and 3.12 with default and `[all]` dependencies.
4. Publishes member packages before the metapackage.
5. Installs from TestPyPI and checks pip's installation report to prove all six MatterGraph
   distributions came from `test-files.pythonhosted.org`.

If any package name is claimed, any `0.1.0` artifact already exists, or any archive emits metadata
2.5 or newer, stop. Do not rename packages or weaken validation inside the release run.

## Publish 0.1.0

After TestPyPI is green, replace `Unreleased` on the `0.1.0` changelog heading with the release
date. Create and push an annotated tag:

```bash
git tag -a v0.1.0 -m "MatterGraph 0.1.0"
git push origin v0.1.0
```

Only a `v*` tag can target production PyPI. The protected `pypi` environment supplies the approval
gate. The workflow creates a GitHub release only after no-cache production installations pass on
Python 3.10 and 3.12, all six downloads resolve from `files.pythonhosted.org`, and the default
metapackage remains free of `mp-api` and `jarvis-tools`.
