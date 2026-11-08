#!/usr/bin/env bash
# One-click build + collect for the HarmonyOS (ArkTS) app -- POSIX shell version.
#
# Why this exists: the .bat is Windows-only. This script covers macOS (DevEco Studio
# is available there) and can also run on Linux / the HarmonyOS PC terminal -- where
# it will clearly report that the HarmonyOS build toolchain is missing, instead of
# failing with a confusing error.
#
# IMPORTANT: a HAP can only be compiled on a machine that has DevEco Studio
# (HarmonyOS SDK + hvigor + node). HarmonyOS PC devices themselves do NOT ship
# that toolchain, so packaging on-device is not possible. On a device you only
# install the produced .hap:  hdc install -r xxx.hap
#
# Usage:
#   ./scripts/pack_hap.sh                # build release HAP
#   ./scripts/pack_hap.sh --debug        # build debug HAP
#   ./scripts/pack_hap.sh --clean        # clean build cache first
#   ./scripts/pack_hap.sh --install      # build, then hdc install + launch
#   ./scripts/pack_hap.sh --check        # only check the toolchain, no build
#   DEVECO_STUDIO_HOME=/path ./scripts/pack_hap.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
PROJ="$ROOT/harmony"

MODE="release"
DO_INSTALL=0
DO_CLEAN=0
CHECK_ONLY=0

usage() {
    cat <<'EOF'
Usage: pack_hap.sh [options]

  --debug        build a debug HAP (default: release)
  --clean        remove build cache before building
  --install      after building, install to the connected device and launch it
  --check        only check the toolchain (no build)
  -h, --help     show this help

Environment:
  DEVECO_STUDIO_HOME   DevEco Studio install dir (auto-detected on macOS)
  HDC                  full path to hdc (default: <DevEco>/sdk/default/openharmony/toolchains/hdc)
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --debug)   MODE="debug" ;;
        --clean)   DO_CLEAN=1 ;;
        --install) DO_INSTALL=1 ;;
        --check)   CHECK_ONLY=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "[ERROR] unknown option: $1"; usage; exit 2 ;;
    esac
    shift
done

