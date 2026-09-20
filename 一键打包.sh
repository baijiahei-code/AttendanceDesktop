#!/bin/sh
# 一键打包（Linux / 信创）—— 与 Windows 的 一键打包.bat 对称。
#
# 真正的构建逻辑在统一入口 scripts/pack_all.py 里，本文件只是一层薄壳：
# 选好解释器、把参数原样透传。
#
#   Linux   ->  scripts/pack_deb.py     ->  release/attendance-desktop_<版本>_<架构>.deb
#   Windows ->  scripts/pack_windows.py ->  release/AttendanceDesktop/ 等（Windows 侧用 .bat）
#
# 首次使用请先建好环境：  bash scripts/setup_linux.sh
# 打包完可离线验证：      bash scripts/verify_deb.sh release/*.deb
# 需要保留中间目录排查时：./一键打包.sh --keep

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

exec "$PY" scripts/pack_all.py deb "$@"
