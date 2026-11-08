/**
 * 计算引擎（对应桌面版 `app/calc.py`）：工资考勤核算公式。
 *
 * 口径与规整规则（与桌面版逐条一致，改之前先读桌面版注释）：
 *  * 金额字段一律过 `pyRound2`（Decimal(str) + HALF_UP），中间步骤也规整；
 *  * 非金额字段过 `pyRound6`（= Python round(v, 6)）；
 *  * 月计薪天数固定 21.75；加班时薪 = 基数 ÷ (21.75 × 8)；
 *  * 三档加班小时取账本上的**手填值**，逐日 `overtime_hours` 只汇总成
 *    「月加班总时长」用于合规判定；
 *  * 约定工作天数 ≤ 0 时不折算日薪/时薪（宁可少扣不错扣）。
 *
 * `compute` 是**纯函数**：只读 book，不修改入参。
 */

import { MonthBook, PAYITEM_FIXED_ALLOW, PAYITEM_PERDAY_ALLOW, PAYITEM_SUBSIDY, PAYITEM_WAGE } from './model';
import { pyFixed, pyGeneral, pyGroupedFixed, pyRound2, pyRound6 } from './num';
import { OT_RATE_HOLIDAY, OT_RATE_RESTDAY, OT_RATE_WORKDAY } from './config';

/** 月计薪天数（国家规定，固定值不可改）。 */
export const PAYABLE_DAYS: number = 21.75;

// ====== 工时与加班合规阈值 ======
export const MAX_DAILY_OVERTIME_H: number = 3;
export const MAX_MONTHLY_WORK_HOURS: number = 220;
export const MAX_MONTHLY_OVERTIME_HOURS: number = 36;
export const MAX_MONTHLY_WORK_DAYS: number = 26;

/** 「判定标准」文案；数字全取自上面的常量（与报表 / Excel 共用一份）。 */
export function complianceStandardText(): string {
  return `月工时≤${pyGeneral(MAX_MONTHLY_WORK_HOURS)}h / 月加班≤${pyGeneral(MAX_MONTHLY_OVERTIME_HOURS)}h / `
    + `上班≤${pyGeneral(MAX_MONTHLY_WORK_DAYS)}天 / 单日加班≤${pyGeneral(MAX_DAILY_OVERTIME_H)}h`;
}

/** 三档加班倍率文案（如「工作日加班×1.5 · 休息日×2.0 · 法定节假日×3.0」）。 */
export function overtimeRateText(): string {
  return `工作日加班×${pyFixed(OT_RATE_WORKDAY, 1)} · `
    + `休息日×${pyFixed(OT_RATE_RESTDAY, 1)} · `
    + `法定节假日×${pyFixed(OT_RATE_HOLIDAY, 1)}`;
}

/** 加班时薪折算方式提示（如「时薪 = 加班费基数 ÷（21.75 × 8 = 174 小时）」）。 */
export function overtimeHourlyTip(): string {
  return `时薪 = 加班费基数 ÷（${pyGeneral(PAYABLE_DAYS)} × 8 = ${pyGeneral(PAYABLE_DAYS * 8)} 小时）`;
}

// ====== 出勤统计 ======

export class Counts {
  work: number = 0;
  rest: number = 0;
  personal_leave: number = 0;
  sick_leave: number = 0;
  marriage_leave: number = 0;
  bereavement_leave: number = 0;
  maternity_leave: number = 0;
  annual_leave: number = 0;
  other: number = 0;
  weekend: number = 0;
  legal_holiday: number = 0;
  provided_normal_labor: number = 0;
  normal_labor_days: number = 0;
  diff_agreed_normal_labor: number = 0;
}

export class ReportLine {
  label: string = '';
  value: number | null = null;
  unit: string = '元';
  text: string | null = null;
  /** n 普通 / i 只读灰字 / ok 合规 / bad 违规 / sec 组内小标题 */
  kind: string = 'n';
  bold: boolean = false;

