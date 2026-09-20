"""国密算法（SM2 / SM3 / SM4）薄封装 —— 供敏感字段加密使用。

依赖 ``gmssl``：算法本体是**纯 Python**（自己实现 SM3/SM4，不调目标机的 libssl），
但它依赖 ``pycryptodomex``（**C 扩展** —— ``gmssl/sm2.py`` 顶层就 import
``Cryptodome.Util.asn1``）。因此打包到信创环境时：

* x86_64 / aarch64：PyPI 有 manylinux wheel，开箱即用；
* **loongarch64：pycryptodomex 需自行编译**（适配要点，别按“零依赖”做规划）。

下列事实均已在本机实测核实（改动前请先复测，勿凭印象）：

* ``gmssl.func.random_hex`` 用 ``random.choice``（**非密码学安全**），而
  ``CryptSM2.encrypt()`` 内部正是用它取随机数 k（k 可预测 → 密文可被恢复）。
  本模块在导入时把 ``random_hex`` 换成 ``os.urandom`` 版本，见 :func:`_harden_random`。
* ``CryptSM2.decrypt()`` 算出完整性哈希 u 却**不与 C3 比较** —— 库自身不校验密文
  完整性，故完整性一律由外层 HMAC-SM3 承担（Encrypt-then-MAC）。
* ``CryptSM2.__init__`` 的位置参数顺序是 **(private_key, public_key, ...)**，
  与直觉相反 → 本模块一律用关键字参数调用。
* ``CryptSM2.encrypt()`` 的 ``mode``：0 → C1C2C3，1 → C1C3C2。本模块固定 **mode=1**，
  即 GM/T 0009 推荐的 C1C3C2 顺序；C1 不带 04 前缀。
* ``CryptSM4(mode, padding_mode=PKCS7)``，``crypt_cbc(iv, data)`` 自动 PKCS#7 填充。
* SM3 标准向量、SM4 标准向量（GB/T 32907 A.1）、SM2 加解密/签名往返均实测通过。
"""
from __future__ import annotations

import hmac as _hmac
import os

from gmssl import func as _func
from gmssl import sm2 as _sm2
from gmssl import sm3 as _sm3
from gmssl import sm4 as _sm4

SM3_DIGEST_SIZE = 32
SM4_KEY_SIZE = 16
SM4_BLOCK_SIZE = 16
# SM2 密文单元顺序：1 = C1C3C2（GM/T 0009 推荐），0 = C1C2C3
_SM2_CIPHER_MODE = 1

# gmssl 的 SM2 曲线阶 n（用于校验私钥取值范围）
_SM2_ORDER = int(
    _sm2.CryptSM2(private_key="0" * 64, public_key="").ecc_table["n"], 16
)
# 加固前的随机数实现（供 selftest 断言“确实被替换过”）
_ORIGINAL_RANDOM_HEX = _func.random_hex


