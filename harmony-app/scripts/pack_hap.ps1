# One-click build + collect script for the HarmonyOS (ArkTS) app.
# NOTE: keep this file ASCII-only -- Windows PowerShell 5.1 reads UTF-8 without BOM as ANSI,
#       non-ASCII text here would turn into mojibake in the console.
#
# Steps:
#   1) locate DevEco Studio (param / env / common install paths)
#   2) optionally clean build cache (-Clean)
#   3) sync core/*.ts -> harmony/entry/src/main/ets/core, then hvigor assembleHap
#      (release by default; retries with debug if release fails)
#   4) copy the .hap into <repo>/release/ with a versioned name
#   5) optionally install to the connected device and launch it (-Install)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/pack_hap.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/pack_hap.ps1 -Install
#   powershell -ExecutionPolicy Bypass -File scripts/pack_hap.ps1 -BuildMode debug
#   powershell -ExecutionPolicy Bypass -File scripts/pack_hap.ps1 -Clean
#   powershell -ExecutionPolicy Bypass -File scripts/pack_hap.ps1 -DevEco "C:\Program Files\Huawei\DevEco Studio"

param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$BuildMode = 'release',
    [string]$DevEco = '',
    [switch]$Install,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$startedAt = Get-Date

function Find-DevEco {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:DEVECO_STUDIO_HOME) { $candidates += $env:DEVECO_STUDIO_HOME }
    $candidates += @(
        'D:\DevEco Studio',
        'C:\Program Files\Huawei\DevEco Studio',
        'C:\Program Files\DevEco Studio',
        'E:\DevEco Studio'
    )
    foreach ($c in $candidates) {
        if (-not $c) { continue }
        $node = Join-Path $c 'tools\node\node.exe'
        $hvigor = Join-Path $c 'tools\hvigor\bin\hvigorw.js'
        if ((Test-Path $node) -and (Test-Path $hvigor)) { return $c }
    }
    return ''
}