  constructor(label: string, value: number | null = null, unit: string = '元',
              text: string | null = null, kind: string = 'n', bold: boolean = false) {
    this.label = label;
    this.value = value;
    this.unit = unit;
    this.text = text;
    this.kind = kind;
    this.bold = bold;
  }
}

export class ReportGroup {
  title: string = '';
  lines: ReportLine[] = [];

  constructor(title: string, lines: ReportLine[]) {
    this.title = title;
    this.lines = lines;
  }
}

export class Result {
  counts: Counts = new Counts();
  // 工时
  total_daily_ot_hours: number = 0;
  monthly_work_hours: number = 0;
  daily_leave_hours: number = 0;
  // 工资链
  wage_components_total: number = 0;
  perday_allowances_total: number = 0;
  fixed_allowances_total: number = 0;
  overtime_wage_total: number = 0;
  overtime_wage_workday: number = 0;
  overtime_wage_restday: number = 0;
  overtime_wage_holiday: number = 0;
  ot_hours_workday: number = 0;
  ot_hours_restday: number = 0;
  ot_hours_holiday: number = 0;
  company_subsidies_included: number = 0;
  in_wage_part: number = 0;
  not_in_wage_part: number = 0;
  deduct_part_in: number = 0;
  deduct_part_out: number = 0;
  gross_wage: number = 0;
  // 个人扣除
  personal_social: number = 0;
  big_disease: number = 0;
  personal_fund: number = 0;
  income_tax: number = 0;
  personal_deductions_total: number = 0;
  after_deduction: number = 0;
  // 公司承担
  company_social: number = 0;
  company_fund: number = 0;
  // 请假扣款
  leave_deduction_days: number = 0;
  leave_deduction_hours: number = 0;
  leave_deduction_total: number = 0;
  leave_per_day: number = 0;
  leave_per_hour: number = 0;
  // 加班折算单价
  overtime_daily_wage: number = 0;
  overtime_hourly_wage: number = 0;
  // 实发
  take_home: number = 0;
  take_home_hourly: number = 0;
  company_hourly_cost: number = 0;
  // 合规结论（文案）
  min_wage_status: string = '';
  work_time_legality: string = '';
  company_cost_status: string = '';
  // 判定结果本身（颜色 / 图标 / 徽章一律读这两个布尔）
  min_wage_ok: boolean = false;
  work_time_legal: boolean = false;
  work_time_issues: string[] = [];
  daily_ot_over3_days: number = 0;
  groups: ReportGroup[] = [];
}

/** 个税月度预扣率表：(级距上限, 税率, 速算扣除数)。 */
const TAX_BRACKETS: number[][] = [
  [3000, 0.03, 0],
  [12000, 0.10, 210],
  [25000, 0.20, 1410],
  [35000, 0.25, 2660],
  [55000, 0.30, 4410],
  [80000, 0.35, 7160],
];

/** 按月度税率表计算个税（简化单月预扣，不含专项附加扣除）。 */
function monthlyTax(taxable: number): number {
  if (taxable <= 0) {
    return 0;
  }
  for (const b of TAX_BRACKETS) {
    if (taxable <= b[0]) {
      return Math.max(0, taxable * b[1] - b[2]);
    }
  }
  return Math.max(0, taxable * 0.45 - 15160);
}

// ====== 主入口 ======

