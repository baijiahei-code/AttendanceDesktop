/**
 * 月度账本数据模型（对应桌面版 `app/model.py`）。
 *
 * ⚠ 所有字段名保持 Python 的 snake_case —— 它们就是存档 JSON 的键名，
 *   改成 camelCase 会让历史存档读不进来。
 *
 * JSON 边界层只有这里：`from_dict(raw)` 收「全 optional 的 dict 结构」，
 * 不用索引签名（ArkTS 禁用），调用方 `JSON.parse(text) as MonthBookDict`。
 */

/** JSON 里可能出现的数值形态（手改过的存档什么都可能有）。 */
export type NumLike = number | string | boolean | null | undefined;

export interface DayEntryDict {
  day?: NumLike;
  status?: string | null;
  mark?: NumLike;
  overtime_hours?: NumLike;
  leave_hours?: NumLike;
}

export interface PayItemDict {
  name?: string | null;
  type?: string | null;
  amount?: NumLike;
}

export interface MonthBookDict {
  year?: NumLike;
  month?: NumLike;
  note?: string | null;
  days?: DayEntryDict[] | null;
  pay_items?: PayItemDict[] | null;
  social_base?: NumLike;
  fund_base?: NumLike;
  personal_social_rate?: NumLike;
  personal_fund_rate?: NumLike;
  company_social_rate?: NumLike;
  company_fund_rate?: NumLike;
  min_wage?: NumLike;
  parttime_min?: NumLike;
  agreed_work_days?: NumLike;
  hours_per_day?: NumLike;
  overtime_base?: NumLike;
  fixed_overtime_wage?: NumLike;
  workday_ot_hours?: NumLike;
  restday_ot_hours?: NumLike;
  holiday_ot_hours?: NumLike;
  big_disease?: NumLike;
  income_tax?: NumLike;
  income_tax_auto?: NumLike;
  locked?: NumLike;
}

// ====== 常量：考勤状态 / 工资项类型 ======

export const STATUS_LABELS: string[] = ['上班', '休息', '事假', '病假', '婚假', '丧假', '产假', '年假', '其他'];
export const MARK_LABELS: string[] = ['', '法定节假日', '其他视为提供正常劳动的天数'];

export const PAYITEM_WAGE = 'wage';
export const PAYITEM_SUBSIDY = 'subsidy';
export const PAYITEM_FIXED_ALLOW = 'fixed_allow';
export const PAYITEM_PERDAY_ALLOW = 'perday_allow';

export const PAYITEM_TYPE_KEYS: string[] = [
  PAYITEM_WAGE, PAYITEM_SUBSIDY, PAYITEM_FIXED_ALLOW, PAYITEM_PERDAY_ALLOW
];

export const PAYITEM_TYPE_NAMES: Map<string, string> = new Map<string, string>([
  [PAYITEM_WAGE, '计入最低工资标准的工资'],
  [PAYITEM_SUBSIDY, '公司补贴'],
  [PAYITEM_FIXED_ALLOW, '固定津贴'],
  [PAYITEM_PERDAY_ALLOW, '按出勤津贴'],
]);

export const PAYITEM_DEFAULT_NAME: Map<string, string> = new Map<string, string>([
  [PAYITEM_WAGE, '基本工资'],
  [PAYITEM_SUBSIDY, '竞业限制补偿'],
  [PAYITEM_FIXED_ALLOW, '一次性奖励'],
  [PAYITEM_PERDAY_ALLOW, '伙食补贴'],
]);

// ====== 安全转换（手改存档容错，口径照抄 Python 的 _safe_float/_safe_int/_safe_bool）======

