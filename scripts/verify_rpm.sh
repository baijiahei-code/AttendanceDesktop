#!/usr/bin/env bash
# 验证 rpm 包内容：解包到临时目录并直接运行，不需要 root、不污染系统。
#
# 用法（仓库根目录）：
#   bash scripts/verify_rpm.sh release/attendance-desktop-1.0.0-1.x86_64.rpm
#
# 验证项：包头信息 / 依赖声明 / 文件清单与权限 / 解包后能否真正启动 / SM3 摘要
#
# 依赖 rpm 工具链（Debian / Deepin 上需要自行安装）：
#   sudo apt install -y rpm cpio
set -e

rpm_file="$1"
if [ -z "$rpm_file" ] || [ ! -f "$rpm_file" ]; then
    echo "用法: bash scripts/verify_rpm.sh <路径.rpm>"
    exit 1
fi
if ! command -v rpm >/dev/null 2>&1; then
    echo "[ERROR] 未找到 rpm 命令，请先安装： sudo apt install -y rpm cpio"
    exit 1
fi

rpm_abs=$(readlink -f "$rpm_file")

# 普通用户读不了系统包库 /var/lib/rpm，rpm 查询时会往 stderr 刷三条无关的 error
# （"Unable to open sqlite database ..." 等）。让它指向一个空的临时 dbpath 即可彻底
# 消除 —— 元数据全部来自 .rpm 文件本身，与系统包库无关。
RPMDB_TMP=$(mktemp -d)
unpack_dir=""
trap 'rm -rf "$RPMDB_TMP" "$unpack_dir"' EXIT
rpm() { command rpm --dbpath "$RPMDB_TMP" "$@"; }

echo "=== 1) 包头信息 ==="
rpm -qpi "$rpm_abs"

echo
echo "=== 1b) 依赖声明 ==="
echo "  --- Requires ---"
rpm -qp --requires "$rpm_abs" 2>/dev/null || true
echo "  --- Recommends ---"
rpm -qp --recommends "$rpm_abs" 2>/dev/null || true

echo
echo "=== 2) 关键文件 ==="
# 先整体取一次清单：避免逐条 grep 让子进程吃到 SIGPIPE（结果虽对但输出难看）
listing=$(rpm -qpl "$rpm_abs")
for f in /usr/bin/attendance-desktop \
         /usr/share/applications/attendance-desktop.desktop \
         /usr/share/icons/hicolor/256x256/apps/attendance-desktop.png \
         /usr/lib/attendance-desktop/AttendanceDesktop \
         /usr/share/licenses/attendance-desktop/COPYING; do
    case "$listing" in
        *"$f"*) echo "  [OK] $f" ;;
        *)      echo "  [缺失] $f" ;;
    esac
done
echo "  条目总数: $(printf '%s\n' "$listing" | grep -c .)"

echo
echo "=== 2b) 权限抽样（-rwxr-xr-x 等）==="
rpm -qplv "$rpm_abs" | grep -v _internal | head -20

echo
echo "=== 3) 解包并按真实路径结构试运行 ==="
tmp=$(mktemp -d)
unpack_dir="$tmp"
# 优先 rpm2cpio|cpio：实测 rpm2cpio 输出的是标准 cpio 归档（SVR4），最可靠。
# ⚠ 新版 rpm 里 /usr/bin/rpm2cpio 是 rpm2archive 的符号链接，靠 argv[0] 区分行为，
#   所以不能直接调 rpm2archive（它默认写 .tgz 文件，参数语义也不同）。
if command -v rpm2cpio >/dev/null 2>&1 && command -v cpio >/dev/null 2>&1; then
    ( cd "$tmp" && rpm2cpio "$rpm_abs" | cpio -idm --quiet ) || echo "  [WARN] 解包返回非零退出码"
elif command -v rpm2archive >/dev/null 2>&1; then
    ( cd "$tmp" && rpm2archive - < "$rpm_abs" | tar -xzf - ) || echo "  [WARN] rpm2archive 解包返回非零"
else
    echo "  [SKIP] 缺少 rpm2cpio/cpio，无法解包"
    echo "         请安装： sudo apt install -y rpm cpio"
fi
echo "  解包目录: $tmp"
if [ -n "$(ls -A "$tmp" 2>/dev/null)" ]; then
    echo "  体积: $(du -sh "$tmp" | cut -f1)"
fi

launcher="$tmp/usr/lib/attendance-desktop/AttendanceDesktop"
if [ -x "$launcher" ]; then
    echo "  以 offscreen 启动，8 秒后自动结束（124 = 一直存活，属正常）"
    set +e
    QT_QPA_PLATFORM=offscreen timeout 8 "$launcher" > /tmp/verify_rpm_run.log 2>&1
    code=$?
    set -e
    if [ "$code" -eq 124 ]; then
        echo "  [OK] 启动成功并持续运行（被 timeout 终止）"
    elif [ "$code" -eq 0 ]; then
        echo "  [注意] 程序自行退出了（码 0），请查看日志"
    else
        echo "  [FAIL] 启动异常，退出码 $code，日志："
        tail -20 /tmp/verify_rpm_run.log
        exit 1
    fi
    if [ -s /tmp/verify_rpm_run.log ]; then
        echo "  --- 运行日志 ---"
        tail -10 /tmp/verify_rpm_run.log
    fi
else
    echo "  [SKIP] 未解出可执行主程序（解包可能失败），跳过启动测试"
fi

echo
echo "=== 4) 校验和（与 .sm3 文件比对）==="
if [ -f "$rpm_file.sm3" ]; then
    pub=$(cut -d' ' -f1 < "$rpm_file.sm3")
    echo "  发布方 SM3: $pub"
    set +e
    local_sum=$(openssl dgst -sm3 "$rpm_abs" 2>/dev/null | awk '{print $NF}')
    set -e
    if [ -n "$local_sum" ]; then
        echo "  本地重算:   $local_sum"
        if [ "$local_sum" = "$pub" ]; then
            echo "  [OK] SM3 摘要一致"
        else
            echo "  [FAIL] SM3 摘要不一致"
            exit 1
        fi
    else
        echo "  [SKIP] openssl 不支持 sm3（需 OpenSSL 3.x）"
    fi
else
    echo "  未找到 $rpm_file.sm3（跳过比对）"
fi

echo
# 免 root 验证的全过程 —— 临时目录（rpmdb + 解包）由开头的 EXIT trap 自动清理
echo "✅ 验证完成"
