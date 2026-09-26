#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一打包入口：同一个命令，按平台产出对应版本。

为什么不能「一条命令同时出 Windows 与 Linux 版」
------------------------------------------------
PyInstaller **不能交叉编译**（Windows 上打不出 Linux 可执行文件），deb / rpm 也各自
依赖本机的 ``dpkg-deb`` / ``rpmbuild``。所以「一台机器一次跑出两平台」在技术上不成立。
本脚本解决的是**入口不统一**：两个平台都只记这一个命令，由它按平台分派。

同一平台内则可以一次出齐：Linux 上用 ``all`` 依次构建 deb + rpm。

    Windows  ->  pack_windows.py  ->  release/AttendanceDesktop/        免安装目录
                                      release/工作考勤表_安装程序.exe    Inno 安装程序
    Linux    ->  pack_deb.py     ->  release/attendance-desktop_<版本>_<架构>.deb
                                      release/attendance-desktop_<版本>_<架构>.deb.sm3
                 pack_rpm.py     ->  release/attendance-desktop-<版本>-<release>.<架构>.rpm
                                      release/attendance-desktop-<版本>-<release>.<架构>.rpm.sm3

用法（仓库根目录）::

    python scripts/pack_all.py              # 按当前平台自动分派（Linux 默认 deb）
    python scripts/pack_all.py win          # 强制 Windows 流程（非 Windows 直接拒绝）
    python scripts/pack_all.py deb          # 强制 deb 流程（非 Linux 直接拒绝）
    python scripts/pack_all.py rpm          # 强制 rpm 流程（需 rpmbuild，见 pack_rpm.py）
    python scripts/pack_all.py all          # Linux 上一次出齐 deb + rpm
    python scripts/pack_all.py deb --keep   # --keep 透传给底层脚本（保留中间目录）
    python scripts/pack_all.py --help

双击入口（都是本脚本的薄壳，参数原样透传）::

    Windows : 一键打包.bat
    Linux   : 一键打包.sh        （首次请先 bash scripts/setup_linux.sh 建好 .venv）
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 项目根（本脚本位于 scripts/ 下）
SCRIPTS = Path(__file__).resolve().parent       # 本目录：各平台的构建实现
PUB = ROOT / "release"
IS_WIN = os.name == "nt"

# target -> (底层脚本, 版本说明, 需要的平台族, 平台不符时的提示)
TARGETS = {
    "win": (
        "pack_windows.py",
        "Windows 版：免安装目录 + Inno Setup 安装程序",
        "nt",
        "Windows 版必须在 Windows 上构建（PyInstaller 不能交叉编译）。",
    ),
    "deb": (
        "pack_deb.py",
        "Linux / 信创版：Debian 系 deb 安装包（含 SM3 摘要）",
        "posix",
        "deb 必须在 Debian 系 Linux 上构建（依赖 dpkg-deb）。"
        "请在 Linux 机器（或 WSL）上用同一入口执行。",
    ),
    "rpm": (
        "pack_rpm.py",
        "Linux / 信创版：RPM 安装包（rpm 系 Linux，如 openEuler 24.03+）",
        "posix",
        "rpm 必须在 Linux 上构建（依赖 rpmbuild）。"
        "Debian 系先装工具链：sudo apt install -y rpm",
    ),
    "all": (
        None,                       # 聚合目标：没有单一底层脚本
        "一键出齐：deb + rpm（两者都在本机 Linux 上构建）",
        "posix",
        "deb / rpm 都必须在 Linux 上构建。Windows 侧请用 一键打包.bat。",
    ),
}

# `all` 依次构建的顺序
ALL_TARGETS = ("deb", "rpm")


def parse_args(argv: list[str]) -> tuple[str | None, list[str], bool]:
    """手写解析：位置参数（可选）win/deb，其余原样透传给底层脚本。

    不用 argparse 是因为 ``--keep`` 这类参数需要**原样**透传，而 argparse 会把
    以 ``-`` 开头的未知参数当错误抛出来。
    """
    target: str | None = None
    extra: list[str] = []
    want_help = False
    for a in argv:
        if a in ("-h", "--help"):
            want_help = True
        elif a in TARGETS and target is None:
            target = a
        else:
            extra.append(a)
    return target, extra, want_help


