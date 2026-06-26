<#
.SYNOPSIS
    Publish the already-built distribution in ./dist to PyPI or TestPyPI.

.DESCRIPTION
    Token-based auth is read from the environment:
        $env:TWINE_USERNAME  (defaults to "__token__")
        $env:TWINE_PASSWORD  the API token, e.g. "pypi-AgEI..." (REQUIRED)

    Run ci-cd/build.ps1 first so ./dist contains the artifacts.
    --skip-existing makes re-running with an already-published version a no-op.

.PARAMETER Repository
    Target index: 'pypi' (default) or 'testpypi'.

.EXAMPLE
    $env:TWINE_PASSWORD = '<paste token in terminal>'
    pwsh ci-cd/publish.ps1 testpypi
#>
[CmdletBinding()]
param(
    [ValidateSet('pypi', 'testpypi')]
    [string]$Repository = 'pypi'
)

$ErrorActionPreference = 'Stop'

$pkgDir = Split-Path -Parent $PSScriptRoot
Set-Location $pkgDir

if ($env:PYTHON) {
    $python = $env:PYTHON
} elseif (Test-Path "$pkgDir/venv/Scripts/python.exe") {
    $python = "$pkgDir/venv/Scripts/python.exe"
} else {
    $python = 'python'
}

if (-not $env:TWINE_PASSWORD) {
    throw 'TWINE_PASSWORD is not set (provide a PyPI API token).'
}
if (-not $env:TWINE_USERNAME) {
    $env:TWINE_USERNAME = '__token__'
}

if (-not (Test-Path 'dist') -or -not (Get-ChildItem 'dist' -ErrorAction SilentlyContinue)) {
    throw './dist is empty - run ci-cd/build.ps1 first.'
}

Write-Host '==> Validating distribution metadata'
& $python -m twine check (Join-Path 'dist' '*')

Write-Host "==> Uploading to '$Repository'"
& $python -m twine upload --non-interactive --skip-existing `
    --repository $Repository (Join-Path 'dist' '*')

Write-Host "==> Publish to '$Repository' complete"
