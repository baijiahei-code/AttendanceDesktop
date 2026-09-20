"""敏感字段加解密（跨平台）：令牌格式、密钥管理、后端分派。

令牌形态（settings.json 中某个字段的值）
--------------------------------------
======================  ====================================================
``dpapi:<b64>``         Windows DPAPI，密钥绑定当前 Windows 用户账户
``gm1:<b64>.<b64>.<b64>.<b64>``
                        国密混合加密（信创 / 非 Windows 平台默认）
其他（无前缀）           更早版本的明文 —— **原样返回**，永不转换（向后兼容）
======================  ====================================================

``gm1`` 密文构造（Encrypt-then-MAC）::

    k_master = 16 随机字节                     # SM4 主密钥
    k_enc    = SM3(k_master || 0x01)[:16]      # 加密密钥
    k_mac    = SM3(k_master || 0x02)           # MAC 密钥
    iv       = 16 随机字节
    ct       = SM4-CBC-PKCS7(k_enc, iv, 明文)
    mac      = HMAC-SM3(k_mac, iv || ct)
    ek       = SM2-公钥加密(k_master)           # C1C3C2
    token    = "gm1:" + b64(ek).b64(iv).b64(ct).b64(mac)

为什么还要外层 HMAC：``gmssl`` 的 ``CryptSM2.decrypt`` 算出哈希却不比较 C3，
SM4-CBC 自身也没有完整性保护 —— 于是机密性交给 SM4-CBC、完整性交给 HMAC-SM3
（先加密后 MAC）。三件套 SM2 / SM3 / SM4 全部用上。

密钥落盘
--------
``<数据目录>/keys/sm2_private.hex``，POSIX 权限 0600。**无私钥口令保护**：
此处威胁模型是“同机其他用户 / 误读文件”，不抵御拿到磁盘镜像的攻击者 ——
对外描述请用这个口径，不要夸大。

后端选择
--------
默认 Windows → ``dpapi``，其他平台 → ``gm``；``ATT_CRYPTO=gm|dpapi|plain``
可强制指定（在 Windows 开发机上强制 ``gm`` 即可完整测试国密分支）。
"""
from __future__ import annotations

import base64
import os
import sys
import threading
import time
import traceback

from . import gm

TOKEN_DPAPI = "dpapi:"
TOKEN_GM = "gm1:"

# DPAPI 附加熵：必须沿用旧值，否则既有 dpapi: 密文将无法解开
_DPAPI_ENTROPY = b"AttendancePy/Settings/v1"

_lock = threading.Lock()
_key_dir: str | None = None                  # configure() 设定的默认密钥目录
# 按「密钥文件绝对路径」分桶缓存：(私钥 hex, 公钥 hex)。
# 用字典而非单个变量：一个进程可能同时持有多个 MonthStore（各自不同数据目录，
# 测试用例里很常见）——单变量会被后创建者挤掉，让行为依赖创建顺序。
_keypairs: dict[str, tuple[str, str]] = {}


# ─────────────────────────── 后端选择 ───────────────────────────

def dpapi_available() -> bool:
    """DPAPI 仅 Windows 提供。"""
    return sys.platform == "win32"


def backend() -> str:
    """当前生效的后端：``dpapi`` / ``gm`` / ``plain``。"""
    forced = (os.environ.get("ATT_CRYPTO") or "").strip().lower()
    if forced in ("gm", "dpapi", "plain"):
        return forced
    return "dpapi" if dpapi_available() else "gm"


def describe(key_dir: str | None = None) -> dict:
    """当前加密配置摘要（供诊断显示；不含任何密钥材料）。

    :return: 含下列键的 dict ——
        ``backend``         当前后端：``dpapi`` / ``gm`` / ``plain``
        ``dpapi_available`` 本平台是否支持 DPAPI
        ``key_path``        SM2 私钥文件路径
        ``key_ready``       私钥是否已就绪（已缓存或文件已存在）
        ``algorithms``      算法描述文案（``plain`` 时为「无（plain）」）
    """
    path = key_path(key_dir)
    mode = backend()
    return {
        "backend": mode,
        "dpapi_available": dpapi_available(),
        "key_path": path,
        "key_ready": path in _keypairs or os.path.exists(path),
        "algorithms": "SM2(C1C3C2) + SM4-CBC + HMAC-SM3" if mode != "plain" else "无（plain）",
    }


