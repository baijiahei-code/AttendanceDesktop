# -*- mode: python ; coding: utf-8 -*-
import os
import re
import sys

# —— Windows 可执行文件属性（公司 / 版权 / 产品名）——
# 版本号只从 installer.iss 的 AppVersion 读取，避免与安装程序漂移。
# 非 Windows 平台 PyInstaller 不写版本资源，保持 None。
_version = '1.0.0'
_spec_path = os.path.abspath(globals().get('SPEC', 'AttendanceDesktop.spec'))
_try_iss = os.path.join(os.path.dirname(_spec_path), 'installer.iss')
try:
    with open(_try_iss, encoding='utf-8-sig') as _f:
        _m = re.search(r'^\s*AppVersion\s*=\s*(.+?)\s*$', _f.read(), re.M)
    if _m:
        _version = _m.group(1)
except OSError:
    pass

_version_info = None
if sys.platform == 'win32':
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    _parts = [int(x) for x in re.findall(r'\d+', _version)][:4]
    _parts += [0] * (4 - len(_parts))
    _version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=tuple(_parts),
            prodvers=tuple(_parts),
            mask=0x3f,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable('080404b0', [
                    StringStruct('CompanyName', '柯一鸣'),
                    StringStruct('FileDescription', '工作考勤表'),
                    StringStruct('FileVersion', _version),
                    StringStruct('InternalName', 'AttendanceDesktop'),
                    StringStruct('LegalCopyright', 'Copyright (C) 2026-present 柯一鸣'),
                    StringStruct('OriginalFilename', 'AttendanceDesktop.exe'),
                    StringStruct('ProductName', '工作考勤表'),
                    StringStruct('ProductVersion', _version),
                ]),
            ]),
            VarFileInfo([VarStruct('Translation', [2052, 1200])]),
        ],
    )


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/icon.ico', 'app')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AttendanceDesktop',
    icon='app/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=_version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AttendanceDesktop',
)
