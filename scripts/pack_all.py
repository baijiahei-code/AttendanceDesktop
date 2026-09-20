#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一打包入口：同一个命令，按平台产出对应版本。

为什么不是「一条命令同时出两个版本」
------------------------------------
PyInstaller **不能交叉编译**（Windows 上打不出 Linux 可执行文件），deb 也必须在
Debian 系上用 ``dpkg-deb`` 生成。所以「一台机器一次跑出两平台」在技术上不成立。
本脚本解决的是**入口不统一**：两个平台都只记这一个命令，由它按平台分派。

    Windows  ->  pack_windows.py  ->  release/AttendanceDesktop/        免安装目录
                                      release/工作考勤表_安装程序.exe    Inno 安装程序
    Linux    ->  pack_deb.py     ->  release/attendance-desktop_<版本>_<架构>.deb
                                      release/attendance-desktop_<版本>_<架构>.deb.sm3

用法（仓库根目录）::

    python scripts/pack_all.py              # 按当前平台自动分派
    python scripts/pack_all.py win          # 强制 Windows 流程（非 Windows 直接拒绝）
    python scripts/pack_all.py deb          # 强制 deb 流程（非 Linux 直接拒绝）
    python scripts/pack_all.py deb --keep   # --keep 透传给 pack_deb.py（保留 build_deb/）
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
}


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


def main(argv: list[str]) -> int:
    target, extra, want_help = parse_args(argv)
    if want_help:
        print(__doc__)
        return 0

    # 未指定 target 时按当前平台自动选择；指定了但平台不符 → 下面给出明确拒绝原因
    target = target or ("win" if IS_WIN else "deb")
    script, label, want_platform, hint = TARGETS[target]
    family = "nt" if IS_WIN else "posix"

    print("=" * 62)
    print("  统一打包入口（Attendance desktop）")
    print("=" * 62)
    print(f"  当前平台 : {sys.platform}  (os.name={os.name})")
    print(f"  目标版本 : {target} —— {label}")
    print(f"  底层脚本 : {script}")

    if family != want_platform:
        print(f"\n[FATAL] {hint}")
        print("        两个平台各有一个一键脚本（一键打包.bat / 一键打包.sh），")
        print("        请在目标平台上执行同一入口。")
        return 2

    script_path = SCRIPTS / script
    if not script_path.exists():
        print(f"\n[FATAL] 找不到底层脚本：{script_path}")
        return 1

    py = venv_python()
    cmd = [str(py), str(script_path), *extra]
    print(f"  解释器   : {py}")
    print(f"  透传参数 : {extra if extra else '（无）'}")
    print("-" * 62, flush=True)

    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode

    print("-" * 62)
    print(f"  {script} 退出码 = {rc}")
    if rc == 0:
        summarize()
        print("\n打包完成。")
    else:
        print("\n打包失败 —— 请查看上面底层脚本的输出。")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