/** 等价于 Python `float(v)`，失败返回 null（对应 `_safe_float(v, None)`）。 */
function toFloatOpt(v: NumLike): number | null {
  if (typeof v === 'number') {
    return v;
  }
  if (typeof v === 'boolean') {
    return v ? 1 : 0;
  }
  if (typeof v === 'string') {
    const t: string = v.trim();
    if (t === '') {
      return null;
    }
    // Python 的 float() 接受 inf / nan / 数字下划线
    if (/^[+-]?(inf|infinity)$/i.test(t)) {
      return t.charAt(0) === '-' ? -Infinity : Infinity;
    }
    if (/^[+-]?nan$/i.test(t)) {
      return NaN;
    }
    if (!/^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/.test(t.replace(/_/g, ''))) {
      return null;
    }
    const n: number = Number(t.replace(/_/g, ''));
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

/** 等价于 Python `round(float(v), 6)` 的解析部分：失败返回 default。 */
export function safeFloat(v: NumLike, def: number): number {
  const n: number | null = toFloatOpt(v);
  return n === null ? def : n;
}

/** 等价于 `_safe_int`：bool 不算数，字符串 "3.9" → 3（向零截断）。 */
export function safeInt(v: NumLike, def: number): number {
  if (typeof v === 'boolean') {
    return def;
  }
  const n: number | null = toFloatOpt(v);
  if (n === null || !isFinite(n)) {
    return def;
  }
  return Math.trunc(n);
}

/** 等价于 `_safe_bool`：字符串 "false" 必须判成 false（不能用 Python 的 bool() 思路）。 */
export function safeBool(v: NumLike, def: boolean): boolean {
  if (typeof v === 'boolean') {
    return v;
  }
  if (typeof v === 'number') {
    return v !== 0 && !Number.isNaN(v);
  }
  if (typeof v === 'string') {
    const t: string = v.trim().toLowerCase();
    if (t === 'true' || t === '1' || t === 'yes' || t === 'y' || t === '是') {
      return true;
    }
    if (t === 'false' || t === '0' || t === 'no' || t === 'n' || t === '' || t === '否') {
      return false;
    }
  }
  return def;
}

function applyFloat(cur: number, raw: NumLike): number {
  if (raw === null || raw === undefined) {
    return cur;
  }
  if (typeof raw === 'string' && raw.trim() === '') {
    return cur;
  }
  const n: number | null = toFloatOpt(raw);
  return n === null ? cur : n;
}

// ====== PayItem ======

export class PayItem {
  name: string = '基本工资';
  type: string = PAYITEM_WAGE;
  amount: number = 0;

  constructor(name: string = '基本工资', type: string = PAYITEM_WAGE, amount: number = 0) {
    this.name = name;
    this.type = type;
    this.amount = amount;
  }

  /** 是否为「每日标准 × 上班天数」。 */
  isPerDay(): boolean {
    return this.type === PAYITEM_PERDAY_ALLOW;
  }

  toDict(): PayItemDict {
    return { name: this.name, type: this.type, amount: this.amount };
  }

  static fromDict(raw: PayItemDict): PayItem {
    let t: string = typeof raw.type === 'string' && raw.type !== '' ? raw.type : PAYITEM_WAGE;
    if (PAYITEM_TYPE_KEYS.indexOf(t) < 0) {
      t = PAYITEM_WAGE;
    }
    const defName: string = PAYITEM_DEFAULT_NAME.get(t) ?? '工资项';
    const name: string = typeof raw.name === 'string' && raw.name !== '' ? raw.name : defName;
    return new PayItem(name, t, safeFloat(raw.amount, 0));
  }
}

// ====== DayEntry ======

/** 公历（proleptic Gregorian）自 1970-01-01 起的天数，供星期计算用。 */
function daysFromCivil(y: number, m: number, d: number): number {
  const yy: number = m <= 2 ? y - 1 : y;
  const era: number = Math.floor(yy / 400);
  const yoe: number = yy - era * 400;
  const doy: number = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe: number = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

/** 星期几：0=周一 … 6=周日（与 Python `date.weekday()` 同口径）。 */
export function weekdayIndex(year: number, month: number, day: number): number {
  const days: number = daysFromCivil(year, month, day);
  return ((days + 3) % 7 + 7) % 7; // 1970-01-01 是周四
}

export class DayEntry {
  day: number = 1;
  status: string = '';
  mark: number = 0;
  overtime_hours: number = 0;
  leave_hours: number = 0;

  constructor(day: number = 1) {
    this.day = day;
  }

  /**
   *return weekdayIndex(year, month, this.day)休表**（补班的周六在这里仍算「周末」）。
   *   要按调休判断当天类型，请用 `holidays.dayKind()`。
   */
  isWeekendDt(year: number, month: number): boolean {
    const days: number = daysFromCivil(year, month, this.day);
    const weekday: number = ((days + 3) % 7 + 7) % 7; // 1970-01-01 是周四（周一=0）
    return weekday >= 5;
  }
}

// ====== 月份天数 ======

export function daysInMonth(year: number, month: number): number {
  const y: number = Math.trunc(year);
  const m: number = Math.trunc(month);
  if (!isFinite(y) || !isFinite(m) || m < 1 || m > 12) {
    return 0;
  }
  const leap: boolean = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  const table: number[] = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return table[m - 1];
}

// ====== MonthBook ======

export class MonthBook {
  // —— 基本信息 ——
  year: number = 0;
  month: number = 0;
  note: string = '';
  days: DayEntry[] = [];

  // —— 参数 ——
  social_base: number = 0;
  fund_base: number = 0;
  personal_social_rate: number = 0;
  personal_fund_rate: number = 0;
  company_social_rate: number = 0;
  company_fund_rate: number = 0;
  min_wage: number = 2170;
  parttime_min: number = 22;
  agreed_work_days: number = 26;
  hours_per_day: number = 8;
  overtime_base: number = 0;

  // —— 加班 / 个税 / 个人扣项 ——
  fixed_overtime_wage: number = 0;
  workday_ot_hours: number = 0;
  restday_ot_hours: number = 0;
  holiday_ot_hours: number = 0;
  big_disease: number = 0;
  income_tax: number = 0;
  income_tax_auto: boolean = false;

  // —— 月份状态 ——
  locked: boolean = false;

  // —— 工资项 ——
  pay_items: PayItem[] = [];

  get n_days(): number {
    return daysInMonth(this.year, this.month);
  }

  /** 按号取考勤日；缺号返回占位对象（不会写回 days）。 */
  day(dayNum: number): DayEntry {
    for (const d of this.days) {
      if (d.day === dayNum) {
        return d;
      }
    }
    return new DayEntry(dayNum);
  }

  toDict(): MonthBookDict {
    const out: MonthBookDict = {
      year: this.year,
      month: this.month,
      note: this.note,
      days: this.days.map((x: DayEntry): DayEntryDict => ({
        day: x.day,
        status: x.status,
        mark: x.mark,
        overtime_hours: x.overtime_hours,
        leave_hours: x.leave_hours,
      })),
      pay_items: this.pay_items.map((x: PayItem): PayItemDict => x.toDict()),
      social_base: this.social_base,
      fund_base: this.fund_base,
      personal_social_rate: this.personal_social_rate,
      personal_fund_rate: this.personal_fund_rate,
      company_social_rate: this.company_social_rate,
      company_fund_rate: this.company_fund_rate,
      min_wage: this.min_wage,
      parttime_min: this.parttime_min,
      agreed_work_days: this.agreed_work_days,
      hours_per_day: this.hours_per_day,
      overtime_base: this.overtime_base,
      fixed_overtime_wage: this.fixed_overtime_wage,
      workday_ot_hours: this.workday_ot_hours,
      restday_ot_hours: this.restday_ot_hours,
      holiday_ot_hours: this.holiday_ot_hours,
      big_disease: this.big_disease,
      income_tax: this.income_tax,
      income_tax_auto: this.income_tax_auto,
      locked: this.locked,
    };
    return out;
  }

  /** 反序列化：非法 / 缺失的字段一律保持默认值（口径见 model.py 的 from_dict）。 */
  static fromDict(raw: MonthBookDict): MonthBook {
    const b: MonthBook = new MonthBook();

    b.year = safeInt(raw.year, b.year);
    b.month = safeInt(raw.month, b.month);
    if (typeof raw.note === 'string') {
      b.note = raw.note;
    }

    b.social_base = applyFloat(b.social_base, raw.social_base);
    b.fund_base = applyFloat(b.fund_base, raw.fund_base);
    b.personal_social_rate = applyFloat(b.personal_social_rate, raw.personal_social_rate);
    b.personal_fund_rate = applyFloat(b.personal_fund_rate, raw.personal_fund_rate);
    b.company_social_rate = applyFloat(b.company_social_rate, raw.company_social_rate);
    b.company_fund_rate = applyFloat(b.company_fund_rate, raw.company_fund_rate);
    b.min_wage = applyFloat(b.min_wage, raw.min_wage);
    b.parttime_min = applyFloat(b.parttime_min, raw.parttime_min);
    b.agreed_work_days = applyFloat(b.agreed_work_days, raw.agreed_work_days);
    b.hours_per_day = applyFloat(b.hours_per_day, raw.hours_per_day);
    b.overtime_base = applyFloat(b.overtime_base, raw.overtime_base);
    b.fixed_overtime_wage = applyFloat(b.fixed_overtime_wage, raw.fixed_overtime_wage);
    b.workday_ot_hours = applyFloat(b.workday_ot_hours, raw.workday_ot_hours);
    b.restday_ot_hours = applyFloat(b.restday_ot_hours, raw.restday_ot_hours);
    b.holiday_ot_hours = applyFloat(b.holiday_ot_hours, raw.holiday_ot_hours);
    b.big_disease = applyFloat(b.big_disease, raw.big_disease);
    b.income_tax = applyFloat(b.income_tax, raw.income_tax);
    b.income_tax_auto = safeBool(raw.income_tax_auto, b.income_tax_auto);
    b.locked = safeBool(raw.locked, b.locked);

    const items: PayItemDict[] | null | undefined = raw.pay_items;
    if (Array.isArray(items)) {
      b.pay_items = items.filter((x: PayItemDict): boolean => typeof x === 'object' && x !== null)
        .map((x: PayItemDict): PayItem => PayItem.fromDict(x));
    } else {
      b.pay_items = [];
    }

    // 天数：按 n_days 补全；year/month 非法时 n_days=0，days 留空
    const n: number = b.n_days;
    const existing: Map<number, DayEntry> = new Map<number, DayEntry>();
    const rawDays: DayEntryDict[] | null | undefined = raw.days;
    if (Array.isArray(rawDays)) {
      for (const x of rawDays) {
        if (typeof x !== 'object' || x === null) {
          continue;
        }
        const dNum: number = safeInt(x.day, 0);
        if (dNum <= 0 || (n > 0 && dNum > n)) {
          continue;
        }
        const ent: DayEntry = new DayEntry(dNum);
        ent.status = typeof x.status === 'string' ? x.status : '';
        ent.mark = safeInt(x.mark, 0);
        ent.overtime_hours = safeFloat(x.overtime_hours, 0);
        ent.leave_hours = safeFloat(x.leave_hours, 0);
        existing.set(dNum, ent);
      }
    }
    b.days = [];
    for (let d = 1; d <= n; d++) {
      b.days.push(existing.get(d) ?? new DayEntry(d));
    }
    return b;
  }
}

/** 创建空账本并预填当月所有天（对应 `model.create_book`）。 */
export function createBook(year: number, month: number, note: string = '',
                           withCommonPayItems: boolean = false): MonthBook {
  const b: MonthBook = new MonthBook();
  b.year = year;
  b.month = month;
  b.note = note;
  const n: number = daysInMonth(year, month);
  b.days = [];
  for (let d = 1; d <= n; d++) {
    b.days.push(new DayEntry(d));
  }
  if (withCommonPayItems) {
    b.pay_items = buildCommonPayItems();
  }
  return b;
}

/** 常用工资项模板（金额 0）。 */
export function buildCommonPayItems(): PayItem[] {
  const out: PayItem[] = [];
  const groups: string[][] = [
    ['基本工资', '岗位工资', '绩效工资', '奖金', '工龄工资', '全勤奖'],
  ];
  for (const g of groups) {
    for (const n of g) {
      out.push(new PayItem(n, PAYITEM_WAGE, 0));
    }
  }
  for (const n of ['伙食补贴', '交通补贴', '通讯补贴', '高温津贴']) {
    out.push(new PayItem(n, PAYITEM_PERDAY_ALLOW, 0));
  }
  out.push(new PayItem('一次性奖励', PAYITEM_FIXED_ALLOW, 0));
  return out;
}
