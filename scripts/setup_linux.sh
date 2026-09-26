#!/usr/bin/env bash
# 在 Linux / 信创（Deepin、UOS、麒麟、openEuler 等）上准备开发与打包环境。
# 同一套环境既可用于构建 deb（dpkg-deb），也可用于构建 rpm（需另装 rpm 包提供 rpmbuild）。
#
# 用法（仓库根目录）：
#   bash scripts/setup_linux.sh
#
# 说明：
#   * Debian 系把 venv 拆成独立包，缺了会提示装 python3-venv（需 sudo）。
#   * PySide6 体积大，走清华镜像；gmssl 国内镜像常缺，回退默认 PyPI 源。
set -e
# 切到项目根（本脚本位于 scripts/ 下）—— venv 要建在根目录、app.gm 也在根
cd "$(dirname "$0")/.."

echo "=== 环境自检 ==="
python3 --version
# 只打印 glibc；"产物最低基线"的告警统一交给 scripts/pack_deb.py —— 避免两处判断逻辑漂移
ldd --version 2>/dev/null | head -1 || echo "glibc: 未知"

if ! python3 -c "import venv" 2>/dev/null; then
    echo "[需要] 缺少 python3-venv 模块，请先执行："
    echo "    sudo apt install -y python3.12-venv"
    exit 1
fi

# 注意：上次创建失败会留下"有 python 没 pip"的残骸，只判断目录存在会误跳过 → 判 pip
if [ ! -x .venv/bin/pip ]; then
    echo "=== 创建 venv（如为残骸则先清理）==="
    rm -rf .venv
    python3 -m venv .venv
    if [ ! -x .venv/bin/pip ]; then
        echo "[失败] venv 内没有 pip，通常是缺 python3-venv 包。请执行："
        echo "    sudo apt install -y python3.12-venv"
        exit 1
    fi
fi

echo "=== 安装依赖 ==="
.venv/bin/python -m pip install -q -U pip
echo "-- 主依赖（清华镜像）"
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    PySide6==6.11.2 openpyxl==3.1.5 pyinstaller==6.22.2
echo "-- gmssl（默认源：国内镜像常缺该包）"
.venv/bin/python -m pip install gmssl

echo
echo "=== 依赖清单 ==="
.venv/bin/python -m pip list 2>/dev/null | grep -i -E "pyside6|openpyxl|pyinstaller|gmssl|shiboken"

echo
echo "=== 国密算法自证（应全部 PASS） ==="
.venv/bin/python -m app.gm

echo
echo "=== 打包工具链自检 ==="
if command -v dpkg-deb >/dev/null 2>&1; then
    echo "  dpkg-deb : 可用（可构建 deb）"
else
    echo "  dpkg-deb : 缺失（Debian 系通常自带）"
fi
if command -v rpmbuild >/dev/null 2>&1; then
    echo "  rpmbuild : 可用（可构建 rpm）"
else
    echo "  rpmbuild : 缺失 —— 仅在需要 rpm 包时安装： sudo apt install -y rpm"
fi

echo
echo "✅ 环境就绪"
echo "   运行应用： .venv/bin/python main.py"
echo "   冒烟测试： QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/smoke_test.py"
echo "   构建 deb： .venv/bin/python scripts/pack_deb.py   （或 ./一键打包.sh）"
echo "   构建 rpm： .venv/bin/python scripts/pack_rpm.py   （或 ./一键打包.sh rpm）"