export function compute(book: MonthBook): Result {
  const counts: Counts = countAttendance(book);
  const r: Result = new Result();
  r.counts = counts;

  // 工时 + 加班分类：单次遍历
  let totalOt: number = 0;
  let totalLeave: number = 0;
  const over3Days: number[] = [];
  for (const d of book.days) {
    const h: number = d.overtime_hours;
    totalOt += h;
    totalLeave += d.leave_hours;
    if (h > MAX_DAILY_OVERTIME_H) {
      over3Days.push(d.day);
    }
  }
  r.total_daily_ot_hours = pyRound6(totalOt);
  r.daily_leave_hours = pyRound6(totalLeave);
  r.monthly_work_hours = pyRound6(counts.work * book.hours_per_day + r.total_daily_ot_hours);
  r.daily_ot_over3_days = over3Days.length;

  // 工资项分类
  const totals: number[] = payItemTotals(book);
  const piWages: number = totals[0];
  const piSubsidies: number = totals[1];
  const piFixed: number = totals[2];
  const piPerday: number = totals[3];
  r.wage_components_total = pyRound2(piWages);
  r.company_subsidies_included = pyRound2(piSubsidies);
  r.fixed_allowances_total = pyRound2(piFixed);
  r.perday_allowances_total = pyRound2(piPerday * counts.work);

  // 加班
  const payable8: number = PAYABLE_DAYS * 8;
  r.overtime_hourly_wage = pyRound2(payable8 !== 0 ? book.overtime_base / payable8 : 0);
  r.overtime_daily_wage = pyRound2(book.overtime_base / PAYABLE_DAYS);
  r.ot_hours_workday = pyRound6(book.workday_ot_hours);
  r.ot_hours_restday = pyRound6(book.restday_ot_hours);
  r.ot_hours_holiday = pyRound6(book.holiday_ot_hours);
  r.overtime_wage_workday = pyRound2(OT_RATE_WORKDAY * r.ot_hours_workday * r.overtime_hourly_wage);
  r.overtime_wage_restday = pyRound2(OT_RATE_RESTDAY * r.ot_hours_restday * r.overtime_hourly_wage);
  r.overtime_wage_holiday = pyRound2(OT_RATE_HOLIDAY * r.ot_hours_holiday * r.overtime_hourly_wage);
  r.overtime_wage_total = pyRound2(r.overtime_wage_workday + r.overtime_wage_restday
    + r.overtime_wage_holiday);

  // 计入 / 不计入最低工资标准
  r.in_wage_part = pyRound2(r.wage_components_total);
  r.not_in_wage_part = pyRound2(r.perday_allowances_total + r.fixed_allowances_total
    + r.company_subsidies_included + book.fixed_overtime_wage
    + r.overtime_wage_total);
  r.gross_wage = pyRound2(r.in_wage_part + r.not_in_wage_part);

  // 计入 / 不计入工资扣除部分（Excel B24/B25）
  r.deduct_part_in = pyRound2(r.in_wage_part + r.company_subsidies_included
    + book.fixed_overtime_wage);
  r.deduct_part_out = pyRound2(r.not_in_wage_part - r.company_subsidies_included
    - book.fixed_overtime_wage);

  // 个人扣除
  r.personal_social = pyRound2(book.personal_social_rate * book.social_base);
  r.big_disease = pyRound2(book.big_disease);
  r.personal_fund = pyRound2(book.personal_fund_rate * book.fund_base);
  const taxable: number = r.gross_wage - 5000 - r.personal_social - r.personal_fund;
  r.income_tax = pyRound2(book.income_tax_auto ? monthlyTax(taxable) : book.income_tax);
  r.personal_deductions_total = pyRound2(r.personal_social + r.big_disease
    + r.personal_fund + r.income_tax);
  r.after_deduction = pyRound2(r.gross_wage - r.personal_deductions_total);

  // 公司承担
  r.company_social = pyRound2(book.company_social_rate * book.social_base);
  r.company_fund = pyRound2(book.company_fund_rate * book.fund_base);

  // 请假扣款（约定工作天数 ≤ 0 时不做任何折算）
  const agreed: number = pyRound6(book.agreed_work_days);
  if (agreed > 0) {
    r.leave_per_day = pyRound2(r.after_deduction / agreed);
    r.leave_per_hour = pyRound2(r.after_deduction / agreed / 8);
  } else {
    r.leave_per_day = 0;
    r.leave_per_hour = 0;
  }
  r.leave_deduction_days = pyRound2(counts.diff_agreed_normal_labor > 0
    ? counts.diff_agreed_normal_labor * r.leave_per_day : 0);
  r.leave_deduction_hours = pyRound2(r.daily_leave_hours * r.leave_per_hour);
  r.leave_deduction_total = pyRound2(r.leave_deduction_days + r.leave_deduction_hours);

  // 实发
  r.take_home = pyRound2(r.after_deduction - r.leave_deduction_total);
  r.take_home_hourly = pyRound2(
    (r.after_deduction > 0 && r.monthly_work_hours > 0)
      ? (r.after_deduction - r.leave_deduction_total) / r.monthly_work_hours
      : 0);
  // 公司每小时成本：分母 = 提供正常劳动天数 × 每日工时（两个因子都可能为 0）
  const costHours: number = counts.normal_labor_days * book.hours_per_day;
  r.company_hourly_cost = pyRound2(costHours > 0
    ? (r.gross_wage + (r.company_social + r.company_fund)) / costHours : 0);

  // 合规
  r.min_wage_ok = r.wage_components_total >= book.min_wage;
  r.min_wage_status = r.min_wage_ok ? '不低于月最低工资标准' : '低于月最低工资标准';

  const issues: string[] = [];
  if (r.monthly_work_hours > MAX_MONTHLY_WORK_HOURS) {
    issues.push(`月工时 ${pyGroupedFixed(r.monthly_work_hours, 1)}h > ${pyGeneral(MAX_MONTHLY_WORK_HOURS)}h 上限`);
  }
  if (r.total_daily_ot_hours > MAX_MONTHLY_OVERTIME_HOURS) {
    issues.push(`月加班总时长 ${pyGroupedFixed(r.total_daily_ot_hours, 1)}h > `
      + `${pyGeneral(MAX_MONTHLY_OVERTIME_HOURS)}h 上限`);
  }
  if (counts.work > MAX_MONTHLY_WORK_DAYS) {
    issues.push(`实际上班天数 ${counts.work} 天 > ${MAX_MONTHLY_WORK_DAYS} 天上限`);
  }
  if (over3Days.length > 0) {
    const shown: number[] = over3Days.length > 6 ? over3Days.slice(0, 6) : over3Days;
    let label: string = shown.map((d: number): string => d.toString()).join(',');
    if (over3Days.length > 6) {
      label = label + `…共 ${over3Days.length} 天`;
    }
    issues.push(`单日加班超过 ${pyGeneral(MAX_DAILY_OVERTIME_H)}h 的日期：${label} 号`);
  }
  r.work_time_issues = issues;
  r.work_time_legal = issues.length === 0;
  r.work_time_legality = r.work_time_legal ? '不违法' : '违法';

  r.company_cost_status = r.company_hourly_cost >= book.parttime_min
    ? '大于非全日制小时最低工资标准' : '小于非全日制小时最低工资标准';

  r.groups = buildGroups(book, r);
  return r;
}