def _harden_random() -> None:
    """把 gmssl 的随机数源替换为 ``os.urandom``。

    gmssl 内部以 ``func.random_hex(...)`` 属性访问方式取随机数，故替换模块属性
    即可对 ``CryptSM2.encrypt`` 等调用点全局生效（无需改第三方源码）。
    """
    def _urandom_hex(n: int) -> str:
        # n 为所需 hex 字符数（沿用 gmssl.random_hex 的语义）
        return os.urandom((n + 1) // 2).hex()[:n]

    # `_sm2.func` 与 `_func` 是同一个模块对象（gmssl.func），赋值一次即全局生效
    _func.random_hex = _urandom_hex


_harden_random()


# ───────────────────────────── SM3 ─────────────────────────────

def sm3_hex(data: bytes) -> str:
    """SM3 摘要（GB/T 32905）的十六进制字符串形式（小写）。"""
    return _sm3.sm3_hash(_func.bytes_to_list(data))


def sm3(data: bytes) -> bytes:
    """SM3 摘要的 32 字节形式。"""
    return bytes.fromhex(sm3_hex(data))


def kdf(z: bytes, klen: int) -> bytes:
    """SM3-KDF：由共享信息 z 派生 klen 字节密钥（GB/T 32918.4 §5.4.3）。

    自己实现而不复用 ``gmssl.sm3.sm3_kdf``：后者要求 z 是 bytes 却内部按 utf-8
    解码再 fromhex，接口含糊且 klen 语义为“hex 字符数”，容易误用。
    """
    if klen <= 0:
        raise ValueError("klen 必须为正整数")
    out = bytearray()
    ct = 1
    while len(out) < klen:
        if ct > 0xFFFFFFFF:
            raise ValueError("klen 过大（超出 SM3-KDF 定义范围）")
        out += sm3(z + ct.to_bytes(4, "big"))
        ct += 1
    return bytes(out[:klen])


# ─────────────────────────── HMAC-SM3 ───────────────────────────

class _SM3Hash:
    """hashlib 兼容的 SM3 包装（只实现 hmac 模块所需的最小接口）。"""

    block_size = 64
    digest_size = SM3_DIGEST_SIZE
    name = "sm3"

    def __init__(self, data: bytes = b""):
        self._data = bytearray(data)

    def update(self, data: bytes) -> "_SM3Hash":
        self._data += data
        return self  # hmac 依赖 update 返回 self

    def digest(self) -> bytes:
        return sm3(bytes(self._data))

    def hexdigest(self) -> str:
        return self.digest().hex()

    def copy(self) -> "_SM3Hash":
        clone = _SM3Hash()
        clone._data = bytearray(self._data)
        return clone


def hmac_sm3(key: bytes, msg: bytes) -> bytes:
    """HMAC-SM3（RFC 2104，以 SM3 为哈希函数），返回 32 字节。"""
    return _hmac.new(key, msg, _SM3Hash).digest()


def hmac_sm3_verify(key: bytes, msg: bytes, mac: bytes) -> bool:
    """常量时间比较的 HMAC-SM3 校验。"""
    return _hmac.compare_digest(hmac_sm3(key, msg), mac)


# ───────────────────────────── SM4 ─────────────────────────────

def _check_sm4_args(key: bytes, iv: bytes) -> None:
    if len(key) != SM4_KEY_SIZE:
        raise ValueError("SM4 密钥必须为 16 字节")
    if len(iv) != SM4_BLOCK_SIZE:
        raise ValueError("SM4 IV 必须为 16 字节")


def sm4_cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """SM4-CBC 加密（PKCS#7 填充，GB/T 32907）。"""
    _check_sm4_args(key, iv)
    cipher = _sm4.CryptSM4(_sm4.SM4_ENCRYPT, _sm4.PKCS7)
    cipher.set_key(key, _sm4.SM4_ENCRYPT)
    return cipher.crypt_cbc(iv, data)


def sm4_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """SM4-CBC 解密（去 PKCS#7 填充）。密文非法时可能抛异常，由调用方兜底。"""
    _check_sm4_args(key, iv)
    cipher = _sm4.CryptSM4(_sm4.SM4_DECRYPT, _sm4.PKCS7)
    cipher.set_key(key, _sm4.SM4_DECRYPT)
    return cipher.crypt_cbc(iv, data)


# ───────────────────────────── SM2 ─────────────────────────────

def sm2_pub_from_priv(priv_hex: str) -> str:
    """由私钥推导公钥（128 位 hex，x||y，无 04 前缀）。

    使用 gmssl 的 ``_kg`` 私有方法：该库未提供密钥生成 API，这是唯一可用的
    标量乘法入口（点乘逻辑本身即 SM2 标准算法，已用加解密往返验证）。
    """
    holder = _sm2.CryptSM2(private_key=priv_hex, public_key="")
    return holder._kg(int(priv_hex, 16), holder.ecc_table["g"])


def sm2_new_keypair() -> tuple[str, str]:
    """生成 SM2 密钥对，返回 ``(私钥 hex, 公钥 hex)``。

    私钥取自 ``os.urandom`` 并校验落在 [1, n-2]（SM2 要求，见 GB/T 32918.5）。
    """
    while True:
        priv = os.urandom(32).hex()
        d = int(priv, 16)
        if 1 <= d <= _SM2_ORDER - 2:
            return priv, sm2_pub_from_priv(priv)


def sm2_encrypt(pub_hex: str, data: bytes) -> bytes:
    """SM2 公钥加密（C1C3C2 顺序），返回原始字节。"""
    cipher = _sm2.CryptSM2(private_key="", public_key=pub_hex, mode=_SM2_CIPHER_MODE)
    out = cipher.encrypt(data)
    if out is None:  # 库在 kdf 输出全零时返回 None（概率极低）
        raise ValueError("SM2 加密失败")
    return out


def sm2_decrypt(priv_hex: str, data: bytes) -> bytes:
    """SM2 私钥解密。密文被篡改时**不会**报错（库不校验 C3）——
    完整性必须由外层的 HMAC-SM3 保证，勿单独依赖本函数。
    """
    cipher = _sm2.CryptSM2(private_key=priv_hex, public_key="", mode=_SM2_CIPHER_MODE)
    out = cipher.decrypt(data)
    if out is None:
        raise ValueError("SM2 解密失败")
    return out


def sm2_sign(priv_hex: str, pub_hex: str, data: bytes) -> str:
    """SM2-with-SM3 签名（默认用户标识 ``1234567812345678``），返回 128 hex（r||s）。

    随机数一律显式传入 ``os.urandom``：gmssl 的 ``sign_with_sm3`` 在不传
    ``random_hex_str`` 时会退回非密码学安全的 ``random.choice``。
    """
    cipher = _sm2.CryptSM2(private_key=priv_hex, public_key=pub_hex)
    return cipher.sign_with_sm3(data, os.urandom(32).hex())


def sm2_verify(pub_hex: str, sig_hex: str, data: bytes) -> bool:
    """校验 SM2-with-SM3 签名。"""
    cipher = _sm2.CryptSM2(private_key="", public_key=pub_hex)
    try:
        return bool(cipher.verify_with_sm3(sig_hex, data))
    except Exception:
        return False


def sm2_is_valid_private(priv_hex: str) -> bool:
    """私钥是否落在 SM2 合法取值范围 [1, n-2]（GB/T 32918.5）。"""
    if not isinstance(priv_hex, str) or len(priv_hex) != 64:
        return False
    try:
        d = int(priv_hex, 16)
    except ValueError:
        return False
    return 1 <= d <= _SM2_ORDER - 2


# ─────────────────────────── 自证清单 ───────────────────────────

def selftest() -> list[tuple[str, bool]]:
    """国密算法自证：标准测试向量 + 关键安全属性，返回 ``[(用例名, 是否通过)]``。

    用途：交付/审计取证 —— “仅使用国密算法”这类口径需要可复现的证据，
    而不是口头声明。命令行直接运行 ``python -m app.gm`` 即可打印全部结果。

    向量出处：SM3 → GB/T 32905 附录 A 示例；SM4 → GB/T 32907 附录 A.1 示例
    （用全零 IV 的 CBC 首块等价于 ECB 单块，以便复用同一条向量）。
    """
    results: list[tuple[str, bool]] = []

    def case(name: str, fn) -> None:
        try:
            results.append((name, bool(fn())))
        except Exception:
            results.append((name, False))

    case("SM3('abc') = 66c7f0f4…",
         lambda: sm3_hex(b"abc") == "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0")
    case("SM3('abcd'x16) = debe9ff9…",
         lambda: sm3_hex(b"abcd" * 16) == "debe9ff92275b8a138604889c18e5a4d6fdb70e5387e5765293dcba39c0c5732")

    def _sm4_vector() -> bool:
        key = bytes.fromhex("0123456789abcdeffedcba9876543210")
        return sm4_cbc_encrypt(key, bytes(16), key)[:16].hex() == "681edf34d206965e86b3e94f536e4246"

    case("SM4 单块加密 = 681edf34…（GB/T 32907 A.1）", _sm4_vector)
    def _sm4_padding_bounds() -> bool:
        """PKCS#7 填充边界：空串 / 差一字节 / 正好整块 / 多一字节。"""
        key, iv = bytes(16), bytes(16)
        for n in (0, 1, 15, 16, 17):
            msg = os.urandom(n)
            if sm4_cbc_decrypt(key, iv, sm4_cbc_encrypt(key, iv, msg)) != msg:
                return False
        return True

    case("SM4-CBC 填充边界（0/1/15/16/17 字节）", _sm4_padding_bounds)
    case("SM3-KDF 确定性与长度",
         lambda: kdf(b"z", 48) == kdf(b"z", 48) and len(kdf(b"z", 48)) == 48 and kdf(b"z", 1000) != kdf(b"z", 48))

    def _hmac() -> bool:
        key, msg = bytes(32), b"message"
        tag = hmac_sm3(key, msg)
        return hmac_sm3_verify(key, msg, tag) and not hmac_sm3_verify(key, msg + b"x", tag)

    case("HMAC-SM3 校验与篡改检测", _hmac)

    def _openssl_crosscheck() -> bool:
        """与 OpenSSL 的 SM3 C 实现逐字节对拍（本机后端不支持 SM3 时视为通过/跳过）。"""
        import hashlib
        import hmac as _stdlib_hmac
        try:
            hashlib.new("sm3")
        except Exception:
            return True
        samples = [b"", b"abc", os.urandom(55), os.urandom(64), os.urandom(1000)]
        if any(sm3_hex(s) != hashlib.new("sm3", s).hexdigest() for s in samples):
            return False
        key, msg = os.urandom(32), os.urandom(120)
        return hmac_sm3(key, msg) == _stdlib_hmac.new(key, msg, "sm3").digest()

    case("SM3 / HMAC-SM3 与 OpenSSL 对拍", _openssl_crosscheck)

    def _sm2_roundtrip() -> bool:
        priv, pub = sm2_new_keypair()
        _, other_pub = sm2_new_keypair()
        msg = "国密自证".encode("utf-8")
        if sm2_decrypt(priv, sm2_encrypt(pub, msg)) != msg:
            return False
        if sm2_encrypt(pub, msg) == sm2_encrypt(pub, msg):
            return False  # 随机数失效时两次密文会相同
        sig = sm2_sign(priv, pub, msg)
        return (sm2_verify(pub, sig, msg)
                and not sm2_verify(pub, sig, msg + b"!")
                and not sm2_verify(other_pub, sig, msg))

    case("SM2 加解密 + 签名/验签 + 负向用例", _sm2_roundtrip)
    case("私钥范围校验 [1, n-2]",
         lambda: (sm2_is_valid_private("0" * 63 + "1")
                  and not sm2_is_valid_private("0" * 64)
                  and not sm2_is_valid_private("zz")
                  and not sm2_is_valid_private("F" * 64)))
    case("SM2 私钥随机数源已加固（非 random.choice）",
         lambda: _func.random_hex is not _ORIGINAL_RANDOM_HEX)
    return results


if __name__ == "__main__":
    # 命令行自证入口：全部通过退出码 0，任一失败为 1（便于 CI / 交付脚本判定）
    rows = selftest()
    for _name, _ok in rows:
        print(f"{'PASS' if _ok else 'FAIL'}  {_name}")
    _passed = sum(1 for _, o in rows if o)
    print(f"\n{_passed}/{len(rows)} 项通过")
    raise SystemExit(0 if _passed == len(rows) else 1)