# ───────────────────────── Windows DPAPI ─────────────────────────

def _dpapi_call(raw: bytes, decrypt: bool) -> bytes | None:
    """调用 CryptProtectData / CryptUnprotectData；失败返回 None。

    延迟 import ``ctypes.wintypes``：它只在 Windows 存在，放在模块顶层会让
    非 Windows 平台**导入本模块就崩溃**（这正是改造前的原始问题）。
    """
    if not dpapi_available():
        return None
    try:
        import ctypes
        from ctypes import Structure, wintypes

        class _DataBlob(Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        op = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
        blob_in = _DataBlob(len(raw), ctypes.cast(
            ctypes.c_char_p(raw), ctypes.POINTER(ctypes.c_byte)))
        ent = _DPAPI_ENTROPY
        blob_ent = _DataBlob(len(ent), ctypes.cast(
            ctypes.c_char_p(ent), ctypes.POINTER(ctypes.c_byte)))
        blob_out = _DataBlob()
        if not op(ctypes.byref(blob_in), None, ctypes.byref(blob_ent),
                  None, None, 0, ctypes.byref(blob_out)):
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


# ───────────────────────── SM2 密钥管理 ─────────────────────────

def configure(key_dir: str) -> None:
    """设定默认密钥目录（通常为 ``<数据目录>/keys``）。

    仅决定 ``key_path()`` 这类无参调用的落点；已缓存的密钥对按目录分桶保留，
    因此多实例切换不会互相清缓存。
    """
    global _key_dir
    _key_dir = key_dir


def _default_key_dir() -> str:
    """未调用 :func:`configure` 时的兜底目录（口径与 ``storage.default_data_dir`` 一致）。"""
    env = os.environ.get("ATT_KEY_DIR")
    if env:
        return env
    if dpapi_available():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "工作考勤表", "keys")


def key_path(key_dir: str | None = None) -> str:
    """SM2 私钥文件路径；``key_dir`` 省略时用 :func:`configure` 设定的默认目录。"""
    return os.path.join(key_dir or _key_dir or _default_key_dir(), "sm2_private.hex")


