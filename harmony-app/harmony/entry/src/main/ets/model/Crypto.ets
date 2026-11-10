/**
 * 存档加密（HUKS：鸿蒙系统密钥库）。
 *
 * 为什么用 HUKS：密钥生成在系统密钥库内、不可导出，应用数据被拷走也解不开。
 * 代价：HUKS 只有异步接口（Promise），所以存储层也是异步的。
 *
 * 算法：AES-256-GCM / NoPadding（HUKS 内置），AAD 固定 "ATT1"。
 * 存储格式：`h1:<base64(nonce || 密文本体 || AEAD)>`，nonce 12 字节、AEAD 16 字节。
 *
 * 官方规格（AES/GCM/NoPadding）：
 *  - 加密：NONCE / AAD 可选；不指定 NONCE 时 HUKS 返回「密文 + AEAD + NONCE」。
 *  - 解密：NONCE、AEAD 必选，AAD 可选。
 * 因此解密必须把 AEAD 用 `HUKS_TAG_AE_TAG` 单独传入，不能和密文一起放在 inData 里
 * （否则 initSession 报 401「The parameter does not exist」）。
 *
 * 兜底：HUKS 不可用（个别环境/模拟器）时返回 `h0:` 前缀的明文，并把
 * 失败阶段 + 错误码 记在 lastError 里 —— 界面必须显示原因，绝不静默降级。
 */

import { huks } from '@kit.UniversalKeystoreKit';
import { cryptoFramework } from '@kit.CryptoArchitectureKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';

/** 本应用唯一使用的密钥别名（HUKS 内不可导出）。 */
const KEY_ALIAS: string = 'attendance_store_key';
const NONCE_LEN: number = 12;
/** AES-GCM 的 AEAD（认证标签）长度：官方规格默认 16 字节。 */
const AEAD_LEN: number = 16;
const TAG_ENC: string = 'h1:';
const TAG_PLAIN: string = 'h0:';

const AAD: Uint8Array = new Uint8Array([0x41, 0x54, 0x54, 0x31]); // "ATT1"

/** HUKS_ERROR_NOT_EXIST：部分实现用它「抛错」表示 key 不存在。 */
const ERR_NOT_EXIST: number = 12000011;

/** 把 BusinessError 转成 "code msg" 便于界面直接展示。 */
function errText(e: Error): string {
  const be: BusinessError = e as BusinessError;
  const code: number | undefined = be === undefined ? undefined : be.code;
  const msg: string = (be === undefined || be.message === undefined) ? `${e}` : be.message;
  if (code === undefined) {
    return msg;
  }
  return `code=${code} ${msg}`;
}

/** 编码器/解码器无状态，模块级复用（每次新建一个对象是白花钱）。 */
const ENCODER: util.TextEncoder = new util.TextEncoder();
const DECODER: util.TextDecoder = util.TextDecoder.create('utf-8');
const B64: util.Base64Helper = new util.Base64Helper();

function toBytes(text: string): Uint8Array {
  return ENCODER.encodeInto(text);
}

function fromBytes(bytes: Uint8Array): string {
  return DECODER.decodeToString(bytes);
}

function b64(bytes: Uint8Array): string {
  return B64.encodeToStringSync(bytes);
}

function unb64(text: string): Uint8Array {
  return B64.decodeSync(text);
}

