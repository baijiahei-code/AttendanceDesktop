/**
 * Python 兼容数值工具。
 *
 * 桌面版 `app/calc.py` 里存在**两个不同口径**的取整，移植时严禁混用：
 *
 * 1. `_round2(v)` —— 金额专用：
 *    `float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))`
 *    ⚠ 关键点：它先取**最短十进制表示**（`str(v)`）再做 HALF_UP，
 *      所以 443.835 → 443.84（尽管二进制的精确值是 443.83499…）。
 *      而且它**不是** Python 内置 round() 的银行家舍入：2.675 → 2.68。
 *
 * 2. `_f(v)` —— 小时数 / 天数 / 比例专用：`round(float(v), 6)`
 *    这是 Python 内置 round()，语义是「对**二进制精确值**做 round-half-to-even」，
 *    所以 0.1234565 → 0.123456（精确值 0.1234564999…）。
 *
 * 两个函数都按 IEEE 754 的精确语义实现，避免 JS 里 `toFixed` / `Math.round`
 * 的口径差异（`toFixed` 对 1.005 会给 1.00，`Math.round` 又是 half-up 不区分符号）。
 *
 * ArkTS 约束：不使用 `any` / 索引签名 / 结构化类型；全部显式标注类型。
 */

interface DecParts {
  readonly neg: boolean;
  readonly digits: string;
  readonly exp: number;
}

interface Exact {
  /** 尾数（非负整数），值 = m * 2^e */
  readonly m: bigint;
  readonly e: number;
}

function pow10(n: number): bigint {
  return 10n ** BigInt(n);
}

/** 把放大 10^n 的整数还原成定点十进制串（不带符号）。 */
function scaledToDecimalString(scaled: bigint, n: number): string {
  let s: string = scaled.toString();
  if (n > 0) {
    if (s.length <= n) {
      s = '0'.repeat(n - s.length + 1) + s;
    }
    s = s.substring(0, s.length - n) + '.' + s.substring(s.length - n);
  }
  return s;
}

/** 把十进制串拼回 number（等价于「十进制 → 最近的 double」，与 Python 的 float(Decimal) 一致）。 */
function fromScaled(scaled: bigint, n: number): number {
  return Number(scaledToDecimalString(scaled, n));
}

/** 解析 `String(v)` 得到「无符号数字串 + 十进制指数」，值 = digits * 10^exp。 */
function parseShortest(v: number): DecParts {
  let s: string = String(v);
  let neg: boolean = false;
  if (s.charAt(0) === '-') {
    neg = true;
    s = s.substring(1);
  }
  let exp: number = 0;
  const ePos: number = s.search(/[eE]/);
  if (ePos >= 0) {
    exp = Number(s.substring(ePos + 1));
    s = s.substring(0, ePos);
  }
  const dot: number = s.indexOf('.');
  let digits: string = s;
  if (dot >= 0) {
    digits = s.substring(0, dot) + s.substring(dot + 1);
    exp -= s.length - dot - 1;
  }
  const stripped: string = digits.replace(/^0+/, '');
  return { neg: neg, digits: stripped === '' ? '0' : stripped, exp: exp };
}

/** 把 digits*10^exp 按 HALF_UP 取整到 10^-n 的整数倍，返回放大 10^n 后的非负整数。 */
function scaleHalfUp(digits: string, exp: number, n: number): bigint {
  const shift: number = exp + n;
  const num: bigint = BigInt(digits);
  if (shift >= 0) {
    return num * pow10(shift);
  }
  const div: bigint = pow10(-shift);
  let q: bigint = num / div;
  const r: bigint = num % div;
  if (r * 2n >= div) {
    q += 1n;
  }
  return q;
}

/** 把非负 double 精确分解为 m * 2^e（IEEE 754 binary64）。 */
const _buf: ArrayBuffer = new ArrayBuffer(8);
const _view: DataView = new DataView(_buf);

function exactBinary(absV: number): Exact {
  _view.setFloat64(0, absV, false);
  const hi: number = _view.getUint32(0, false);
  const lo: number = _view.getUint32(4, false);
  const expBits: number = (hi >>> 20) & 0x7ff;
  let m: bigint = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
  let e: number;
  if (expBits === 0) {
    e = -1074;
  } else {
    m = m | (1n << 52n);
    e = expBits - 1075;
  }
  return { m: m, e: e };
}

/** 把非负 double 按 round-half-to-even 取整到 10^-n 的整数倍，返回放大 10^n 后的整数。 */
function scaleHalfEven(absV: number, n: number): bigint {
  const ex: Exact = exactBinary(absV);
  if (ex.e >= 0) {
    return (ex.m << BigInt(ex.e)) * pow10(n);
  }
  const k: number = -ex.e;
  // absV * 10^k 是整数：m / 2^k * 10^k = m * 5^k
  const num: bigint = ex.m * 5n ** BigInt(k);
  if (k <= n) {
    return num * pow10(n - k);
  }
  const div: bigint = pow10(k - n);
  let q: bigint = num / div;
  const r: bigint = num % div;
  const twice: bigint = r * 2n;
  if (twice > div) {
    q += 1n;
  } else if (twice === div && q % 2n === 1n) {
    q += 1n;
  }
  return q;
}

