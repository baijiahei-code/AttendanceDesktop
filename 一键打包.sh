#!/bin/sh
# 一键打包（Linux / 信创）—— 与 Windows 的 一键打包.bat 对称。
#
# 真正的构建逻辑在统一入口 scripts/pack_all.py 里，本文件只是一层薄壳：
# 选好解释器、把参数原样透传。
#
#   Linux   ->  scripts/pack_deb.py     ->  release/attendance-desktop_<版本>_<架构>.deb
#               scripts/pack_rpm.py     ->  release/attendance-desktop-<版本>-<release>.<架构>.rpm
#   Windows ->  scripts/pack_windows.py ->  release/AttendanceDesktop/ 等（Windows 侧用 .bat）
#
# 首次使用请先建好环境：  bash scripts/setup_linux.sh
# 打包完可离线验证：      bash scripts/verify_deb.sh release/*.deb
#                         bash scripts/verify_rpm.sh release/*.rpm
# 需要保留中间目录排查时：./一键打包.sh --keep
#
# 包格式（默认 deb）：
#   ./一键打包.sh            # deb —— Debian 系 Linux（如 Deepin 25）
#   ./一键打包.sh rpm        # rpm —— rpm 系 Linux（如 openEuler 24.03+）
#                            #        需先装工具链：sudo apt install -y rpm
#   ./一键打包.sh all        # 一次出齐 deb + rpm（PyInstaller 各跑一次，耗时翻倍）
#
# ⚠ 能装到哪些系统由**构建机的 glibc**决定，与包格式无关：基线更低的系统
#   （麒麟 V10 / V10 SP1、UOS 20 等）装了也起不来，详见 README「glibc 基线」。

set -e

cd "$(dirname "$0")"

PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "[ERROR] 未找到 $PY"
    echo "        请先执行： bash scripts/setup_linux.sh"
    exit 1
fi

if [ ! -f "scripts/pack_all.py" ]; then
    echo "[ERROR] 未找到统一入口 scripts/pack_all.py（请在仓库根目录执行本脚本）"
    exit 1
fi

# 第一个参数若是已知的包格式就当作 target，否则用默认 deb
# （这样 `./一键打包.sh --keep` 也能把 --keep 原样透传下去）
case "${1:-}" in
    deb|rpm|all) TARGET="$1"; shift ;;
    *)           TARGET=deb ;;
esac

exec "$PY" scripts/pack_all.py "$TARGET" "$@"