say()  { printf '%s\n' "$*"; }
info() { printf '\033[36m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
err()  { printf '\033[31m%s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- toolchain
find_deveco() {
    local candidates=()
    [ -n "${DEVECO_STUDIO_HOME:-}" ] && candidates+=("$DEVECO_STUDIO_HOME")
    candidates+=(
        "/Applications/DevEco-Studio.app/Contents"
        "/Applications/DevEco Studio.app/Contents"
        "/opt/deveco-studio"
        "$HOME/deveco-studio"
        "/opt/DevEco Studio"
        "/d/DevEco Studio"                            # Git Bash / WSL (D: drive)
        "/c/Program Files/Huawei/DevEco Studio"     # Git Bash / WSL (C: drive)
        "/e/DevEco Studio"
    )
    local c n
    for c in "${candidates[@]}"; do
        n=$(node_bin "$c") || true
        if [ -n "$n" ] && [ -f "$c/tools/hvigor/bin/hvigorw.js" ]; then
            printf '%s\n' "$c"
            return 0
        fi
    done
    return 1
}

# node may be node.exe (Windows DevEco used from Git Bash / WSL) or node (macOS/Linux)
node_bin() {
    if [ -x "$1/tools/node/bin/node" ]; then printf '%s\n' "$1/tools/node/bin/node"; return 0; fi
    if [ -x "$1/tools/node/node.exe" ]; then printf '%s\n' "$1/tools/node/node.exe"; return 0; fi
    return 1
}

find_hdc() {
    local deveco="$1"
    if [ -n "${HDC:-}" ] && [ -x "$HDC" ]; then printf '%s\n' "$HDC"; return 0; fi
    if command -v hdc >/dev/null 2>&1; then command -v hdc; return 0; fi
    local p="$deveco/sdk/default/openharmony/toolchains/hdc"
    if [ -x "$p" ]; then printf '%s\n' "$p"; return 0; fi
    return 1
}

read_json5() { # file key
    sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$1" | head -1
}

# Windows hdc.exe cannot open MSYS-style paths (/c/Users/...), so convert when possible.
to_native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s\n' "$1"
    fi
}

uname_s=$(uname -s 2>/dev/null || echo unknown)
uname_m=$(uname -m 2>/dev/null || echo unknown)
info "=== Work Attendance - HarmonyOS build (POSIX) ==="
say  "  platform : $uname_s / $uname_m"
say  "  project  : $PROJ"

if ! DEVECO=$(find_deveco); then
    err "[ERROR] DevEco Studio toolchain not found."
    if [ "$uname_s" = "HarmonyOS" ] || [ "$uname_s" = "OpenHarmony" ]; then
        warn "  This looks like a HarmonyOS PC. A HAP cannot be compiled on the device:"
        warn "  HarmonyOS PCs do not ship the DevEco Studio toolchain (SDK / hvigor / node)."
        warn "  Build it on Windows or macOS instead, then install on this device with:"
        warn "      hdc install -r AttendanceHarmony-v*-unsigned.hap"
    else
        warn "  Install DevEco Studio (Windows/macOS), then either:"
        warn "    export DEVECO_STUDIO_HOME=\"<install dir>\""
        warn "  or pass it inline. On macOS the default is:"
        warn "    /Applications/DevEco-Studio.app/Contents"
        warn "  On Windows use the .bat instead:  one-click build (pack_hap.ps1)."
    fi
    exit 2
fi
NODE=$(node_bin "$DEVECO")
HVIGOR="$DEVECO/tools/hvigor/bin/hvigorw.js"
say  "  DevEco   : $DEVECO"

if [ "$CHECK_ONLY" = "1" ]; then
    say  "  node     : $( "$NODE" --version 2>/dev/null || echo '?' )"
    say  "  hvigor   : $HVIGOR"
    if HDC_PATH=$(find_hdc "$DEVECO"); then say "  hdc      : $HDC_PATH"; else warn "  hdc      : not found (install not possible)"; fi
    say  "[OK] toolchain looks usable."
    exit 0
fi

[ -d "$PROJ" ] || { err "[ERROR] harmony project not found: $PROJ"; exit 2; }

# ---------------------------------------------------------------- clean
if [ "$DO_CLEAN" = "1" ]; then
    info "[0/3] cleaning build cache ..."
    rm -rf "$PROJ/entry/build" "$PROJ/.hvigor"
fi

# ---------------------------------------------------------------- sync core
info "[1/3] sync core/ -> ets/core/ ..."
CORE_SRC="$ROOT/core"
CORE_DST="$PROJ/entry/src/main/ets/core"
if [ -d "$CORE_SRC" ]; then
    mkdir -p "$CORE_DST"
    cp -f "$CORE_SRC"/*.ts "$CORE_DST"/
    # drop stale copies (deleted core file would otherwise keep compiling)
    for f in "$CORE_DST"/*.ts; do
        [ -e "$f" ] || continue
        base=$(basename "$f")
        [ -f "$CORE_SRC/$base" ] || rm -f "$f"
    done
    say  "  $(ls -1 "$CORE_SRC"/*.ts | wc -l | tr -d ' ') file(s)"
fi

# ---------------------------------------------------------------- build
info "[2/3] building HAP ($MODE) ..."
export DEVECO_SDK_HOME="$DEVECO/sdk"
cd "$PROJ"
set +e
"$NODE" "$HVIGOR" --mode module -p product=default -p "buildMode=$MODE" assembleHap --no-daemon
RC=$?
set -e
if [ "$RC" -ne 0 ] && [ "$MODE" != "debug" ]; then
    warn ""
    warn "[WARN] release build failed (exit $RC), retrying with debug ..."
    set +e
    "$NODE" "$HVIGOR" --mode module -p product=default -p buildMode=debug assembleHap --no-daemon
    RC=$?
    set -e
    MODE="debug"
fi
[ "$RC" -eq 0 ] || { err "[ERROR] build failed (exit $RC)"; exit 1; }

# ---------------------------------------------------------------- collect
info "[3/3] collecting artifacts ..."
OUT_DIR="$PROJ/entry/build/default/outputs/default"
HAP=$(ls -t "$OUT_DIR"/*.hap 2>/dev/null | head -1 || true)
[ -n "$HAP" ] || { err "[ERROR] no .hap found under: $OUT_DIR"; exit 1; }
# prefer a signed one if present
SIGNED=$(ls -t "$OUT_DIR"/*.hap 2>/dev/null | grep -v 'unsigned' | head -1 || true)
[ -n "$SIGNED" ] && HAP="$SIGNED"
case "$(basename "$HAP")" in
    *unsigned*) IS_SIGNED=0 ;;
    *)          IS_SIGNED=1 ;;
esac

REPO_ROOT=$(cd "$ROOT/.." && pwd)
REL_DIR="$REPO_ROOT/release"
mkdir -p "$REL_DIR"
VER=$(read_json5 "$PROJ/AppScope/app.json5" versionName)
[ -n "$VER" ] || VER="0.0.0"
TAG=""; [ "$IS_SIGNED" = "0" ] && TAG="-unsigned"
DEST="$REL_DIR/AttendanceHarmony-v${VER}-${MODE}${TAG}.hap"
cp -f "$HAP" "$DEST"

say ""
info "[OK] build finished"
say  "  output : $DEST"
say  "  size   : $(du -k "$DEST" | cut -f1) KB"
if [ "$IS_SIGNED" = "1" ]; then
    say "  signed : yes"
else
    say "  signed : NO (installable on emulator / developer-mode devices only)"
    warn "  note   : to sign it yourself (free, needs a Huawei account):"
    warn "             DevEco Studio > File > Project Structure > Project"
    warn "             > Signing Configs > tick 'Automatically generate signature'"
    warn "           then re-run this script; the signed HAP is picked up automatically."
    warn "           full guide: harmony-app/README.md - Signing and distribution."
fi

# ---------------------------------------------------------------- install
if [ "$DO_INSTALL" = "1" ]; then
    if HDC_PATH=$(find_hdc "$DEVECO"); then
        BUNDLE=$(read_json5 "$PROJ/AppScope/app.json5" bundleName)
        TARGETS=$("$HDC_PATH" list targets 2>/dev/null | tr -d '\r' | grep -v '^$' | head -3 || true)
        say ""
        info "[INSTALL] $HDC_PATH"
        if [ -z "$TARGETS" ] || printf '%s' "$TARGETS" | grep -qi 'empty'; then
            warn "[WARN] no device/emulator connected -- start it and run again."
            exit 0
        fi
        say "          targets: $(printf '%s' "$TARGETS" | paste -sd ',' -)"
        HAP_ARG=$(to_native_path "$DEST")
        OUT=$("$HDC_PATH" install -r "$HAP_ARG" 2>&1 || true)
        printf '%s\n' "$OUT"
        # hdc may exit 0 even on failure -> decide by the success keyword
        if printf '%s' "$OUT" | grep -qi 'install bundle successfully'; then
            if [ -n "$BUNDLE" ]; then
                "$HDC_PATH" shell aa force-stop "$BUNDLE" >/dev/null 2>&1 || true
                "$HDC_PATH" shell aa start -a EntryAbility -b "$BUNDLE" >/dev/null 2>&1 || true
                info "[OK] launched: $BUNDLE"
            fi
        else
            warn "[WARN] install failed -- an unsigned HAP may be rejected on this device."
        fi
    else
        warn ""
        warn "[WARN] hdc not found -- skip install (set HDC=/path/to/hdc)."
    fi
else
    say ""
    info "Next: hdc install -r \"$(to_native_path "$DEST")\""
    info "      or rerun with --install"
fi