/**
 * 金额取整：对应 `app/calc.py::_round2`。
 *
 * 所有金额字段（含派生单价：加班时薪、请假每日扣）都必须走这个函数，
 * 否则会和桌面版的存档值 / Excel 导出差 1 分钱。
 */
export function pyRound2(v: number | null | undefined): number {
  const x: number = v === null || v === undefined ? 0 : v;
  if (!isFinite(x) || x === 0) {
    return x === 0 ? x : 0; // NaN / ±Infinity 归零；保留 -0
  }
  const p: DecParts = parseShortest(x);
  const scaled: bigint = scaleHalfUp(p.digits, p.exp, 2);
  const r: number = fromScaled(scaled, 2);
  return p.neg ? -r : r;
}

/** 非金额字段取整：对应 `app/calc.py::_f`（Python 内置 round(v, 6)）。 */
export function pyRound6(v: number | null | undefined): number {
  const x: number = v === null || v === undefined ? 0 : v;
  if (!isFinite(x) || x === 0) {
    return x === 0 ? x : 0;
  }
  const scaled: bigint = scaleHalfEven(Math.abs(x), 6);
  const r: number = fromScaled(scaled, 6);
  return x < 0 ? -r : r;
}

/**
 * 等价于 Python 的 `f"{v:.Nf}"`（**half-to-even**，对二进制精确值取整）。
 *
 * ⚠ 不能用 `toFixed`：`(2.25).toFixed(1)` 在 V8 里给 "2.3"，而 Python 的
 * `f"{2.25:.1f}"` 给 "2.2"。报表文案要求逐字一致，所以自己算。
 */
export function pyFixed(v: number, digits: number): string {
  if (Number.isNaN(v)) {
    return 'nan';
  }
  if (!isFinite(v)) {
    return v > 0 ? 'inf' : '-inf';
  }
  const neg: boolean = v < 0 || Object.is(v, -0);
  const body: string = scaledToDecimalString(scaleHalfEven(Math.abs(v), digits), digits);
  return (neg ? '-' : '') + body;
}

/** 等价于 Python 的 `f"{v:,}"`（千分位整数）。 */
export function pyGroupedInt(v: number): string {
  const s: string = pyFixed(v, 0);
  const neg: boolean = s.charAt(0) === '-';
  const body: string = neg ? s.substring(1) : s;
  let out: string = '';
  for (let i = 0; i < body.length; i++) {
    if (i > 0 && (body.length - i) % 3 === 0) {
      out += ',';
    }
    out += body.charAt(i);
  }
  return (neg ? '-' : '') + out;
}

/** 等价于 Python 的 `f"{v:,.Nf}"`（千分位 + 定点小数）。 */
export function pyGroupedFixed(v: number, digits: number): string {
  const s: string = pyFixed(v, digits);
  const neg: boolean = s.charAt(0) === '-';
  const body: string = neg ? s.substring(1) : s;
  const dot: number = body.indexOf('.');
  const intPart: string = dot >= 0 ? body.substring(0, dot) : body;
  const fracPart: string = dot >= 0 ? body.substring(dot) : '';
  let grouped: string = '';
  for (let i = 0; i < intPart.length; i++) {
    if (i > 0 && (intPart.length - i) % 3 === 0) {
      grouped += ',';
    }
    grouped += intPart.charAt(i);
  }
  return (neg ? '-' : '') + grouped + fracPart;
}

/**
 * 等价于 Python 的 `f"{v:g}"`（默认 6 位有效数字、去掉尾随 0）。
 *
 * 只用于常量拼文案（220 / 36 / 26 / 3 / 21.75 / 174），实现覆盖这些量级即可：
 * 指数 < -4 或 >= precision 时用科学计数法（与 Python 一致，指数补两位）。
 */
export function pyGeneral(v: number, precision: number = 6): string {
  if (Number.isNaN(v)) {
    return 'nan';
  }
  if (!isFinite(v)) {
    return v > 0 ? 'inf' : '-inf';
  }
  if (v === 0) {
    return '0';
  }
  const neg: boolean = v < 0;
  const abs: number = Math.abs(v);
  const e: number = Math.floor(Math.log10(abs));
  let body: string;
  if (e < -4 || e >= precision) {
    const mantissa: string = trimZeros(pyFixed(abs / Math.pow(10, e), precision - 1));
    const absExp: number = Math.abs(e);
    const expText: string = (absExp < 10 ? '0' : '') + absExp.toString();
    body = mantissa + 'e' + (e < 0 ? '-' : '+') + expText;
  } else {
    const decimals: number = Math.max(0, precision - 1 - e);
    body = trimZeros(pyFixed(abs, decimals));
  }
  return (neg ? '-' : '') + body;
}

function trimZeros(s: string): string {
  if (s.indexOf('.') < 0) {
    return s;
  }
  let end: number = s.length;
  while (end > 0 && s.charAt(end - 1) === '0') {
    end--;
  }
  if (end > 0 && s.charAt(end - 1) === '.') {
    end--;
  }
  return s.substring(0, end);
}
