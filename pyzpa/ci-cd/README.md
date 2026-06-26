# pyzpa CI/CD

Scripts and GitHub Actions workflows that build and publish the `pyzpa`
package to PyPI / TestPyPI.

## Contents

| File | Purpose |
|------|---------|
| `build.sh` / `build.ps1` | Clean, build `sdist` + `wheel`, run `twine check`. |
| `publish.sh` / `publish.ps1` | Upload `./dist` to `pypi` or `testpypi` (idempotent via `--skip-existing`). |
| `stamp_dev_version.py` | Rewrites `pyproject.toml` version to `X.Y.Z.dev<UTC-timestamp>` so periodic builds are unique. |
| `pypirc.example` | Template for local `~/.pypirc` (do **not** commit real tokens). |
| `github-workflows/ci.yml` | Lint + test + build on every push/PR. |
| `github-workflows/publish-pypi.yml` | Publish to **PyPI** when a `vX.Y.Z` tag is pushed. |
| `github-workflows/nightly-testpypi.yml` | **Periodic** scheduled build → dev version → **TestPyPI**. |

> The scripts resolve the package root (the parent of `ci-cd/`) automatically,
> so they can be run from anywhere.

## Local usage

```pwsh
# Build and validate
pwsh ci-cd/build.ps1

# Publish to TestPyPI (paste your token directly into the terminal)
$env:TWINE_PASSWORD = '<your-testpypi-token>'
pwsh ci-cd/publish.ps1 testpypi
```

```bash
# Linux/macOS
bash ci-cd/build.sh
export TWINE_PASSWORD='<your-testpypi-token>'
bash ci-cd/publish.sh testpypi
```

Tokens are read from `TWINE_PASSWORD` (username defaults to `__token__`).
**Never paste tokens into chat or commit them** — type them straight into the
terminal or store them as CI secrets.

## Enabling the GitHub Actions workflows

GitHub only runs workflows located at `<repo-root>/.github/workflows/`. Copy the
templates there (paths assume `pyzpa/` sits at the repo root — adjust the
`working-directory` and `paths:` filters if it is nested differently):

```bash
mkdir -p .github/workflows
cp pyzpa/ci-cd/github-workflows/*.yml .github/workflows/
```

Then add the API tokens as repository secrets
(Settings → Secrets and variables → Actions):

| Secret | Used by | Get it from |
|--------|---------|-------------|
| `PYPI_API_TOKEN` | `publish-pypi.yml` | https://pypi.org/manage/account/token/ |
| `TEST_PYPI_API_TOKEN` | `nightly-testpypi.yml` | https://test.pypi.org/manage/account/token/ |

### How "publish periodically" works

`nightly-testpypi.yml` runs on a cron schedule (default `0 3 * * *`, daily at
03:00 UTC). Each run:

1. stamps a unique `X.Y.Z.dev<timestamp>` version,
2. builds + validates the distribution,
3. uploads it to **TestPyPI**.

This is intentionally pointed at **TestPyPI**: the real PyPI rejects duplicate
versions, so recurring publishes there would fail without a manual bump. For an
actual release, push a tag and let `publish-pypi.yml` ship that version to PyPI:

```bash
# keep pyproject.toml `version` in sync with the tag, then:
git tag v0.1.0
git push origin v0.1.0
```

Change the cadence by editing the `cron:` expression, or trigger any workflow
manually via the **Run workflow** button (`workflow_dispatch`).
