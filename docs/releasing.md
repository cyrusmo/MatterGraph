# Releasing MatterGraph

MatterGraph publishes six synchronized distributions. A release is complete only after a fresh
installation from production PyPI passes; uploading files alone is not sufficient.

## One-time trusted-publisher setup

Confirm that all six names are available before configuring publishers:

```bash
python scripts/release_checks.py registry --index testpypi --version 0.1.0
python scripts/release_checks.py registry --index pypi --version 0.1.0
```

Create the base GitHub environments `testpypi` and `pypi`, plus one component environment per
registry. Allow `main` on every TestPyPI environment and `v*` tags on every production
environment. Require a reviewer on every production environment. For the first publication only,
also require a reviewer on the five TestPyPI component environments so the initial uploads can be
approved in bounded waves.

| Distribution | TestPyPI environment | PyPI environment |
| --- | --- | --- |
| `mattergraph` | `testpypi` | `pypi` |
| `mattergraph-core` | `testpypi-mattergraph-core` | `pypi-mattergraph-core` |
| `mattergraph-connectors` | `testpypi-mattergraph-connectors` | `pypi-mattergraph-connectors` |
| `mattergraph-benchmarks` | `testpypi-mattergraph-benchmarks` | `pypi-mattergraph-benchmarks` |
| `mattergraph-sim` | `testpypi-mattergraph-sim` | `pypi-mattergraph-sim` |
| `mattergraph-api` | `testpypi-mattergraph-api` | `pypi-mattergraph-api` |

On both PyPI and TestPyPI, register a pending trusted publisher for each distribution:

- PyPI project names: `mattergraph`, `mattergraph-core`, `mattergraph-connectors`,
  `mattergraph-benchmarks`, `mattergraph-sim`, and `mattergraph-api`
- GitHub owner: `cyrusmo`
- Repository: `MatterGraph`
- Workflow: `release.yml`
- Environment: the package-scoped value in the table above

Pending publishers create a project during its first upload but do not reserve its name. Do not
leave a long gap between the successful TestPyPI rehearsal and the production release. MatterGraph
does not use long-lived upload tokens. PyPI permits a publisher to serve multiple existing projects,
but only one unconsumed pending project may use an identical OIDC identity, and one account may
hold only three pending publishers at a time. The package-scoped environments make the
six-project first publication deterministic without temporary credentials or manual bootstrap
uploads.

For the first publication on each registry, stage the pending publishers and environment approvals:

1. Register `mattergraph`, `mattergraph-api`, and `mattergraph-benchmarks`.
2. Start the workflow and approve only the API and benchmarks component environments. Leave the
   other component deployments waiting.
3. After those two projects become active and free their pending slots, register
   `mattergraph-connectors` and `mattergraph-core`, then approve those environments.
4. After those projects become active, register `mattergraph-sim` and approve its environment.
5. The downstream metapackage job consumes the already-registered `mattergraph` publisher after
   every component succeeds.

After the TestPyPI rehearsal creates all six projects, remove the temporary reviewer requirement
from the five TestPyPI component environments. Keep every production approval gate.

## Rehearse on TestPyPI

Run the `Release` workflow manually. Manual dispatch always targets TestPyPI. During the first run,
follow the staged publisher approvals above; no publish job should be allowed to fail merely because
its publisher has not been registered yet. The workflow:

1. Runs tests and builds all packages using `build-constraints.txt`.
2. Requires exactly twelve Core Metadata 2.4 artifacts and runs Twine validation.
3. Installs local artifacts on Python 3.10 and 3.12 with default and `[all]` dependencies.
4. Isolates one wheel and one sdist per OIDC job, then publishes member packages before the
   metapackage.
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

Only a `v*` tag can target production PyPI. The protected `pypi*` environments supply the approval
gates. The workflow creates a GitHub release only after no-cache production installations pass on
Python 3.10 and 3.12, all six downloads resolve from `files.pythonhosted.org`, and the default
metapackage remains free of `mp-api` and `jarvis-tools`.
