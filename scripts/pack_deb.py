#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 Linux / 信创（deb 系）安装包。

用法（在仓库根目录、Linux 上执行）::

    .venv/bin/python scripts/pack_deb.py            # 完整构建
    .venv/bin/python scripts/pack_deb.py --keep     # 保留 build_deb/ 中间目录便于排查
    # 一般不经直接调用，而是经统一入口：scripts/pack_all.py deb

流程：环境检查 → 清理 → PyInstaller(spec) → 组装 deb 目录树 → dpkg-deb 打包 → SM3 摘要

产物：``release/attendance-desktop_<版本>_<架构>.deb``（同目录另存 ``.sm3`` 摘要文件）

设计要点：

* **只在 Linux 执行**：Windows 侧发布请用 ``pack_windows.py`` / ``一键打包.bat``。
* 版本号单一来源：从 ``installer.iss`` 的 ``AppVersion`` 读取，避免两处版本漂移。
* 架构由 ``dpkg --print-architecture`` 自动探测（amd64 / arm64 / loong64 均适用）。
* 用 ``dpkg-deb --build --root-owner-group`` 定属主为 root，**不需要 fakeroot**。
* **glibc 基线由构建机决定**：PyInstaller 会把构建机的 ``libpython`` / ``libstdc++`` /
  GTK-GLib 等动态库一并收进包内，这些库的**符号版本**就是产物的安装下限。实测在
  Deepin 25（glibc 2.38）上构建的包要求 ``GLIBC_2.38``，**装不进**麒麟 V10(2.23) /
  V10 SP1(2.31) / UOS 20(≈2.28)；可用的是 openEuler 24.03+ / Deepin 23+。
  要覆盖旧基线必须**同时**做两件事：① 在低 glibc 容器内构建（``python:3.11-slim-bullseye``
  = 2.31、``python:3.11-slim-buster`` = 2.28）；② **把 PySide6 降到 ≤ 6.7** ——
  PySide6 6.11 的 wheel 标签是 ``manylinux_2_34``，在 2.31/2.28 的容器里根本装不上。
  麒麟 V10 的 2.23 低于 Qt6 全家（≥2.28）的下限，需换 Qt5 技术栈才可能支持。
"""
from __future__ import annotations

import email.utils
import gzip
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 项目根（本脚本位于 scripts/ 下）
PUB = ROOT / "release"
SPEC = ROOT / "AttendanceDesktop.spec"
DIST_APP = ROOT / "dist" / "AttendanceDesktop"
BUILD_DIR = ROOT / "build_deb"

PKG = "attendance-desktop"          # Debian 包名：必须小写 ASCII
APP_TITLE = "工作考勤表"
LIB_DIR = f"/usr/lib/{PKG}"         # 程序本体安装位置（FHS：非 /opt 的本地包用 /usr/lib）
DEFAULT_VERSION = "1.0.0"
MAINTAINER = "工作考勤表 <193697875+baijiahei-code@users.noreply.github.com>"
HOMEPAGE = "https://github.com/baijiahei-code/AttendanceDesktop"

# Qt6 运行时依赖：Depends 只放"缺了必然起不来"的，可选的放 Recommends
DEPENDS = ("libc6, libxcb-cursor0, libxkbcommon-x11-0, libgl1, libegl1, "
           "libfontconfig1, libdbus-1-3")
RECOMMENDS = ("libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, "
              "libxcb-xinerama0, libxcb-shape0, fonts-noto-cjk")

LAUNCHER = """#!/bin/sh
# {title} 启动器
# 部分信创桌面（Wayland 会话）下 Qt6 的 xcb 后端更稳；用户可用环境变量覆盖。
QT_QPA_PLATFORM="${{QT_QPA_PLATFORM:-xcb}}"
export QT_QPA_PLATFORM
exec {lib_dir}/AttendanceDesktop "$@"
"""

DESKTOP = """[Desktop Entry]
Type=Application
Version=1.0
Name={title}
Name[en_US]=Attendance Desktop
GenericName=考勤与工资核算
Comment=本地离线的月度考勤与工资核算工具
Comment[en_US]=Offline monthly attendance and payroll calculator
Exec=/usr/bin/{pkg}
Icon={pkg}
Terminal=false
Categories=Office;Finance;Calculator;
Keywords=考勤;工资;薪酬;attendance;payroll;salary;
StartupNotify=true
StartupWMClass=AttendanceDesktop
"""

POSTINST = """#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
"""

PRERM = """#!/bin/sh
# 卸载不删除用户数据（数据在 XDG_DATA_HOME/{title}，SM2 私钥在同目录 keys/）
set -e
exit 0
"""

# Debian 政策 §12.5：每个包必须附版权声明（用机器可读格式，许可全文引用系统自带副本）
COPYRIGHT = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: AttendanceDesktop
Source: {homepage}

Files: *
Copyright: 2026 baijiahei-code
License: GPL-3.0-or-later
 本程序是自由软件：你可以依据 GNU 通用公共许可证（GPL）第 3 版、
 或（由你选择）任何更新版本的规定，重新发布和/或修改它。
 .
 本程序分发时希望有用，但不提供任何担保，甚至不提供适销性或特定
 用途适用性的默示担保。详见 GNU 通用公共许可证。
 .
 许可证全文由系统提供：/usr/share/common-licenses/GPL-3
 仓库内亦附完整副本：LICENSE
"""

