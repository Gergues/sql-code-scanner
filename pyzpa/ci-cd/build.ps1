<#
.SYNOPSIS
    Build a clean sdist + wheel for the pyzpa package and validate metadata.

.DESCRIPTION
    Local convenience wrapper around `python -m build` and `twine check`.
    Set $env:PYTHON to use a specific interpreter (defaults to the venv python
    next to this repo if present, otherwise `python`).

.EXAMPLE
    pwsh ci-cd/build.ps1
#>
[CmdletBinding()]
param()

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

Write-Host '==> Cleaning previous build artifacts'
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build
Get-ChildItem -Directory -Filter '*.egg-info' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host '==> Ensuring build tooling is present'
& $python -m pip install --quiet --upgrade build twine

Write-Host '==> Building sdist and wheel'
& $python -m build

Write-Host '==> Validating distribution metadata'
& $python -m twine check (Join-Path 'dist' '*')

Write-Host '==> Build complete:'
Get-ChildItem dist | Select-Object Name, Length