function joinBytes(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out: Uint8Array = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

/** 逐字节拷贝一段：HUKS 对 `slice()` 产生的视图可能参数校验不过。 */
function sliceCopy(src: Uint8Array, start: number, end: number): Uint8Array {
  const out: Uint8Array = new Uint8Array(end - start);
  for (let i = start; i < end; i++) {
    out[i - start] = src[i];
  }
  return out;
}

function randomNonce(): Uint8Array {
  const rnd: cryptoFramework.Random = cryptoFramework.createRandom();
  return rnd.generateRandomSync(NONCE_LEN).data;
}

/** 生成/查询密钥用的属性：只有 ALGORITHM + KEY_SIZE。
 *  ⚠ 生成时不要带上 PADDING / BLOCK_MODE / DIGEST 等「会话级」 tag，
 *    否则密钥属性不完整，后续解密 initSession 会报 401。 */
function keyProps(): huks.HuksParam[] {
  return [
    { tag: huks.HuksTag.HUKS_TAG_ALGORITHM, value: huks.HuksKeyAlg.HUKS_ALG_AES },
    { tag: huks.HuksTag.HUKS_TAG_KEY_SIZE, value: huks.HuksKeySize.HUKS_AES_KEY_SIZE_256 }
  ];
}

/** 加解密会话的公共属性（AES-256-GCM / 无填充 / 无摘要）。 */
function aesProps(): huks.HuksParam[] {
  const props: huks.HuksParam[] = [
    { tag: huks.HuksTag.HUKS_TAG_ALGORITHM, value: huks.HuksKeyAlg.HUKS_ALG_AES },
    { tag: huks.HuksTag.HUKS_TAG_KEY_SIZE, value: huks.HuksKeySize.HUKS_AES_KEY_SIZE_256 },
    { tag: huks.HuksTag.HUKS_TAG_PADDING, value: huks.HuksKeyPadding.HUKS_PADDING_NONE },
    { tag: huks.HuksTag.HUKS_TAG_BLOCK_MODE, value: huks.HuksCipherMode.HUKS_MODE_GCM },
    // GCM 不用摘要，但部分实现要求显式声明 NONE，否则返回参数错误
    { tag: huks.HuksTag.HUKS_TAG_DIGEST, value: huks.HuksKeyDigest.HUKS_DIGEST_NONE }
  ];
  return props;
}

function sessionProps(purpose: number, nonce: Uint8Array): huks.HuksParam[] {
  const props: huks.HuksParam[] = aesProps();
  props.push({ tag: huks.HuksTag.HUKS_TAG_PURPOSE, value: purpose });
  props.push({ tag: huks.HuksTag.HUKS_TAG_NONCE, value: nonce });
  props.push({ tag: huks.HuksTag.HUKS_TAG_ASSOCIATED_DATA, value: AAD });
  return props;
}

/**
 * 执行一次 HUKS 加解密会话（单次 init + finish）。
 *
 * 官方规格（AES/GCM/NoPadding）：
 *  - 加密：NONCE、AAD 可选；不指定 NONCE 时返回「密文 + AEAD + NONCE」（AEAD 16、NONCE 12）。
 *  - 解密：NONCE、AEAD 必选，AAD 可选。
 * 所以解密必须把密文尾部的 AEAD 用 HUKS_TAG_AE_TAG 单独传入，密文本体不含 tag；
 * 把 tag 一起塞进 inData 会让 initSession 直接报 401「parameter does not exist」。
 */
async function runSession(purpose: number, nonce: Uint8Array, input: Uint8Array,
  aead?: Uint8Array): Promise<Uint8Array> {
  const props: huks.HuksParam[] = sessionProps(purpose, nonce);
  if (aead !== undefined) {
    props.push({ tag: huks.HuksTag.HUKS_TAG_AE_TAG, value: aead });
  }
  const options: huks.HuksOptions = { properties: props, inData: input };
  const handle: huks.HuksSessionHandle = await huks.initSession(KEY_ALIAS, options);
  const result: huks.HuksReturnResult = await huks.finishSession(handle.handle, options);
  const out: Uint8Array | undefined = result.outData;
  return out === undefined ? new Uint8Array(0) : out;
}

export class Crypter {
  lastError: string = '';
  /** 最近失败发生在哪个阶段（便于定位）。 */
  lastStage: string = '';
  /** HUKS 是否可用（不可用时降级为明文并置 false）。 */
  available: boolean = true;
  private keyChecked: boolean = false;

  private fail(stage: string, e: Error): void {
    this.available = false;
    this.lastStage = stage;
    this.lastError = `${stage}：${errText(e)}`;
  }

  private async keyExists(): Promise<boolean> {
    const probe: huks.HuksOptions = { properties: keyProps() };
    try {
      return await huks.isKeyItemExist(KEY_ALIAS, probe);
    } catch (e) {
      const be: BusinessError = e as BusinessError;
      const code: number = (be === undefined || be.code === undefined) ? -1 : be.code;
      if (code === ERR_NOT_EXIST) {
        // ⚠ 本机实测：key 不存在时 isKeyItemExist 会抛 12000011，而不是返回 false
        return false;
      }
      this.fail('HUKS 查询密钥', e as Error);
      throw e as Error;
    }
  }

  private async ensureKey(): Promise<void> {
    if (this.keyChecked) {
      return;
    }
    const exist: boolean = await this.keyExists();
    if (!exist) {
      // 生成密钥：ALGORITHM + KEY_SIZE + PURPOSE（与 keyExists 的查询属性保持一致）
      const props: huks.HuksParam[] = keyProps();
      props.push({
        tag: huks.HuksTag.HUKS_TAG_PURPOSE,
        value: huks.HuksKeyPurpose.HUKS_KEY_PURPOSE_ENCRYPT | huks.HuksKeyPurpose.HUKS_KEY_PURPOSE_DECRYPT
      });
      const genOptions: huks.HuksOptions = { properties: props };
      try {
        await huks.generateKeyItem(KEY_ALIAS, genOptions);
      } catch (e) {
        this.fail('HUKS 生成密钥', e as Error);
        throw e as Error;
      }
    }
    this.keyChecked = true;
  }

  private plainFallback(plain: string): string {
    return TAG_PLAIN + b64(toBytes(plain));
  }

  /** 预热：确保密钥已就绪（同时清理历史别名）。启动时调用一次。 */
  async ready(): Promise<boolean> {
    try {
      await this.ensureKey();
      return true;
    } catch (e) {
      return false;
    }
  }

  async encrypt(plain: string): Promise<string> {
    try {
      await this.ensureKey();
    } catch (e) {
      // ensureKey 内部已记录更具体的阶段，这里只兼底
      if (this.lastError.length === 0) {
        this.fail('HUKS 密钥初始化', e as Error);
      }
      return this.plainFallback(plain);
    }
    try {
      const nonce: Uint8Array = randomNonce();
      const cipher: Uint8Array = await runSession(huks.HuksKeyPurpose.HUKS_KEY_PURPOSE_ENCRYPT, nonce,
        toBytes(plain));
      // 官方规格：GCM 输出 = 密文本体 + 16 字节 AEAD
      if (cipher.length <= AEAD_LEN) {
        throw new Error(`密文长度异常（${cipher.length}）`);
      }
      this.available = true;
      this.lastError = '';
      this.lastStage = '';
      return TAG_ENC + b64(joinBytes(nonce, cipher));
    } catch (e) {
      this.fail('HUKS 加密', e as Error);
      return this.plainFallback(plain);
    }
  }

  /** 解密；不认识的格式按明文处理。 */
  async decrypt(stored: string): Promise<string> {
    if (stored.startsWith(TAG_PLAIN)) {
      return fromBytes(unb64(stored.substring(TAG_PLAIN.length)));
    }
    if (!stored.startsWith(TAG_ENC)) {
      return stored;
    }
    try {
      await this.ensureKey();
    } catch (e) {
      if (this.lastError.length === 0) {
        this.fail('HUKS 密钥初始化', e as Error);
      }
      throw new Error(this.lastError);
    }
    try {
      const raw: Uint8Array = unb64(stored.substring(TAG_ENC.length));
      if (raw.length <= NONCE_LEN + AEAD_LEN) {
        throw new Error('密文长度异常');
      }
      const nonce: Uint8Array = sliceCopy(raw, 0, NONCE_LEN);
      const cipher: Uint8Array = sliceCopy(raw, NONCE_LEN, raw.length);
      // 解密：NONCE、AEAD 必选 —— AEAD 单独取出，body 不含 tag
      const aead: Uint8Array = sliceCopy(cipher, cipher.length - AEAD_LEN, cipher.length);
      const body: Uint8Array = sliceCopy(cipher, 0, cipher.length - AEAD_LEN);
      const plain: Uint8Array = await runSession(huks.HuksKeyPurpose.HUKS_KEY_PURPOSE_DECRYPT, nonce, body,
        aead);
      this.available = true;
      return fromBytes(plain);
    } catch (e) {
      this.fail('HUKS 解密', e as Error);
      throw new Error(this.lastError);
    }
  }
}