# Build the HarmonyOS project from CLI (no DevEco Studio GUI needed).
# NOTE: keep this file ASCII-only -- Windows PowerShell 5.1 reads UTF-8 without BOM as ANSI,
#       Chinese text here would turn into mojibake and can break string interpolation.
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$BuildMode = 'debug',
    [string]$DevEco = $(if ($env:DEVECO_STUDIO_HOME) { $env:DEVECO_STUDIO_HOME } else { 'D:\DevEco Studio' })
)
$ErrorActionPreference = 'Stop'
$devEco = $DevEco
$node = Join-Path $devEco 'tools\node\node.exe'
$hvigor = Join-Path $devEco 'tools\hvigor\bin\hvigorw.js'
$proj = Join-Path $Root 'harmony'

if (-not (Test-Path $node)) { Write-Error "node not found: $node"; exit 1 }
if (-not (Test-Path $proj)) { Write-Error "project not found: $proj"; exit 1 }

# Always sync core/*.ts -> entry/src/main/ets/core before building.
# core/ is the single source of truth (Node tests run there); the ets copy is only for ArkTS.
$coreSrc = Join-Path $Root 'core'
$coreDst = Join-Path $proj 'entry\src\main\ets\core'
if (Test-Path $coreSrc) {
    if (-not (Test-Path $coreDst)) { New-Item -ItemType Directory -Path $coreDst -Force | Out-Null }
    $srcFiles = Get-ChildItem $coreSrc -Filter *.ts -File
    foreach ($f in $srcFiles) {
        Copy-Item $f.FullName (Join-Path $coreDst $f.Name) -Force
    }
    # Drop stale copies (e.g. a deleted core file would otherwise keep compiling)
    $stale = Get-ChildItem $coreDst -Filter *.ts -File |
        Where-Object { $srcFiles.Name -notcontains $_.Name }
    foreach ($s in $stale) { Remove-Item $s.FullName -Force }
    Write-Host ("core synced: {0} file(s)" -f $srcFiles.Count)
}

$env:DEVECO_SDK_HOME = Join-Path $devEco 'sdk'
Push-Location $proj
$code = 1
try {
    & $node $hvigor --mode module -p product=default -p "buildMode=$BuildMode" assembleHap --no-daemon
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -eq 0) {
    $outDir = Join-Path $proj 'entry\build\default\outputs\default'
    $hap = Get-ChildItem $outDir -Filter *.hap -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($hap) {
        Write-Host ("HAP: {0} ({1} MB)" -f $hap.FullName, [math]::Round($hap.Length / 1MB, 2))
    } else {
        Write-Host "HAP: not found under $outDir"
    }
}
exit $code
