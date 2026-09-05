"""按月 JSON 存档（移植自 C# JsonFileStore）。

默认数据目录优先级：
  1. 环境变量 ATT_DATA_DIR（测试 / 便携场景可整体重定向）
  2. %LOCALAPPDATA%\\工作考勤表\\data（Windows 标准本地目录）
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import shutil
import threading
import traceback
from ctypes import Structure, wintypes

from . import model

_lock = threading.Lock()

# —— Windows DPAPI：加密敏感字段（api_key 等），密钥与当前 Windows 用户账户绑定 ——
# 非Windows平台或DPAPI不可用时退化为明文（仅桌面应用本地存储，无更好方案）。
_ENTROPY = b"AttendancePy/Settings/v1"


class _DATA_BLOB(Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


# CryptProtectData / CryptUnprotectData 都是 BOOL(WINAPI*)(...DATA_BLOB*, ...),
# 签名一致。抽到一处靠 callable 切换。
_CryptProtectW = ctypes.windll.crypt32.CryptProtectData
_CryptUnprotectW = ctypes.windll.crypt32.CryptUnprotectData
_LocalFree = ctypes.windll.kernel32.LocalFree


def _dpapi_call(raw: bytes, op) -> bytes | None:
    """DPAPI 加/解密公共调用骨架；op 取 _CryptProtectW / _CryptUnprotectW。

    返回原始字节；调用方负责 base64 / decode。失败返回 None。
    """
    try:
        ent = _ENTROPY
        blob_in = _DATA_BLOB(len(raw), ctypes.cast(
            ctypes.c_char_p(raw), ctypes.POINTER(ctypes.c_byte)))
        blob_ent = _DATA_BLOB(len(ent), ctypes.cast(
            ctypes.c_char_p(ent), ctypes.POINTER(ctypes.c_byte)))
        blob_out = _DATA_BLOB()
        if not op(
            ctypes.byref(blob_in), None, ctypes.byref(blob_ent),
            None, None, 0, ctypes.byref(blob_out)
        ):
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            _LocalFree(blob_out.pbData)
    except Exception:
        return None


def _dpapi_protect(data: str) -> str:
    """DPAPI 加密：返回 "dpapi:" 前缀 + base64 密文；失败返回原值。"""
    if not data:
        return data
    enc = _dpapi_call(data.encode("utf-8"), _CryptProtectW)
    if enc is None:
        return data
    return "dpapi:" + base64.b64encode(enc).decode("ascii")


def _dpapi_unprotect(token: str) -> str:
    """DPAPI 解密：识别 "dpapi:" 前缀；非该前缀视为旧版明文直接返回（向后兼容）。"""
    if not token or not token.startswith("dpapi:"):
        return token
    raw = base64.b64decode(token[6:])
    dec = _dpapi_call(raw, _CryptUnprotectW)
    if dec is None:
        return token
    try:
        return dec.decode("utf-8")
    except Exception:
        return token


# 设置中需要加密的字段（其余字段为非敏感业务配置）
_SENSITIVE_KEYS = ("api_key",)


def default_data_dir() -> str:
    """ATT_DATA_DIR > %LOCALAPPDATA%\\工作考勤表\\data。"""
    env = os.environ.get("ATT_DATA_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    target = os.path.join(base, "工作考勤表", "data")
    os.makedirs(target, exist_ok=True)
    return target


class MonthStore:
    def __init__(self, directory: str | None = None):
        self.dir = directory or default_data_dir()
        self.last_error: str | None = None
        os.makedirs(self.dir, exist_ok=True)

    def _file(self, year: int, month: int) -> str:
        return os.path.join(self.dir, f"{year:04d}-{month:02d}.json")

    def list_months(self) -> list[tuple[int, int]]:
        with _lock:
            out = []
            if not os.path.isdir(self.dir):
                return out
            for name in os.listdir(self.dir):
                if not name.endswith(".json"):
                    continue
                stem = name[:-5]
                parts = stem.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    y, m = int(parts[0]), int(parts[1])
                    if 1 <= m <= 12:
                        out.append((y, m))
        return sorted(out, key=lambda x: (-x[0], -x[1]))

    def load(self, year: int, month: int) -> model.MonthBook | None:
        path = self._file(year, month)
        self.last_error = None
        with _lock:
            if not os.path.exists(path):
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                book = model.MonthBook.from_dict(raw)
                model.fix_days(book)
                return book
            except Exception as ex:
                # 解析失败：不删原文件，留给 UI 提示，避免“看起来是新月份”掩盖数据损坏
                self.last_error = str(ex)
                traceback.print_exc()
                return None

    def save(self, book: model.MonthBook) -> None:
        with _lock:
            path = self._file(book.year, book.month)
            data = json.dumps(book.to_dict(), ensure_ascii=False, indent=2)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            if os.path.exists(path):
                bak = path + ".bak"
                try:
                    if os.path.exists(bak):
                        os.remove(bak)
                    shutil.copyfile(path, bak)
                except Exception:
                    pass
            os.replace(tmp, path)  # 原子覆盖（可覆盖已存在文件），避免“先删后移”丢失窗口

    def delete(self, year: int, month: int) -> bool:
        path = self._file(year, month)
        with _lock:
            if os.path.exists(path):
                os.remove(path)
                return True
        return False

    # ========== 应用级设置（省份 / 偏好等）==========

    def _settings_path(self) -> str:
        return os.path.join(self.dir, "settings.json")

    def load_settings(self) -> dict:
        try:
            with open(self._settings_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        # 透明解密敏感字段
        for k in _SENSITIVE_KEYS:
            if k in data:
                data[k] = _dpapi_unprotect(data[k])
        return data

    def save_settings(self, data: dict) -> bool:
        try:
            os.makedirs(self.dir, exist_ok=True)
            # 透明加密敏感字段，避免明文落盘
            safe = dict(data)
            for k in _SENSITIVE_KEYS:
                if k in safe and safe[k]:
                    safe[k] = _dpapi_protect(safe[k])
            with open(self._settings_path(), "w", encoding="utf-8") as f:
                json.dump(safe, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            traceback.print_exc()
            return False
