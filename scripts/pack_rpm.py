#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 RPM 安装包 —— 面向 rpm 系 Linux（openEuler 等）。

⚠ 本包**不一定能装到麒麟 / UOS 上**：产物要求 glibc ≥ 构建机版本，而麒麟 V10（2.23）、
V10 SP1（2.31）、UOS 20（≈2.28）都低于当前构建基线（Deepin 25 = 2.38）。
判定与解法见 README「glibc 基线」与 ARCHITECTURE「Linux 兼容性基线（glibc）」。

与 pack_deb.py 的关系
---------------------
两者**共用同一套 PyInstaller 产物与运行时裁剪逻辑**（本脚本直接 ``import pack_deb``
里的函数与常量，不复制代码、也不修改它），差别只在最后一步的**包格式组装**：

    deb : DEBIAN/ 目录树          + dpkg-deb
    rpm : .spec 文件 + buildroot  + rpmbuild -bb

为什么 ``AutoReqProv: no``
--------------------------
PyInstaller 的产物里含几十个自带 ``.so``，rpm 的自动依赖探测会把它们全算成系统依赖，
生成一长串**本机才有**的 ``libX.so.1()(64bit)`` 之类的 Requires —— 装到目标机上必然
「依赖不满足」。所以关掉自动探测，改为显式声明那几个**缺了必然起不来**的系统库。

依赖（构建机）
--------------
Debian 系需要 rpm 工具链：``sudo apt install -y rpm``（提供 ``rpmbuild``）。
``scripts/setup_linux.sh`` 会在打 rpm 时提示安装。

glibc 基线
----------
与 deb **完全一致**：由构建机的 glibc 决定，裁剪最多降到 2.36；
同样覆盖不了麒麟 V10(2.23) / V10 SP1(2.31) / UOS 20(≈2.28)。
详见 ``pack_deb.py`` 的模块 docstring 与 ``ARCHITECTURE.md`` 的兼容性小节。

用法::

    python scripts/pack_rpm.py              # 构建 + 输出 SM3 摘要
    python scripts/pack_rpm.py --keep       # 保留中间目录 build_rpm/
"""
from __future__ import annotations

import shutil
import string
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path

# 直接路径执行时 sys.path[0] 就是 scripts/，但显式插入更稳（也兼容 -m 方式）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pack_deb import (  # noqa: E402  —— 复用而非复制
    APP_TITLE,
    DEPENDS_LIBS,
    DESKTOP,
    DIST_APP,
    HOMEPAGE,
    LAUNCHER,
    LIB_DIR,
    MAINTAINER,
    PKG,
    PUB,
    RECOMMENDS,
    ROOT,
    SPEC,
    build_machine_glibc,
    build_machine_glibc_version,
    normalize_perms,
    read_version,
    run,
    sm3_of,
    trim_bundle,
)

BUILD_DIR = ROOT / "build_rpm"
RPM_RELEASE = "1"

# Debian 包名 → RPM 包名
# ⚠ 必须是目标体系的**真实包名**，已逐个核对 openEuler 24.03-LTS 仓库索引：
#   · libxcb-cursor0 → xcb-util-cursor（且**只**在 EPOL 仓库，不在 OS 仓库）
#   · fonts-noto-cjk → google-noto-sans-cjk-ttc-fonts（不叫 ...-sans-cjk-fonts）
#   · libxcb-xinerama0 / libxcb-shape0 在 openEuler 均已并入 libxcb，无独立包
DEB_TO_RPM = {
    "libc6": "glibc",
    "libxcb-cursor0": "xcb-util-cursor",
    "libxkbcommon-x11-0": "libxkbcommon-x11",
    "libgl1": "mesa-libGL",
    "libegl1": "mesa-libEGL",
    "libfontconfig1": "fontconfig",
    "libdbus-1-3": "dbus-libs",
    "libxcb-icccm4": "xcb-util-wm",
    "libxcb-image0": "xcb-util-image",
    "libxcb-keysyms1": "xcb-util-keysyms",
    "libxcb-render-util0": "xcb-util-renderutil",
    "libxcb-xinerama0": "libxcb",
    "libxcb-shape0": "libxcb",
    "fonts-noto-cjk": "google-noto-sans-cjk-ttc-fonts",
}


def _split_list(text: str) -> tuple[str, ...]:
    """拆开 deb 侧的 ``"a, b, c"`` 依赖串。"""
    return tuple(part.strip() for part in text.split(",") if part.strip())


# 只能写成软依赖的包：xcb-util-cursor 是 Qt6 xcb 插件的硬需求，但它在 openEuler
# 仅存在于 EPOL 仓库；未启用 EPOL 时根本取不到，若写成 Requires 会让**整包装不上**。
# 写成 Recommends：dnf install 能取到就自动装；取不到则由 README 指引手动补装。
_SOFT_ONLY = ("libxcb-cursor0",)
# libc6 由 rpm_requires() 单独带版本下限，故从库清单里排除
_EXCLUDE_FROM_REQUIRES = ("libc6",) + _SOFT_ONLY


def _to_rpm(deb_names: Iterable[str]) -> tuple[str, ...]:
    """按 DEB_TO_RPM 映射并去重（多个 deb 名会落到同一个 rpm 名，如 libxcb）。"""
    out: list[str] = []
    for name in deb_names:
        rpm_name = DEB_TO_RPM.get(name, name)
        if rpm_name not in out:
            out.append(rpm_name)
    return tuple(out)


def rpm_requires() -> tuple[str, ...]:
    """Requires 列表：glibc 版本下限 + 缺了必然起不来的 Qt 运行时库。

    与 deb 侧同理 —— 产物是按构建机 glibc 打的，基线更低的系统应在 ``rpm -ivh`` 时
    就报依赖不满足，而不是装完运行才崩。探测失败时退化为无版本约束。
    """
    glibc_pkg = DEB_TO_RPM["libc6"]        # 包名也走映射表，避免两处硬编码走偏
    glibc = build_machine_glibc_version()
    libs = _to_rpm(n for n in _split_list(DEPENDS_LIBS)
                   if n not in _EXCLUDE_FROM_REQUIRES)
    return ((f"{glibc_pkg} >= {glibc}",) if glibc else (glibc_pkg,)) + libs


def rpm_recommends() -> tuple[str, ...]:
    """Recommends = deb 侧 RECOMMENDS 的映射 + 只能软依赖的 xcb-util-cursor。"""
    return _to_rpm(_SOFT_ONLY + _split_list(RECOMMENDS))


# dpkg 架构名 → rpm 架构名
ARCH_MAP = {
    "amd64": "x86_64",
    "arm64": "aarch64",
    "loong64": "loongarch64",
    "mips64el": "mips64el",
}

SPEC_TEMPLATE = string.Template("""\
Name:           $pkg
Version:        $version
Release:        $release
Summary:        $title - 本地离线的月度考勤与工资核算桌面工具
License:        GPL-3.0-or-later
URL:            $homepage
BuildArch:      $arch
# 关掉自动依赖探测：产物内自带数十个 .so，自动生成的 Requires 目标机必然不满足
AutoReqProv:    no

