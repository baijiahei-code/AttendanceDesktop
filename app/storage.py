"""按月 JSON 存档与读写（原子写 + .bak 备份 + 权限收紧）。

默认数据目录优先级：
  1. 环境变量 ATT_DATA_DIR（测试 / 便携场景可整体重定向）
  2. Windows：%LOCALAPPDATA%\\工作考勤表\\data
     其他平台（信创 / Linux）：$XDG_DATA_HOME/工作考勤表/data

敏感字段（见 :data:`_SENSITIVE_KEYS`）的加解密一律交给 :mod:`app.crypto`：
Windows 用 DPAPI，非 Windows 用国密 SM2/SM3/SM4；既有的 ``dpapi:`` 密文与更早的
明文写法都保持向后兼容。

文件权限：POSIX 平台（信创 / Linux）把数据目录收紧到 ``700``、数据文件 ``600`` ——
否则 ``umask 002`` 的桌面发行版会写出 ``775/664``，**同机其他用户可直接读取考勤与
工资数据**（Windows 无此问题：%LOCALAPPDATA% 的 ACL 本身按用户隔离）。
排障时可用 ``ATT_PERMS=off`` 临时关闭这套收紧逻辑。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import traceback

from . import crypto, model

_lock = threading.Lock()

# 设置中需要加密的字段（其余字段为非敏感业务配置）
_SENSITIVE_KEYS = ("api_key",)

_DIR_MODE = 0o700
_FILE_MODE = 0o600


def _hardening_disabled() -> bool:
    """``ATT_PERMS=off`` 时关闭权限收紧（仅供排障；默认始终启用）。"""
    return (os.environ.get("ATT_PERMS") or "").strip().lower() in (
        "off", "0", "false", "no")


def secure_path(path: str, mode: int) -> None:
    """POSIX 下把文件/目录权限收紧到 ``mode``；其它情况静默跳过。

    * Windows：``os.chmod`` 只影响只读位、语义不同，且 %LOCALAPPDATA% 的 ACL
      本身就按用户隔离，无需处理；
    * 文件系统不支持（如某些挂载）：失败不影响功能，故忽略 OSError。
    """
    if os.name != "posix" or _hardening_disabled():
        return
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def default_data_dir() -> str:
    """ATT_DATA_DIR > 平台标准数据目录下的 ``工作考勤表/data``。

    Windows 用 %LOCALAPPDATA%；其他平台（信创 / Linux）遵循 XDG 规范用
    $XDG_DATA_HOME（未设置时回退 ``~/.local/share``）。
    """
    env = os.environ.get("ATT_DATA_DIR")
    if env:
        os.makedirs(env, mode=_DIR_MODE, exist_ok=True)
        secure_path(env, _DIR_MODE)
        return env
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    # 应用目录与数据目录分两层创建：两层都要收紧，
    # 否则中间层可被其他用户进入浏览（即便 data/ 本身是 700）
    app_dir = os.path.join(base, "工作考勤表")
    os.makedirs(app_dir, mode=_DIR_MODE, exist_ok=True)
    secure_path(app_dir, _DIR_MODE)
    target = os.path.join(app_dir, "data")
    os.makedirs(target, mode=_DIR_MODE, exist_ok=True)
    secure_path(target, _DIR_MODE)
    return target


class MonthStore:
    """一个月度数据仓库：管理 ``<数据目录>/YYYY-MM.json``、``settings.json`` 与密钥目录。

    :param directory: 数据目录；省略则用 :func:`default_data_dir`。测试 / 便携场景
        显式传入临时目录，避免读写真实验据。
    """

    def __init__(self, directory: str | None = None):
        self.dir = directory or default_data_dir()
        self.last_error: str | None = None
        # 设置缓存：settings.json 虽小，但每次读取都要走磁盘 IO + 解密
        # （app.crypto.unprotect：Windows 走 DPAPI，其他平台走国密 SM2+SM4），
        # 而界面切省市 / 刷新提示时会频繁读。用 (mtime, size) 做失效判断，
        # 文件未变则直接复用上次解析结果。
        self._settings_cache: dict | None = None
        self._settings_stamp: tuple[float, int] | None = None
        os.makedirs(self.dir, mode=_DIR_MODE, exist_ok=True)
        secure_path(self.dir, _DIR_MODE)
        # 敏感字段加解密交给 app.crypto；密钥目录随数据目录走（便于便携 / 测试重定向）。
        # 这里既设全局默认（供 key_path() 这类无参调用），又留实例字段 —— 实际加解密
        # 显式传入，避免同进程多个 MonthStore 互相串用密钥目录。
        self.key_dir = os.path.join(self.dir, "keys")
        crypto.configure(self.key_dir)
        self._harden_existing()

    def _harden_existing(self) -> None:
        """把数据目录里已有的数据文件权限收紧到 600。

        升级场景必需：旧版本（或旧 umask）留下的 ``664`` 文件不会自己变，
        不主动扫一遍就等于漏改。
        """
        if os.name != "posix" or _hardening_disabled():
            return
        try:
            with os.scandir(self.dir) as it:
                for entry in it:
                    if (entry.is_file() and not entry.is_symlink()
                            and ".json" in entry.name):
                        secure_path(entry.path, _FILE_MODE)
        except OSError:
            pass

    def _file(self, year: int, month: int) -> str:
        """月份存档路径：``<dir>/YYYY-MM.json``（固定零填充格式，也是 list_months 的解析依据）。"""
        return os.path.join(self.dir, f"{year:04d}-{month:02d}.json")

    def list_months(self) -> list[tuple[int, int]]:
        """扫描目录里已有的月份存档，返回 ``[(年, 月), ...]``，按时间倒序。"""
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
        """读取某月存档。

        :return: ``None`` 有**两种**含义 —— ① 该月尚无存档文件；② 文件存在但解析失败。
            后一种情况下 :attr:`last_error` 带异常文本，且**原文件不会被删除**
            （留给 UI 提示，避免「看起来是新月份」掩盖数据损坏）。
        """
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
        """保存某月存档：写 ``.tmp``（先收紧权限）→ 旧文件备份到 ``.bak`` → 原子替换。

        用 ``os.replace`` 而不是「先删后移」，避免中途失败时丢数据。
        """
        with _lock:
            path = self._file(book.year, book.month)
            data = json.dumps(book.to_dict(), ensure_ascii=False, indent=2)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            secure_path(tmp, _FILE_MODE)   # 临时文件也不给 group/other 任何位
            if os.path.exists(path):
                bak = path + ".bak"
                try:
                    if os.path.exists(bak):
                        os.remove(bak)
                    shutil.copyfile(path, bak)
                    secure_path(bak, _FILE_MODE)   # copyfile 按默认 umask 建新文件
                except Exception:
                    pass
            os.replace(tmp, path)  # 原子覆盖（可覆盖已存在文件），避免“先删后移”丢失窗口
            secure_path(path, _FILE_MODE)

    def delete(self, year: int, month: int) -> bool:
        """删除某月存档；返回是否真的删掉了文件（不存在时返回 False，不抛异常）。"""
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
        """读取应用设置（带缓存；返回副本，调用方可自由修改后自行保存）。"""
        path = self._settings_path()
        try:
            st = os.stat(path)
            stamp = (st.st_mtime, st.st_size)
        except OSError:
            # 尚未创建设置文件（首次运行）
            self._settings_cache, self._settings_stamp = {}, None
            return {}
        if self._settings_cache is not None and stamp == self._settings_stamp:
            return dict(self._settings_cache)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        # 透明解密敏感字段（dpapi: / gm1: / 旧版明文 三种形态都兼容）
        for k in _SENSITIVE_KEYS:
            if k in data:
                data[k] = crypto.unprotect(data[k], self.key_dir)
        self._settings_cache, self._settings_stamp = data, stamp
        return dict(data)

    def save_settings(self, data: dict) -> bool:
        """保存应用设置：敏感字段透明加密后落盘，并同步缓存失效戳。

        :return: 是否写入成功（异常就地吞掉并打印 traceback）。
        """
        try:
            os.makedirs(self.dir, mode=_DIR_MODE, exist_ok=True)
            secure_path(self.dir, _DIR_MODE)
            # 透明加密敏感字段，避免明文落盘
            safe = dict(data)
            for k in _SENSITIVE_KEYS:
                if k in safe and safe[k]:
                    safe[k] = crypto.protect(safe[k], self.key_dir)
            path = self._settings_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(safe, f, ensure_ascii=False, indent=2)
            secure_path(path, _FILE_MODE)
            # 同步缓存：避免紧接着的读取再次解密，也让连续保存的中间态一致
            self._settings_cache = dict(data)
            try:
                st = os.stat(path)
                self._settings_stamp = (st.st_mtime, st.st_size)
            except OSError:
                self._settings_stamp = None
            return True
        except Exception:
            traceback.print_exc()
            return False
