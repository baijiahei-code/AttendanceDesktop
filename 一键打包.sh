#!/bin/sh
# 一键打包（Linux / macOS / Git Bash）—— 与 Windows 的 一键打包.bat 对称，单一入口。
#
# 真正的构建逻辑都在各自脚本里，本文件只是一层薄壳，按第一个参数分派：
#
#   桌面版（默认）： scripts/pack_all.py
#     deb   -> release/attendance-desktop_<版本>_<架构>.deb
#     rpm   -> release/attendance-desktop-<版本>-<release>.<架构>.rpm
#     all   -> 一次出齐 deb + rpm
#
#   鸿蒙版： harmony-app/scripts/pack_hap.sh
#     harmony -> release/AttendanceHarmony-v<版本>-<模式>[-unsigned].hap
#
# 用法：
#   ./一键打包.sh                   # 桌面版 deb（默认）
#   ./一键打包.sh rpm               # 桌面版 rpm
#   ./一键打包.sh all               # 桌面版 deb + rpm
#   ./一键打包.sh harmony           # 鸿蒙 HAP
#   ./一键打包.sh harmony --install # 鸿蒙 HAP + 安装到设备并启动
#   ./一键打包.sh harmony --check   # 只自检鸿蒙工具链
#   ./一键打包.sh --help            # 显示帮助
#
# 首次使用桌面版请先建好环境：  bash scripts/setup_linux.sh
# 打包完可离线验证：            bash scripts/verify_deb.sh release/*.deb
#                              bash scripts/verify_rpm.sh release/*.rpm
#
# ⚠ 桌面版能装到哪些系统由**构建机的 glibc**决定，与包格式无关
#   （麒麟 V10 / V10 SP1、UOS 20 等基线较低，详见 README「glibc 基线」）。
# ⚠ 鸿蒙 HAP 无法在鸿蒙 PC 上编译（设备无 DevEco SDK / hvigor），
#   必须在 Windows 或 macOS 上构建，再 hdc install 到设备。

set -e

cd "$(dirname "$0")"

usage() {
    sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    harmony|hm)
        shift
        if [ ! -f "harmony-app/scripts/pack_hap.sh" ]; then
            echo "[ERROR] 未找到 harmony-app/scripts/pack_hap.sh" >&2
            echo "        请在仓库根目录执行本脚本" >&2
            exit 2
        fi
        exec bash harmony-app/scripts/pack_hap.sh "$@"
        ;;
esac

# ---- 桌面版（原有逻辑）----
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
