#!/usr/bin/env bash
# 验证 deb 包内容：解包到临时目录并直接运行，不需要 root、不污染系统。
#
# 用法（仓库根目录）：
#   bash scripts/verify_deb.sh release/attendance-desktop_1.0.0_amd64.deb
#
# 验证项：控制信息 / 文件清单 / 启动器与图标是否就位 / 解包后能否真正启动
set -e

# 解包目录（260MB+）必须**无论脚本怎么退出**都被清理：用 EXIT trap，
# 而不是只在末尾写一句 rm —— 中途 exit 1（启动失败 / SM3 不一致）就会漏下它。
tmp=""
trap 'rm -rf "$tmp"' EXIT

deb="$1"
if [ -z "$deb" ] || [ ! -f "$deb" ]; then
    echo "用法: bash scripts/verify_deb.sh <路径.deb>"
    exit 1
fi

echo "=== 1) 控制信息 ==="
dpkg-deb -I "$deb"

echo
echo "=== 2) 关键文件 ==="
# 先整体取一次清单：逐个 `dpkg-deb -c | grep -q` 会让 tar 子进程收到 SIGPIPE 而报错
# （结果虽正确，但输出难看且易被误判为失败）
listing=$(dpkg-deb -c "$deb")
for f in usr/bin/attendance-desktop \
         usr/share/applications/attendance-desktop.desktop \
         usr/share/icons/hicolor/256x256/apps/attendance-desktop.png \
         usr/lib/attendance-desktop/AttendanceDesktop \
         usr/share/doc/attendance-desktop/copyright \
         usr/share/doc/attendance-desktop/changelog.gz; do
    case "$listing" in
        *"$f"*) echo "  [OK] $f" ;;
        *)      echo "  [缺失] $f" ;;
    esac
done
echo "  普通文件数: $(printf '%s\n' "$listing" | grep -c '^-')"

echo
echo "=== 2b) 权限抽样（Debian 惯例：目录 755 / 普通文件 644 / 可执行 755）==="
printf '%s\n' "$listing" | grep -v _internal | head -20

echo
echo "=== 3) 解包并按真实路径结构试运行 ==="
tmp=$(mktemp -d)
dpkg-deb -x "$deb" "$tmp"
echo "  解包目录: $tmp"
echo "  体积: $(du -sh "$tmp" | cut -f1)"

launcher="$tmp/usr/lib/attendance-desktop/AttendanceDesktop"
[ -x "$launcher" ] || { echo "  [FAIL] 主程序不可执行"; exit 1; }

echo "  以 offscreen 启动，8 秒后自动结束（124 = 一直存活，属正常）"
# 运行日志放进解包目录：它随着上面的 EXIT trap 一起被清掉，不在 /tmp 留垃圾
run_log="$tmp/run.log"
set +e
QT_QPA_PLATFORM=offscreen timeout 8 "$launcher" > "$run_log" 2>&1
code=$?
set -e
if [ "$code" -eq 124 ]; then
    echo "  [OK] 启动成功并持续运行（被 timeout 终止）"
elif [ "$code" -eq 0 ]; then
    echo "  [注意] 程序自行退出了（码 0），请查看日志"
else
    echo "  [FAIL] 启动异常，退出码 $code，日志："
    tail -20 "$run_log"
    exit 1
fi
if [ -s "$run_log" ]; then
    echo "  --- 运行日志 ---"
    tail -10 "$run_log"
fi

echo
echo "=== 4) 校验和（与 .sm3 文件比对）==="
if [ -f "$deb.sm3" ]; then
    pub=$(cut -d' ' -f1 < "$deb.sm3")
    echo "  发布方 SM3: $pub"
    # ⚠ 用 openssl 而不是纯 Python gmssl：后者算 72MB 的 deb 要 4 分半（实测）。
    #   openssl 3.x 原生支持 SM3，且与 GB/T 32905 向量逐位一致。
    set +e
    local_sum=$(openssl dgst -sm3 "$deb" 2>/dev/null | awk '{print $NF}')
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
        echo "         备用：.venv/bin/python -c \"import sys; sys.path.insert(0,'.'); from app import gm; print(gm.sm3_hex(open('$deb','rb').read()))\""
    fi
else
    echo "  未找到 $deb.sm3（跳过比对）"
fi

echo
# 免 root 验证的全过程 —— 临时目录（解包 260MB+）正常路径由开头的 EXIT trap 清理，
# 这里再兑底删一次（幂等）
rm -rf "$tmp"
echo "✅ 验证完成（临时目录已清理）"