/** 按 PayItem.type 归并：工资构成 / 公司补贴 / 固定津贴 / 按出勤标准合计。 */
function payItemTotals(book: MonthBook): number[] {
  let wages: number = 0;
  let subsidies: number = 0;
  let fixedAllow: number = 0;
  let perday: number = 0;
  for (const it of book.pay_items) {
    const amt: number = it.amount;
    if (it.type === PAYITEM_WAGE) {
      wages += amt;
    } else if (it.type === PAYITEM_SUBSIDY) {
      subsidies += amt;
    } else if (it.type === PAYITEM_FIXED_ALLOW) {
      fixedAllow += amt;
    } else if (it.type === PAYITEM_PERDAY_ALLOW) {
      perday += amt;
    }
  }
  return [wages, subsidies, fixedAllow, perday];
}

/** 考勤状态 → Counts 计数字段（对应 Python 的 _STATUS_COUNT_FIELDS）。 */
const STATUS_COUNT_FIELDS: Map<string, string> = new Map<string, string>([
  ['上班', 'work'], ['休息', 'rest'], ['事假', 'personal_leave'],
  ['病假', 'sick_leave'], ['婚假', 'marriage_leave'], ['丧假', 'bereavement_leave'],
  ['产假', 'maternity_leave'], ['年假', 'annual_leave'], ['其他', 'other'],
]);