# Debian 政策 §12.7：每个包必须附变更记录（native 包用 changelog.gz）
CHANGELOG = """{pkg} ({version}) unstable; urgency=medium

  * 首个 Linux / 信创（deb 系）版本
  * 敏感配置在 Windows 用 DPAPI、在信创平台用国密 SM2 / SM4 / HMAC-SM3
    加密（GB/T 32918 / 32907 / 32905）
  * 数据目录遵循 XDG 规范；打包 .desktop 入口与 hicolor 图标

 -- {maintainer}  {date}
"""


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def read_version() -> str:
    """从 installer.iss 读 AppVersion（与 Windows 侧发布同源）。"""
    iss = ROOT / "installer.iss"
    if iss.exists():
        text = iss.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r"^\s*AppVersion\s*=\s*([0-9][0-9A-Za-z.\-]*)", text, re.M)
        if m:
            return m.group(1)
    print(f"  [warn] 未能从 installer.iss 读到版本号，回退 {DEFAULT_VERSION}")
    return DEFAULT_VERSION


def dpkg_arch() -> str:
    """探测目标架构（决定 deb 的 Architecture 字段）。"""
    try:
        out = subprocess.run(["dpkg", "--print-architecture"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or "amd64"
    except Exception:
        return "amd64"


def control_text(version: str, arch: str, installed_kb: int) -> str:
    return f"""Package: {PKG}
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Depends: {DEPENDS}
Recommends: {RECOMMENDS}
Installed-Size: {installed_kb}
Maintainer: {MAINTAINER}
Homepage: {HOMEPAGE}
Description: {APP_TITLE} - 本地离线的月度考勤与工资核算桌面工具
 完全离线运行的 Linux 桌面工具：录入每日考勤状态与加班小时，按内置公式核算
 应发工资、社保公积金、个税与实发工资，并导出 Excel 报表。
 .
 数据保存在用户数据目录下的「{APP_TITLE}」文件夹，按月份一个 JSON 文件。
 敏感配置（API 凭据）在 Windows 平台使用 DPAPI，在信创平台使用国密算法
 SM2 / SM4 / HMAC-SM3 加密（GM/T 0009 顺序的 SM2 密文 + SM4-CBC + 先加密后 MAC）。
"""


def _prune(directory: Path, keep: set) -> int:
    """删除目录中不在白名单里的普通文件，返回释放的字节数。"""
    freed = 0
    if not directory.is_dir():
        return freed
    for f in directory.iterdir():
        if f.is_file() and f.name not in keep:
            freed += f.stat().st_size
            f.unlink()
    return freed


def trim_bundle(lib: Path) -> int:
    """裁剪运行时中确定无用的部分，返回释放的字节数。

    只动“个人桌面场景下绝对用不到”的东西：多余的 Qt 语言包与嵌入式平台插件。
    有意**不**动 GTK 主题插件（连带 libgtk-3 约 15 MB）—— 删了界面会退化成
    Fusion 自绘样式，不值得为体积牺牲观感。
    """
    qt = lib / "_internal" / "PySide6" / "Qt"
    # 界面只有中文：Qt 自带 60+ 语言包，每个几百 KB
    freed = _prune(qt / "translations",
                   {"qt_zh_CN.qm", "qtbase_zh_CN.qm", "qt_help_zh_CN.qm"})
    # 桌面只需 X11(xcb) / Wayland / 离屏（离屏供 scripts/verify_deb.sh 用）
    freed += _prune(qt / "plugins" / "platforms",
                    {"libqxcb.so", "libqwayland.so", "libqwayland-egl.so",
                     "libqwayland-generic.so", "libqoffscreen.so", "libqminimal.so"})
    return freed


def normalize_perms(root: Path) -> None:
    """规范权限：目录 755、可执行文件 755、其余文件 644。

    构建机 umask 常为 002，``shutil.copytree`` 会把源目录的 775/664 一并带出，
    结果是**组可写** —— 既违反 Debian 惯例（lintian 报 ``non-standard-dir-perm``
    / ``non-standard-file-perm``），安全审计也把组可写目录当风险点。
    """
    for p in [root, *root.rglob("*")]:
        try:
            if p.is_symlink():
                continue
            if p.is_dir():
                p.chmod(0o755)
            else:
                p.chmod(0o755 if p.stat().st_mode & 0o100 else 0o644)
        except OSError:
            pass


def assemble(deb_root: Path, version: str, arch: str) -> None:
    """组装 deb 目录树。"""
    if deb_root.exists():
        shutil.rmtree(deb_root)
    lib = deb_root / LIB_DIR.lstrip("/")
    lib.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DIST_APP, lib)
    (lib / "AttendanceDesktop").chmod(0o755)

    freed = trim_bundle(lib)
    if freed:
        print(f"  已裁剪运行时冗余：{freed / 1024 / 1024:.1f} MB")

    # 启动器
    bin_dir = deb_root / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / PKG
    launcher.write_text(LAUNCHER.format(title=APP_TITLE, lib_dir=LIB_DIR),
                        encoding="utf-8")
    launcher.chmod(0o755)

    # 桌面入口
    apps = deb_root / "usr" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / f"{PKG}.desktop").write_text(
        DESKTOP.format(title=APP_TITLE, pkg=PKG), encoding="utf-8")

    # 图标（hicolor 256x256；app/icon.png 由 app/icon.ico 转换而来）
    icon_src = ROOT / "app" / "icon.png"
    if icon_src.exists():
        icons = deb_root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        icons.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, icons / f"{PKG}.png")
    else:
        print("  [warn] 缺少 app/icon.png，deb 将不带图标")

    # Debian 政策要求：每个包必须附版权声明（§12.5）与变更记录（§12.7）
    doc = deb_root / "usr" / "share" / "doc" / PKG
    doc.mkdir(parents=True, exist_ok=True)
    (doc / "copyright").write_text(COPYRIGHT.format(homepage=HOMEPAGE), encoding="utf-8")
    (doc / "changelog.gz").write_bytes(gzip.compress(
        CHANGELOG.format(pkg=PKG, version=version, maintainer=MAINTAINER,
                         date=email.utils.formatdate(localtime=True)).encode("utf-8"),
        mtime=0))

    # 权限规范化（必须在内容写完后做）
    normalize_perms(deb_root)

    # DEBIAN 控制信息（Installed-Size 需在内容定稿后统计）
    ctl = deb_root / "DEBIAN"
    ctl.mkdir(parents=True, exist_ok=True)
    installed_kb = sum(f.stat().st_size for f in deb_root.rglob("*") if f.is_file()) // 1024
    (ctl / "control").write_text(control_text(version, arch, installed_kb), encoding="utf-8")
    for name, body in (("postinst", POSTINST), ("prerm", PRERM.format(title=APP_TITLE))):
        f = ctl / name
        f.write_text(body, encoding="utf-8")
        f.chmod(0o755)
    print(f"  deb 树就绪：{deb_root}（Installed-Size {installed_kb} KB）")