function Read-Json5Value {
    param([string]$File, [string]$Key)
    if (-not (Test-Path $File)) { return '' }
    $text = Get-Content $File -Raw
    $m = [regex]::Match($text, '"' + [regex]::Escape($Key) + '"\s*:\s*"([^"]+)"')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Find-Hdc {
    param([string]$DevEcoDir)
    $list = @()
    if ($env:HDC) { $list += $env:HDC }
    $cmd = Get-Command hdc -ErrorAction SilentlyContinue
    if ($cmd) { $list += $cmd.Source }
    if ($DevEcoDir) {
        $list += (Join-Path $DevEcoDir 'sdk\default\openharmony\toolchains\hdc.exe')
    }
    foreach ($p in $list) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return ''
}

Write-Host '=== Work Attendance - HarmonyOS build ===' -ForegroundColor Cyan

$proj = Join-Path $Root 'harmony'
if (-not (Test-Path $proj)) {
    Write-Host "[ERROR] harmony project not found: $proj" -ForegroundColor Red
    exit 2
}

$devEco = Find-DevEco -Explicit $DevEco
if (-not $devEco) {
    Write-Host '[ERROR] DevEco Studio not found.' -ForegroundColor Red
    Write-Host '  Install DevEco Studio, or set the env var:' -ForegroundColor Yellow
    Write-Host '    setx DEVECO_STUDIO_HOME "C:\Program Files\Huawei\DevEco Studio"' -ForegroundColor Yellow
    Write-Host '  or pass: -DevEco "<install dir>"' -ForegroundColor Yellow
    exit 2
}
Write-Host ("  DevEco : {0}" -f $devEco)
Write-Host ("  project: {0}" -f $proj)

# Optional clean: drop build caches so the next build is from scratch.
if ($Clean) {
    Write-Host ''
    Write-Host '[0/3] Cleaning build cache ...' -ForegroundColor Cyan
    foreach ($d in @((Join-Path $proj 'entry\build'), (Join-Path $proj '.hvigor'))) {
        if (Test-Path $d) {
            Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host ("  removed: {0}" -f $d)
        }
    }
}

# 1) sync core -> ets/core, then build
$buildScript = Join-Path $PSScriptRoot 'build_hap.ps1'
Write-Host ''
Write-Host ("[1/3] Building HAP ({0}) ..." -f $BuildMode) -ForegroundColor Cyan
& $buildScript -Root $Root -BuildMode $BuildMode -DevEco $devEco
$code = $LASTEXITCODE
if ($code -ne 0 -and $BuildMode -ne 'debug') {
    Write-Host ''
    Write-Host "[WARN] release build failed (exit $code), retrying with debug ..." -ForegroundColor Yellow
    & $buildScript -Root $Root -BuildMode 'debug' -DevEco $devEco
    $code = $LASTEXITCODE
    $BuildMode = 'debug'
}
if ($code -ne 0) {
    Write-Host "[ERROR] build failed (exit $code)" -ForegroundColor Red
    Write-Host '  Tips: open the project in DevEco Studio once to let it resolve the SDK,' -ForegroundColor Yellow
    Write-Host '        or check the hvigor output above for the first error line.' -ForegroundColor Yellow
    exit 1
}

# 2) pick the newest .hap (signed one wins)
Write-Host ''
Write-Host '[2/3] Collecting artifacts ...' -ForegroundColor Cyan
$outDir = Join-Path $proj 'entry\build\default\outputs\default'
$haps = Get-ChildItem $outDir -Filter *.hap -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending
if (-not $haps -or $haps.Count -eq 0) {
    Write-Host "[ERROR] no .hap found under: $outDir" -ForegroundColor Red
    exit 1
}
$signed = $haps | Where-Object { $_.Name -notmatch 'unsigned' } | Select-Object -First 1
$hap = if ($signed) { $signed } else { $haps[0] }
$isSigned = ($hap.Name -notmatch 'unsigned')

# 3) copy into <repo>/release/
$repoRoot = Split-Path -Parent $Root
$relDir = Join-Path $repoRoot 'release'
if (-not (Test-Path $relDir)) { New-Item -ItemType Directory -Path $relDir -Force | Out-Null }
$ver = Read-Json5Value -File (Join-Path $proj 'AppScope\app.json5') -Key 'versionName'
if (-not $ver) { $ver = '0.0.0' }
$tag = if ($isSigned) { '' } else { '-unsigned' }
$dest = Join-Path $relDir ("AttendanceHarmony-v{0}-{1}{2}.hap" -f $ver, $BuildMode, $tag)
Copy-Item $hap.FullName $dest -Force

$elapsed = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
Write-Host ''
Write-Host ('[3/3] DONE in {0}s' -f $elapsed) -ForegroundColor Green
Write-Host ("  output : {0}" -f $dest)
Write-Host ("  size   : {0} KB" -f [math]::Round((Get-Item $dest).Length / 1KB, 0))
Write-Host ("  signed : {0}" -f $(if ($isSigned) { 'yes' } else { 'NO (installable on emulator / developer-mode devices only)' }))
if (-not $isSigned) {
    Write-Host '  note   : this HAP is UNSIGNED -- only emulator / developer-mode devices.' -ForegroundColor Yellow
    Write-Host '           to sign it yourself (free, needs a Huawei account):' -ForegroundColor Yellow
    Write-Host '             DevEco Studio > File > Project Structure > Project > Signing Configs' -ForegroundColor Yellow
    Write-Host '             > tick "Automatically generate signature" > Sign In > OK' -ForegroundColor Yellow
    Write-Host '           then re-run this script; the signed HAP is picked up automatically.' -ForegroundColor Yellow
    Write-Host '           full guide: harmony-app/README.md - Signing and distribution.' -ForegroundColor Yellow
}

if ($Install) {
    $hdc = Find-Hdc -DevEcoDir $devEco
    if (-not $hdc) {
        Write-Host ''
        Write-Host '[WARN] hdc not found; skip install.' -ForegroundColor Yellow
        Write-Host '       set HDC to the full path of hdc.exe, or add it to PATH.' -ForegroundColor Yellow
        exit 0
    }
    $bundle = Read-Json5Value -File (Join-Path $proj 'AppScope\app.json5') -Key 'bundleName'
    Write-Host ''
    $targets = (& $hdc list targets 2>&1 | Out-String).Trim()
    Write-Host ("[INSTALL] hdc: {0}" -f $hdc) -ForegroundColor Cyan
    if (-not $targets -or $targets -match 'Empty') {
        Write-Host '[WARN] no device/emulator connected.' -ForegroundColor Yellow
        Write-Host '       start the emulator (or connect a device) and run this script again.' -ForegroundColor Yellow
        exit 0
    }
    $firstTargets = (($targets -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -First 3) -join ', '
    Write-Host ("          targets: {0}" -f $firstTargets)
    & $hdc install -r $dest
    if ($LASTEXITCODE -ne 0) {
        Write-Host ('[WARN] install failed (exit {0})' -f $LASTEXITCODE) -ForegroundColor Yellow
        exit 0
    }
    if ($bundle) {
        & $hdc shell aa force-stop $bundle | Out-Null
        & $hdc shell aa start -a EntryAbility -b $bundle | Out-Null
        Write-Host ("[OK] launched: {0}" -f $bundle) -ForegroundColor Green
    }
}
else {
    Write-Host ''
    Write-Host 'Next:  install it with  hdc install -r "<the .hap above>"' -ForegroundColor Cyan
    Write-Host '       or run this script with -Install to do it automatically.' -ForegroundColor Cyan
}
exit 0