function bump(c: Counts, field: string): void {
  if (field === 'work') {
    c.work++;
  } else if (field === 'rest') {
    c.rest++;
  } else if (field === 'personal_leave') {
    c.personal_leave++;
  } else if (field === 'sick_leave') {
    c.sick_leave++;
  } else if (field === 'marriage_leave') {
    c.marriage_leave++;
  } else if (field === 'bereavement_leave') {
    c.bereavement_leave++;
  } else if (field === 'maternity_leave') {
    c.maternity_leave++;
  } else if (field === 'annual_leave') {
    c.annual_leave++;
  } else if (field === 'other') {
    c.other++;
  }
}

/**
 * 按考勤状态 / 标记汇总天数（对应 Excel 的 B15 / B16 口径）。
 *
 * * `normal_labor_days`（提供正常劳动天数）= 上班 + 婚假 + 丧假 + 产假 + 年假
 *   + 法定节假日 + 其他视为提供正常劳动
 * * `diff_agreed_normal_labor` = 约定工作天数 − 提供正常劳动天数，**不 clamp**
 */
export function countAttendance(book: MonthBook): Counts {
  const c: Counts = new Counts();
  for (const d of book.days) {
    const field: string | undefined = STATUS_COUNT_FIELDS.get(d.status);
    if (field !== undefined) {
      bump(c, field);
    }
    if (d.mark === 1) {
      c.legal_holiday++;
    } else if (d.mark === 2) {
      c.provided_normal_labor++;
    }
    if (d.isWeekendDt(book.year, book.month)) {
      c.weekend++;
    }
  }
  c.normal_labor_days = c.work + c.marriage_leave + c.bereavement_leave
    + c.maternity_leave + c.annual_leave + c.legal_holiday + c.provided_normal_labor;
  c.diff_agreed_normal_labor = pyRound6(book.agreed_work_days - c.normal_labor_days);
  return c;
}

function line(label: string, value: number | null = null, unit: string = '元',
              text: string | null = null, kind: string = 'n', bold: boolean = false): ReportLine {
  return new ReportLine(label, value, unit, text, kind, bold);
}