def sm3_of(path: Path) -> tuple[str, str] | None:
    """算 SM3 摘要（GB/T 32905），返回 ``(hex, 实现名)``；失败返回 None。

    **优先用系统 OpenSSL 的 C 实现**：实测 76MB 的 deb 用纯 Python gmssl 要跑
    4 分半（89% CPU 空转）完全不可用；OpenSSL 3.x 原生支持 SM3，且
    ``echo -n abc | openssl dgst -sm3`` 与 GB/T 32905 标准向量逐位一致。
    """
    if shutil.which("openssl"):
        try:
            out = subprocess.run(["openssl", "dgst", "-sm3", str(path)],
                                 capture_output=True, text=True, check=True)
            m = re.search(r"=\s*([0-9a-fA-F]{64})", out.stdout)
            if m:
                return m.group(1).lower(), "openssl"
        except Exception:
            pass
    try:
        sys.path.insert(0, str(ROOT))
        from app import gm
        print("  [warn] openssl 不可用，回退纯 Python SM3（大文件会很慢）")
        return gm.sm3_hex(path.read_bytes()), "gmssl-python"
    except Exception as ex:
        print(f"  [warn] 无法计算 SM3 摘要：{ex}")
        return None


def build_machine_glibc() -> str:
    """构建机 glibc 版本（决定产物的最低可安装基线）。"""
    try:
        return os.confstr("CS_GNU_LIBC_VERSION") or "未知"
    except (AttributeError, ValueError, OSError):
        return "未知"


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("[FATAL] 本脚本只在 Linux 上运行；Windows 请用 pack_windows.py / 一键打包.bat")
        return 1
    if not SPEC.exists():
        print(f"[FATAL] 找不到 spec：{SPEC}")
        return 1
    try:
        import PyInstaller          # 仅用于探测可用性 + 打印版本
    except ImportError:
        print("[FATAL] 当前解释器没有 PyInstaller；请 pip install -r requirements.txt")
        return 1
    if not shutil.which("dpkg-deb"):
        print("[FATAL] 找不到 dpkg-deb（请确认这是 deb 系发行版）")
        return 1

    version, arch = read_version(), dpkg_arch()
    glibc = build_machine_glibc()
    print("=" * 62)
    print(f"  {APP_TITLE} · Linux deb 构建")
    print(f"  版本 {version} / 架构 {arch} / Python {sys.version.split()[0]}")
    print(f"  PyInstaller {PyInstaller.__version__}")
    print(f"  构建机 glibc：{glibc}")
    print("=" * 62)
    if re.search(r"2\.(3[5-9]|[4-9]\d)", glibc):
        print("  ⚠ 构建机 glibc 较新：产物的最低基线就是本机，**无法安装到**")
        print("     麒麟 V10 SP1(2.31) / UOS 20(2.28) 等旧系统。")
        print("     如需覆盖旧基线：在 python:3.11-slim-bullseye(2.31) 容器内构建。")

    print("\n[1/4] 清理")
    for d in (ROOT / "build", ROOT / "dist", BUILD_DIR):
        if d.exists():
            shutil.rmtree(d)
            print(f"  已删 {d}")

    print("\n[2/4] PyInstaller")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)])
    if not (DIST_APP / "AttendanceDesktop").exists():
        print(f"[FATAL] 打包产物不存在：{DIST_APP / 'AttendanceDesktop'}")
        return 1

    print("\n[3/4] 组装 deb")
    PUB.mkdir(parents=True, exist_ok=True)
    deb_root = BUILD_DIR / f"{PKG}_{version}_{arch}"
    assemble(deb_root, version, arch)

    deb_out = PUB / f"{PKG}_{version}_{arch}.deb"
    print("\n[4/4] dpkg-deb 打包")
    try:
        run(["dpkg-deb", "--build", "--root-owner-group", str(deb_root), str(deb_out)])
    except subprocess.CalledProcessError:
        # 老版 dpkg-deb 不支持 --root-owner-group 时回退
        print("  [warn] --root-owner-group 不受支持，改用基础 --build")
        run(["dpkg-deb", "--build", str(deb_root), str(deb_out)])

    size_mb = deb_out.stat().st_size / 1024 / 1024
    print(f"\n✅ 产物：{deb_out}（{size_mb:.2f} MB）")
    got = sm3_of(deb_out)
    if got:
        digest, impl = got
        (deb_out.parent / (deb_out.name + ".sm3")).write_text(
            f"{digest}  {deb_out.name}\n", encoding="utf-8")
        print(f"   SM3 摘要（{impl}）：{digest}")
    if "--keep" in sys.argv:
        print(f"   中间目录保留：{BUILD_DIR}")
    else:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        print(f"   已清理中间目录 {BUILD_DIR}（加 --keep 可保留）")
    print(f"   验证：bash scripts/verify_deb.sh '{deb_out}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