def _read_priv(path: str) -> str | None:
    """读取私钥文件首个非注释行；不存在或不可读返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        return None
    return None


def _write_new_key_file(path: str) -> str:
    """生成并原子创建密钥文件（``O_EXCL``），返回私钥 hex。"""
    os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
    priv, _pub = gm.sm2_new_keypair()
    try:
        # O_EXCL：并发首启时只有一个进程能创建成功，另一个走 FileExistsError 复用既有密钥
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        existing = _read_priv(path)
        if existing and gm.sm2_is_valid_private(existing):
            return existing
        raise
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("# 工作考勤表 SM2 私钥（国密）；本文件等同密钥本身，请勿复制或公开\n")
            f.write(priv + "\n")
    finally:
        try:
            os.chmod(path, 0o600)  # 兜底：umask 可能放宽权限
        except OSError:
            pass
    return priv


def _load_keypair(key_dir: str | None = None) -> tuple[str, str]:
    """加载（必要时生成）SM2 密钥对；按密钥文件路径缓存。"""
    path = key_path(key_dir)
    with _lock:
        cached = _keypairs.get(path)
        if cached is not None:
            return cached
        priv = _read_priv(path)
        if priv and not gm.sm2_is_valid_private(priv):
            # 文件存在但内容非法：备份后重新生成（避免“永久无法加密”）。
            # 依赖旧私钥的密文本就解不开，重生成不会破坏任何既有文件。
            bad = f"{path}.bad-{int(time.time())}"
            try:
                os.replace(path, bad)
                print(f"[crypto] 私钥文件非法，已备份为 {bad}，将重新生成", file=sys.stderr)
            except OSError:
                pass
            priv = None
        if not priv:
            priv = _write_new_key_file(path)
        pair = (priv, gm.sm2_pub_from_priv(priv))
        _keypairs[path] = pair
        return pair


# ───────────────────────── 国密加解密 ─────────────────────────

def _b64e(data: bytes) -> str:
    """bytes → base64 字符串（标准字母表；令牌与 JSON 里只放 ASCII）。"""
    return base64.b64encode(data).decode("ascii")


def _derive_keys(k_master: bytes) -> tuple[bytes, bytes]:
    """由主密钥派生 ``(加密密钥, MAC 密钥)``。

    加解密两侧必须用同一套派生规则，故抽到一处 —— 改一边忘另一边的后果是
    历史密文全部解不开。
    """
    k_enc = gm.sm3(k_master + b"\x01")[:gm.SM4_KEY_SIZE]
    k_mac = gm.sm3(k_master + b"\x02")
    return k_enc, k_mac


def _gm_protect(data: str, key_dir: str | None = None) -> str:
    """国密加密（Encrypt-then-MAC），返回 ``gm1:`` 令牌 —— 步骤见模块 docstring。

    随机主密钥 → 派生 k_enc / k_mac → SM4-CBC-PKCS7 加密 →
    HMAC-SM3(iv ‖ ct) → SM2(C1C3C2) 包裹主密钥。
    每次调用都换新 iv 与主密钥，因此同一明文两次加密的密文不同。
    """
    _priv, pub = _load_keypair(key_dir)
    k_master = os.urandom(gm.SM4_KEY_SIZE)
    k_enc, k_mac = _derive_keys(k_master)
    iv = os.urandom(gm.SM4_BLOCK_SIZE)
    ct = gm.sm4_cbc_encrypt(k_enc, iv, data.encode("utf-8"))
    mac = gm.hmac_sm3(k_mac, iv + ct)
    ek = gm.sm2_encrypt(pub, k_master)
    return TOKEN_GM + ".".join((_b64e(ek), _b64e(iv), _b64e(ct), _b64e(mac)))


def _gm_unprotect(token: str, key_dir: str | None = None) -> str:
    """解密 ``gm1:`` 令牌。

    任意环节失败（字段数不对、base64 非法、SM2 解不开、HMAC 不匹配、UTF-8 解码失败）
    都**抛异常**，由 :func:`unprotect` 统一兜底成「原样返回 token」。
    """
    priv, _pub = _load_keypair(key_dir)
    parts = token[len(TOKEN_GM):].split(".")
    if len(parts) != 4:
        raise ValueError("gm1 令牌字段数不为 4")
    ek, iv, ct, mac = (base64.b64decode(p) for p in parts)
    k_enc, k_mac = _derive_keys(gm.sm2_decrypt(priv, ek))
    if not gm.hmac_sm3_verify(k_mac, iv + ct, mac):
        raise ValueError("HMAC-SM3 校验失败：密文被篡改或密钥不匹配")
    return gm.sm4_cbc_decrypt(k_enc, iv, ct).decode("utf-8")


# ─────────────────────────── 公开 API ───────────────────────────

def protect(data: str, key_dir: str | None = None) -> str:
    """加密单个敏感字段。

    ``key_dir`` 指定 SM2 密钥目录（调用方通常传自己数据目录下的 ``keys``）；
    省略则用 :func:`configure` 设定的默认目录。

    失败时**返回原文**（与改造前 DPAPI 的行为一致）：宁可明文落盘也不要丢用户
    配置 —— 加密失败会打印 traceback 以便排查。
    """
    if not data:
        return data
    mode = backend()
    if mode == "plain":
        return data
    try:
        if mode == "dpapi":
            enc = _dpapi_call(data.encode("utf-8"), decrypt=False)
            return data if enc is None else TOKEN_DPAPI + _b64e(enc)
        return _gm_protect(data, key_dir)
    except Exception:
        traceback.print_exc()
        return data


def unprotect(token: str, key_dir: str | None = None) -> str:
    """解密单个敏感字段（``key_dir`` 语义同 :func:`protect`）。

    任何失败（密钥缺失、跨平台拿到 dpapi:、密文被篡改、字段根本不是密文）都
    **原样返回 token**，绝不抛异常 —— 调用方无需 try，UI 不会因坏数据崩溃。
    """
    if not token:
        return token
    try:
        if token.startswith(TOKEN_DPAPI):
            raw = base64.b64decode(token[len(TOKEN_DPAPI):])
            dec = _dpapi_call(raw, decrypt=True)
            return token if dec is None else dec.decode("utf-8")
        if token.startswith(TOKEN_GM):
            return _gm_unprotect(token, key_dir)
    except Exception:
        traceback.print_exc()
    return token
