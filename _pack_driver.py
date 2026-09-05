# -*- coding: utf-8 -*-
"""等价于 一键打包.bat 的 Python 构建驱动（可用于 CI / 验证打包流程）。

使用前提：
  * 在仓库根目录执行：python _pack_driver.py
  * 已建好 .venv 并 pip install -r requirements.txt（需含 pyinstaller）
  * 已安装 Inno Setup 6（默认自动探测，或用环境变量 ISCC 指定 ISCC.exe）

步骤：环境检查 → 清理 → PyInstaller(spec) → InnoSetup → 复制免安装版 → 清理 build。
产物输出到 release/ 目录（该目录被 .gitignore 忽略，不入库）。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUB = ROOT / "release"
SPEC = ROOT / "AttendanceDesktop.spec"
ISS = ROOT / "installer.iss"
PYEXE = ROOT / ".venv" / "Scripts" / "pyinstaller.exe"

# —— 定位 ISCC.exe：环境变量 ISCC 优先，否则探测常见安装位置 ——
ISCC = Path(os.environ["ISCC"]) if os.environ.get("ISCC") else None
if ISCC is None or not ISCC.exists():
    ISCC = None
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        # Inno 默认装到 %LOCALAPPDATA%\Programs\Inno Setup 6
        Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Public")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for cand in candidates:
        if cand.exists():
            ISCC = cand
            break
if ISCC is None:
    print("[FATAL] ISCC.exe (Inno Setup 6) not found. Set env ISCC=path/to/ISCC.exe")
    sys.exit(1)

print("=" * 62)
print("  Attendance desktop - one-click build (Python driver)")
print("=" * 62)
for label, p in [("PyInstaller", PYEXE), ("Spec", SPEC), ("ISCC", ISCC), ("InnoScript", ISS)]:
    if not p.exists():
        print(f"[FATAL] {label} not found: {p}")
        sys.exit(1)
    print(f"  [OK] {label:10s} -> {p}")

# —— 清理 ——
print("\n[0/3] Kill + Clean")
try:
    subprocess.run(["taskkill", "/F", "/IM", "AttendanceDesktop.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception:
    pass
for d in [PUB / "AttendanceDesktop", ROOT / "build", ROOT / "dist"]:
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        print(f"  Cleaned {d}")

# —— PyInstaller ——
print("\n[1/3] PyInstaller --noconfirm --clean AttendanceDesktop.spec")
r = subprocess.run([str(PYEXE), "--noconfirm", "--clean", str(SPEC)],
                   cwd=str(ROOT), capture_output=True, text=True)
tail = [l for l in r.stdout.splitlines() if l.strip()][-6:]
for l in tail:
    print(" ", l)
print(f"  returncode={r.returncode}")
if r.returncode != 0:
    err_tail = [l for l in r.stderr.splitlines() if l.strip()][-12:]
    for l in err_tail:
        print("  STDERR:", l)
    sys.exit(1)

EXE = ROOT / "dist" / "AttendanceDesktop" / "AttendanceDesktop.exe"
if not EXE.exists():
    print(f"[FATAL] EXE not produced at {EXE}")
    sys.exit(1)
print(f"  Produced -> {EXE}  ({EXE.stat().st_size / 1024 / 1024:.2f} MB)")

# —— Inno Setup ——
print("\n[2/3] ISCC installer.iss")
# 用文件重定向读取输出，避免控制台代码页解码崩溃（ISCC 中文输出为 UTF-8）
out_txt = ROOT / "_iscc_out.tmp"
err_txt = ROOT / "_iscc_err.tmp"
r2 = subprocess.run([str(ISCC), str(ISS)], cwd=str(ROOT),
                    stdout=open(out_txt, "wb"), stderr=open(err_txt, "wb"))
print(f"  returncode={r2.returncode}")
if r2.returncode != 0:
    data = err_txt.read_bytes().decode("utf-8", "replace") if err_txt.exists() else ""
    for l in data.splitlines()[-8:]:
        print("  STDERR:", l)
    out_txt.unlink(missing_ok=True)
    err_txt.unlink(missing_ok=True)
    sys.exit(1)
data = out_txt.read_bytes().decode("utf-8", "replace") if out_txt.exists() else ""
for l in data.splitlines()[-5:]:
    print(" ", l)
out_txt.unlink(missing_ok=True)
err_txt.unlink(missing_ok=True)

# —— 复制免安装版 ——
print("\n[3/3] Copy dist/AttendanceDesktop -> release\\AttendanceDesktop")
PUB.mkdir(parents=True, exist_ok=True)
DST = PUB / "AttendanceDesktop"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(ROOT / "dist" / "AttendanceDesktop", DST)

# —— 清理 build 临时目录 ——
if (ROOT / "build").exists():
    shutil.rmtree(ROOT / "build", ignore_errors=True)

# —— 汇总产物目录 ——
print("\n" + "=" * 62)
print("  Published contents")
print("=" * 62)
for item in sorted(PUB.iterdir()):
    if item.is_dir():
        total_n = sum(1 for _ in item.rglob("*") if _.is_file())
        total_s = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
        print(f" [DIR] {item.name:30s}  {total_s / 1024 / 1024:8.2f} MB  files={total_n}")
    else:
        print(f" [EXE] {item.name:30s}  {item.stat().st_size / 1024 / 1024:8.2f} MB")

# —— 真实 EXE 启动验证 ——
print("\nSmoke: launch real published AttendanceDesktop.exe for 3s")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
proc = subprocess.Popen([str(DST / "AttendanceDesktop.exe")], cwd=str(DST))
time.sleep(3)
alive = (proc.poll() is None)
if alive:
    proc.terminate()
try:
    proc.wait(timeout=5)
except Exception:
    proc.kill()
print(f"  live 3s -> alive={alive}")

print("\nBuild successful, total 3 stages = 0 exit code.")