def venv_python() -> Path:
    """优先用项目虚拟环境的解释器（与两个底层脚本的约定一致）。"""
    cand = ROOT / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")
    if cand.exists():
        return cand
    print(f"[WARN] 未找到项目 venv：{cand}")
    print("       改用当前解释器；若提示缺少 pyinstaller，请先建好 .venv 并安装 requirements.txt")
    return Path(sys.executable)


def summarize() -> None:
    """列出 release/ 里的产物 —— 明确这次到底产出了什么。"""
    print("\n" + "=" * 62)
    print("  release/ 产物")
    print("=" * 62)
    if not PUB.exists():
        print("  （release/ 尚未创建）")
        return
    for item in sorted(PUB.iterdir()):
        if item.is_dir():
            files = [f for f in item.rglob("*") if f.is_file()]
            mb = sum(f.stat().st_size for f in files) / 1024 / 1024
            print(f"  [目录] {item.name:<34} {mb:8.2f} MB  ({len(files)} 个文件)")
        else:
            mb = item.stat().st_size / 1024 / 1024
            print(f"  [文件] {item.name:<34} {mb:8.2f} MB")


def run_target(target: str, extra: list[str]) -> int:
    """跑一个 target 的底层脚本，返回其退出码（`all` 会逐个调用本函数）。"""
    script, label, _want_platform, _hint = TARGETS[target]
    script_path = SCRIPTS / script
    if not script_path.exists():
        print(f"\n[FATAL] 找不到底层脚本：{script_path}")
        return 1
    py = venv_python()
    cmd = [str(py), str(script_path), *extra]
    print(f"  底层脚本 : {script}  —— {label}")
    print(f"  解释器   : {py}")
    print(f"  透传参数 : {extra if extra else '（无）'}")
    print("-" * 62, flush=True)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    print("-" * 62)
    print(f"  {script} 退出码 = {rc}")
    return rc


def main(argv: list[str]) -> int:
    target, extra, want_help = parse_args(argv)
    if want_help:
        print(__doc__)
        return 0

    # 未指定 target 时按当前平台自动选择；指定了但平台不符 → 下面给出明确拒绝原因
    target = target or ("win" if IS_WIN else "deb")
    _script, label, want_platform, hint = TARGETS[target]
    family = "nt" if IS_WIN else "posix"

    print("=" * 62)
    print("  统一打包入口（Attendance desktop）")
    print("=" * 62)
    print(f"  当前平台 : {sys.platform}  (os.name={os.name})")
    print(f"  目标版本 : {target} —— {label}")

    if family != want_platform:
        print(f"\n[FATAL] {hint}")
        print("        一键入口：Windows 用 一键打包.bat；Linux 用 ./一键打包.sh [deb|rpm|all]")
        return 2

    # `all`：依次构建 deb + rpm。⚠ PyInstaller 不能复用，两个包各跑一遍，耗时翻倍。
    if target == "all":
        print(f"\n  将依次构建：{' + '.join(ALL_TARGETS)}（PyInstaller 各跑一次，耗时约翻倍）")
        rc = 0
        for i, t in enumerate(ALL_TARGETS, 1):
            print("\n" + "=" * 62)
            print(f"  [{i}/{len(ALL_TARGETS)}] {t}")
            print("=" * 62)
            rc = run_target(t, extra)
            if rc != 0:
                print(f"\n[FAIL] {t} 构建失败（退出码 {rc}），已中止后续步骤。")
                return rc
        summarize()
        print("\n打包完成。")
        return rc

    rc = run_target(target, extra)
    if rc == 0:
        summarize()
        print("\n打包完成。")
    else:
        print("\n打包失败 —— 请查看上面底层脚本的输出。")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
