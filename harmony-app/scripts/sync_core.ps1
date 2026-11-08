# Copy core/*.ts into the HarmonyOS project (core/ is the single source of truth).
# KEEP THIS FILE PURE ASCII: PS 5.1 reads BOM-less UTF-8 as ANSI on non-936 code pages.
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)
$src = Join-Path $Root 'core'
$dst = Join-Path $Root 'harmony\entry\src\main\ets\core'
if (-not (Test-Path $src)) { Write-Error "core/ not found: $src"; exit 1 }
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item (Join-Path $src '*.ts') $dst -Force
$names = (Get-ChildItem $dst -Filter *.ts | Select-Object -ExpandProperty Name) -join ', '
Write-Host "synced -> $dst ($names)"