Requires:       $requires
Recommends:     $recommends

%description
完全离线运行的 Linux 桌面工具：录入每日考勤状态与加班小时，按内置公式核算
应发工资、社保公积金、个税与实发工资，并导出 Excel 报表。

数据保存在用户数据目录下的「$title」文件夹，按月份一个 JSON 文件。
敏感配置（API 凭据）在 Windows 平台使用 DPAPI，在信创平台使用国密算法
SM2 / SM4 / HMAC-SM3 加密（GM/T 0009 顺序的 SM2 密文 + SM4-CBC + 先加密后 MAC）。

%install
rm -rf %{buildroot}
cp -a $pkgroot/. %{buildroot}/

%files
/usr/bin/$pkg
$lib_dir
/usr/share/applications/$pkg.desktop
/usr/share/icons/hicolor/256x256/apps/$pkg.png
%license /usr/share/licenses/$pkg/COPYING

%changelog
$changelog
""")


def rpm_arch() -> str:
    """探测并映射为 rpm 的架构名（x86_64 / aarch64 / …）。"""
    try:
        out = subprocess.run(["dpkg", "--print-architecture"],
                             capture_output=True, text=True, check=True)
        deb_arch = out.stdout.strip() or "amd64"
    except Exception:
        deb_arch = "amd64"
    return ARCH_MAP.get(deb_arch, deb_arch)


def assemble_pkgroot(version: str, arch: str) -> Path:
    """组装 rpm 的「安装后文件树」（等价于 deb 的目录树），返回其路径。"""
    pkgroot = BUILD_DIR / "pkgroot"
    if pkgroot.exists():
        shutil.rmtree(pkgroot)

    lib = pkgroot / LIB_DIR.lstrip("/")
    lib.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DIST_APP, lib)
    (lib / "AttendanceDesktop").chmod(0o755)

    freed = trim_bundle(lib)
    if freed:
        print(f"  已裁剪运行时冗余：{freed / 1024 / 1024:.1f} MB")

    # 启动器
    bin_dir = pkgroot / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / PKG
    launcher.write_text(LAUNCHER.format(title=APP_TITLE, lib_dir=LIB_DIR), encoding="utf-8")
    launcher.chmod(0o755)

    # 桌面入口
    apps = pkgroot / "usr" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / f"{PKG}.desktop").write_text(
        DESKTOP.format(title=APP_TITLE, pkg=PKG), encoding="utf-8")

    # 图标
    icon_src = ROOT / "app" / "icon.png"
    if icon_src.exists():
        icons = pkgroot / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        icons.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, icons / f"{PKG}.png")
    else:
        print("  [warn] 缺少 app/icon.png，rpm 将不带图标")

    # 许可：rpm 惯例放在 /usr/share/licenses/<pkg>/，由 %license 标记
    lic_dir = pkgroot / "usr" / "share" / "licenses" / PKG
    lic_dir.mkdir(parents=True, exist_ok=True)
    src_lic = ROOT / "LICENSE"
    if src_lic.exists():
        shutil.copy2(src_lic, lic_dir / "COPYING")
    else:
        print("  [warn] 缺少 LICENSE，复制 GPL 协议声明占位")
        (lic_dir / "COPYING").write_text(
            "本程序以 GNU GPL v3（或更新版本）发布，全文见项目仓库 LICENSE 文件。\n",
            encoding="utf-8")

    normalize_perms(pkgroot)
    size_mb = sum(f.stat().st_size for f in pkgroot.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"  文件树就绪：{pkgroot}（{size_mb:.1f} MB）")
    return pkgroot


def build_spec(version: str, arch: str, pkgroot: Path) -> Path:
    """生成 .spec（放在 build_rpm/SPECS/ 下）。"""
    specs = BUILD_DIR / "SPECS"
    specs.mkdir(parents=True, exist_ok=True)
    spec = specs / f"{PKG}.spec"

    # %changelog 格式硬要求：每行以 "* " 开头，日期为 "Mon DD YYYY" 且必须是英文缩写。
    # ⚠ 不能用 strftime("%a %b")：它跟随 locale，中文环境下会输出「六 9月 26 2026」，
    #   令 rpmbuild 报 "%changelog entries must start with *"。
    _now = time.localtime()
    _wd = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[_now.tm_wday]
    _mo = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[_now.tm_mon - 1]
    changelog_date = f"{_wd} {_mo} {_now.tm_mday} {_now.tm_year}"

    spec.write_text(SPEC_TEMPLATE.substitute(
        pkg=PKG,
        version=version,
        release=RPM_RELEASE,
        title=APP_TITLE,
        homepage=HOMEPAGE,
        arch=arch,
        requires=", ".join(rpm_requires()),
        recommends=", ".join(rpm_recommends()),
        lib_dir=LIB_DIR,
        pkgroot=pkgroot,
        changelog=f"* {changelog_date} {MAINTAINER} - {version}-{RPM_RELEASE}\n"
                  f"- 首个 RPM（rpm 系信创）版本，与 deb 同源代码与运行时",
    ), encoding="utf-8")
    print(f"  spec 就绪：{spec}")
    return spec


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("[FATAL] 本脚本只在 Linux 上运行；Windows 请用 pack_windows.py / 一键打包.bat")
        return 1
    if not SPEC.exists():
        print(f"[FATAL] 找不到 spec：{SPEC}")
        return 1
    if not shutil.which("rpmbuild"):
        print("[FATAL] 找不到 rpmbuild —— 请先安装 rpm 工具链：")
        print("        Debian / Deepin / UOS：sudo apt install -y rpm")
        print("        如需覆盖旧基线，必须同时降低构建容器 glibc 与 PySide6 版本（见 ARCHITECTURE.md）")
        return 1
    try:
        import PyInstaller          # 仅用于探测可用性 + 打印版本
    except ImportError:
        print("[FATAL] 当前解释器没有 PyInstaller；请 pip install -r requirements.txt")
        return 1

    version, arch = read_version(), rpm_arch()
    print("=" * 62)
    print(f"  {APP_TITLE} · Linux rpm 构建")
    print(f"  版本 {version}-{RPM_RELEASE} / 架构 {arch} / Python {sys.version.split()[0]}")
    print(f"  PyInstaller {PyInstaller.__version__}")
    glibc = build_machine_glibc()      # 复用 pack_deb 的实现，避免两处口径漂移
    print(f"  构建机 glibc：{glibc}")
    print("=" * 62)
    print("  ⚠ glibc 基线由构建机决定，与 deb 相同：在 glibc 2.38 上构建的包同样")
    print("     装不进麒麟 V10(2.23) / V10 SP1(2.31) / UOS 20(≈2.28)。")

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

    print("\n[3/4] 组装文件树与 spec")
    PUB.mkdir(parents=True, exist_ok=True)
    pkgroot = assemble_pkgroot(version, arch)
    spec = build_spec(version, arch, pkgroot)

    print("\n[4/4] rpmbuild")
    run(["rpmbuild", "-bb", "--define", f"_topdir {BUILD_DIR}", str(spec)])

    rpms = sorted((BUILD_DIR / "RPMS").rglob("*.rpm"))
    if not rpms:
        print("[FATAL] rpmbuild 未产出 .rpm 文件")
        return 1
    src = rpms[0]
    out = PUB / src.name
    shutil.copy2(src, out)

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"\n✅ 产物：{out}（{size_mb:.2f} MB）")
    got = sm3_of(out)
    if got:
        digest, impl = got
        (out.parent / (out.name + ".sm3")).write_text(
            f"{digest}  {out.name}\n", encoding="utf-8")
        print(f"   SM3 摘要（{impl}）：{digest}")
    if "--keep" in sys.argv:
        print(f"   中间目录保留：{BUILD_DIR}")
    else:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        print(f"   已清理中间目录 {BUILD_DIR}（加 --keep 可保留）")
    print(f"   验证：bash scripts/verify_rpm.sh '{out}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