/** 把核算结果整理成报表分组（报表页与导出共用）。 */
function buildGroups(book: MonthBook, r: Result): ReportGroup[] {
  const c: Counts = r.counts;
  const g: ReportGroup[] = [];

  g.push(new ReportGroup('出勤统计（天）', [
    line('上班', c.work, '天'),
    line('休息', c.rest, '天'),
    line('事假', c.personal_leave, '天'),
    line('病假', c.sick_leave, '天'),
    line('婚假', c.marriage_leave, '天'),
    line('丧假', c.bereavement_leave, '天'),
    line('产假', c.maternity_leave, '天'),
    line('年假', c.annual_leave, '天'),
    line('其他', c.other, '天'),
    line('周末', c.weekend, '天', null, 'i'),
    line('法定节假日', c.legal_holiday, '天', null, 'i'),
    line('其他视为提供正常劳动', c.provided_normal_labor, '天', null, 'i'),
  ]));

  g.push(new ReportGroup('工时核算', [
    line('月计薪天数', PAYABLE_DAYS, '天', null, 'i'),
    line('约定工作天数', book.agreed_work_days, '天', null, 'i'),
    line('提供正常劳动天数', c.normal_labor_days, '天', null, 'n', true),
    line('缺勤天数（约定工作天数 − 提供正常劳动天数）', c.diff_agreed_normal_labor, '天'),
    line('工作日加班时长', r.ot_hours_workday, '小时'),
    line('休息日加班时长', r.ot_hours_restday, '小时'),
    line('法定节假日加班时长', r.ot_hours_holiday, '小时'),
    line('月加班总时长', r.total_daily_ot_hours, '小时'),
    line('月工作总时长', r.monthly_work_hours, '小时', null, 'n', true),
  ]));

  // 应发分组：工资构成 → 加班工资 → 两种口径拆分 → 合计（用灰字小标题分段）
  const otWageSubtotal: number = pyRound2(r.overtime_wage_total + book.fixed_overtime_wage);
  // 「非加班工资合计」用「应发 − 加班合计」反推（不是分项相加），保证恒等、不差 1 分
  const baseWageSubtotal: number = pyRound2(r.gross_wage - otWageSubtotal);
  g.push(new ReportGroup('工资核算（应发）', [
    line('工资构成', null, '元', null, 'sec'),
    line('基本工资项合计（工资类）', r.wage_components_total),
    line('津贴合计（按出勤天数）', r.perday_allowances_total),
    line('固定津贴/一次性奖励合计', r.fixed_allowances_total),
    line('公司补贴', r.company_subsidies_included),
    line('非加班工资合计', baseWageSubtotal, '元', null, 'n', true),
    line('加班工资', null, '元', null, 'sec'),
    line('加班费计算基数', book.overtime_base, '元', null, 'i'),
    line('加班费计算的日工资', r.overtime_daily_wage, '元', null, 'i'),
    line('加班费计算的小时工资', r.overtime_hourly_wage, '元', null, 'i'),
    line('工作日加班工资', r.overtime_wage_workday),
    line('休息日加班工资', r.overtime_wage_restday),
    line('法定节假日加班工资', r.overtime_wage_holiday),
    line('固定加班工资', book.fixed_overtime_wage),
    line('加班工资合计', otWageSubtotal, '元', null, 'n', true),
    line('两种口径拆分（仅对照，两组相加都等于应发工资）', null, '元', null, 'sec'),
    line('计入最低工资标准的工资', r.in_wage_part),
    line('不计入最低工资标准的工资', r.not_in_wage_part),
    line('计入工资扣除部分', r.deduct_part_in),
    line('不计入工资扣除部分/已经扣除部分', r.deduct_part_out),
    line('应发工资合计', r.gross_wage, '元', null, 'n', true),
  ]));

  g.push(new ReportGroup('个人扣除', [
    line('个人社保', r.personal_social),
    line('大病医疗补助', r.big_disease),
    line('个人公积金', r.personal_fund),
    line('个人所得税', r.income_tax),
    line('扣除合计', r.personal_deductions_total, '元', null, 'n', true),
    line('应发扣除个人项目后', r.after_deduction, '元', null, 'n', true),
  ]));

  g.push(new ReportGroup('请假扣款', [
    line('请假一天扣除的工资', r.leave_per_day, '元', null, 'i'),
    line('请假一个小时扣除的工资', r.leave_per_hour, '元', null, 'i'),
    line('请假扣的天工资', r.leave_deduction_days),
    line('请假扣的小时工资', r.leave_deduction_hours),
    line('请假扣的总工资', r.leave_deduction_total, '元', null, 'n', true),
  ]));

  g.push(new ReportGroup('实发结果', [
    line('实际到手工资', r.take_home, '元', null, 'n', true),
    line('到手小时工资', r.take_home_hourly),
    line('公司社保', r.company_social, '元', null, 'i'),
    line('公司公积金', r.company_fund, '元', null, 'i'),
    line('公司每小时成本', r.company_hourly_cost, '元', null, 'i'),
  ]));

  const complianceLines: ReportLine[] = [
    line('计入最低工资标准的工资与月最低工资标准比较', null, '元',
      r.min_wage_status, r.min_wage_ok ? 'ok' : 'bad'),
    line('工作时间是否违法', null, '元', r.work_time_legality,
      r.work_time_legal ? 'ok' : 'bad'),
  ];
  for (const issue of r.work_time_issues) {
    complianceLines.push(line(`  · ${issue}`, null, '元', null, 'bad'));
  }
  if (r.work_time_issues.length === 0) {
    complianceLines.push(line(`  · 判定标准：${complianceStandardText()}`, null, '元', null, 'i'));
  }
  complianceLines.push(line('公司雇佣成本与小时最低工资比较（仅参考）', null, '元',
    r.company_cost_status, 'i'));
  g.push(new ReportGroup('合规判定', complianceLines));

  return g;
}
