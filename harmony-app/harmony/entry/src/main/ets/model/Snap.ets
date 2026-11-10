/**
 * 界面用的「快照」：模型 → 纯数据 → 只给界面读。
 *
 * 为什么要这一层（踩过的坑）：
 * ArkUI 的局部刷新只跟踪 `@State` 的赋值。`MonthBook` 是我们自己的纯 TS 类（不是
 * `@Observed`），直接让界面读 `this.book.xxx` 的话，改了模型不会重绘；
 * `ForEach` 还会按 key 缓存旧组件，表现为「点状态没反应 / 换月不刷新」。
 *
 * 约定：任何改动都是「改模型 → 重新 `Snap.from()` → 整体赋值给 `@State snap`」，
 * 界面只读 snap，不再碰 book。
 */

import { compute, MAX_DAILY_OVERTIME_H, MAX_MONTHLY_OVERTIME_HOURS, MAX_MONTHLY_WORK_DAYS, MAX_MONTHLY_WORK_HOURS, Result } from '../core/calc';
import { DayEntry, MonthBook, weekdayIndex } from '../core/model';
import { pyFixed, pyGeneral, pyGroupedFixed, pyGroupedInt } from '../core/num';

function pad2(n: number): string {
  return (n < 10 ? '0' : '') + n.toString();
}

/** 日历一格（纯数据）。 */
export class CalCell {
  day: number = 0;
  status: string = '';
  mark: number = 0;
  /** 周末（用于未填时的粉红虚线框） */
  weekend: boolean = false;
  /** 格子第二行：`上班 · 法定节` 或 `未填` */
  midText: string = '未填';
  /** 格子第三行：`+2h  -1h` */
  hoursText: string = '';
}

/** 日历顶部统计 chip（桌面版 9 个）。 */
export class CalStat {
  label: string = '';
  value: string = '';

  constructor(label: string, value: string) {
    this.label = label;
    this.value = value;
  }
}

/** 报表一行（已格式化）。 */
export class RecLine {
  label: string = '';
  value: string = '';
  /** n 普通 / i 灰字 / ok 合规 / bad 违规 / sec 组内小标题 */
  kind: string = 'n';
  bold: boolean = false;
}

/** 报表一组。 */
export class RecGroup {
  title: string = '';
  lines: RecLine[] = [];
}

/** 相关单位一行（已格式化）。
 *  ⚠ 必须是 @ObservedV2：ForEach 对相同 key 的项不会重新求值，
 *  只有 @Trace 属性变化才会通知界面（否则改了名字界面还显示旧值）。 */
@ObservedV2
export class UnitRow {
  index: number = 0;
  role: string = 'contract';
  roleLabel: string = '';
  codeLabel: string = '';
  @Trace name: string = '';
  @Trace code: string = '';
}

/** 年度汇总一行。 */
/** 年度汇总的一行（对应桌面版 _COLS 的 10 列）。 */
export class AnnualRow {
  month: number = 1;
  hasData: boolean = false;
  /** 合计行 */
  isTotal: boolean = false;
  workText: string = '—';
  otText: string = '—';
  leaveText: string = '—';
  gross: string = '—';
  deduct: string = '—';
  leaveDeduct: string = '—';
  takeHome: string = '—';
  companyCost: string = '—';
  legal: boolean = true;
}

/** 工资项一行（已格式化）。 */
export class PayRow {
  index: number = 0;
  name: string = '';
  type: string = 'wage';
  amountText: string = '0';
  subText: string = '0.00';
}

export class Snap {
  // ── 顶栏 strip ──
  gross: string = '0.00';
  inWage: string = '0.00';
  outWage: string = '0.00';
  takeHome: string = '0.00';

  // ── 工作台 KPI ──
  workDays: number = 0;
  monthlyHours: string = '0.0';
  otHours: string = '0.0';
  minWageOk: boolean = false;
  workTimeLegal: boolean = false;
  minWageText: string = '';
  workTimeText: string = '';

  // ── 报表 ──
  groups: RecGroup[] = [];
  deductTotal: string = '0.00';
  leaveDeductionTotal: string = '0.00';

  // ── 薪酬页 ──
  payRows: PayRow[] = [];
  payTotal: string = '0.00';
  otHoursWorkday: string = '0';
  otHoursRestday: string = '0';
  otHoursHoliday: string = '0';
  otWageWorkday: string = '0.00';
  otWageRestday: string = '0.00';
  otWageHoliday: string = '0.00';
  otSubtotal: string = '0.00';
  otHourlyText: string = '0.00';
  fixedOt: string = '0';
  otBaseText: string = '0';
  personalSocialText: string = '0.00';
  personalFundText: string = '0.00';
  /** 带公式的显示文：`¥447.84（0.105 × 4,200）`（桌面版同款） */
  personalSocialDetail: string = '';
  personalFundDetail: string = '';
  bigDisease: string = '0';
  incomeTax: string = '0.00';
  incomeTaxAuto: boolean = false;
  companyHourlyCost: string = '0.00';
  takeHomeHourly: string = '0.00';
  /** 工作台：公司总成本 / 提供正常劳动 / 加班·请假 / 两项合规详情 */
  companyCost: string = '0.00';
  normalLaborText: string = '0 天';
  otLeaveText: string = '0.0h / 0.0h';
  minWageDetail: string = '';
  workTimeDetail: string = '';
  parttimeMinText: string = '0.00';
  hasHourlyCost: boolean = false;
  issues: string[] = [];

  // ── 考勤日历 ──
  year: number = 0;
  month: number = 0;
  selDay: number = 1;
  selSubtitle: string = '';
  selStatus: string = '';
  selMark: number = 0;
  weeks: CalCell[][] = [];
  workCount: number = 0;
  restCount: number = 0;
  leaveCount: number = 0;
  calStats: CalStat[] = [];

  static from(book: MonthBook, selDay: number): Snap {
    const r: Result = compute(book);
    const s: Snap = new Snap();

    s.gross = pyGroupedFixed(r.gross_wage, 2);
    s.inWage = pyGroupedFixed(r.in_wage_part, 2);
    s.outWage = pyGroupedFixed(r.not_in_wage_part, 2);
    s.takeHome = pyGroupedFixed(r.take_home, 2);
    s.workDays = r.counts.work;
    s.monthlyHours = pyGroupedFixed(r.monthly_work_hours, 1);
    s.otHours = pyFixed(r.total_daily_ot_hours, 1);
    s.minWageOk = r.min_wage_ok;
    s.workTimeLegal = r.work_time_legal;
    s.minWageText = r.min_wage_status;
    s.workTimeText = r.work_time_legality;
    s.companyHourlyCost = pyGroupedFixed(r.company_hourly_cost, 2);
    s.takeHomeHourly = pyGroupedFixed(r.take_home_hourly, 2);
    s.hasHourlyCost = r.company_hourly_cost > 0;
    s.companyCost = pyGroupedFixed(r.gross_wage + r.company_social + r.company_fund, 2);
    s.normalLaborText = `${r.counts.normal_labor_days} 天`;
    s.otLeaveText = `${pyGroupedFixed(r.total_daily_ot_hours, 1)}h / ${pyGroupedFixed(r.daily_leave_hours, 1)}h`;
    s.parttimeMinText = pyGroupedFixed(book.parttime_min, 2);
    const cmp: string = r.min_wage_ok ? '≥' : '<';
    s.minWageDetail = `¥ ${pyGroupedFixed(r.wage_components_total, 2)} ${cmp} `
      + `¥ ${pyGroupedFixed(book.min_wage, 2)}（月最低工资）`;
    const wt: string[] = [];
    wt.push(`月工时 ${pyGroupedFixed(r.monthly_work_hours, 1)}h/${pyGeneral(MAX_MONTHLY_WORK_HOURS)}h`);
    wt.push(`月加班 ${pyGroupedFixed(r.total_daily_ot_hours, 1)}h/${pyGeneral(MAX_MONTHLY_OVERTIME_HOURS)}h`);
    wt.push(`上班 ${r.counts.work} 天/${MAX_MONTHLY_WORK_DAYS} 天`);
    if (r.daily_ot_over3_days > 0) {
      wt.push(`${r.daily_ot_over3_days} 天单日加班>${pyGeneral(MAX_DAILY_OVERTIME_H)}h`);
    } else {
      wt.push(`单日加班≤${pyGeneral(MAX_DAILY_OVERTIME_H)}h`);
    }
    s.workTimeDetail = wt.join(' · ');
    s.issues = r.work_time_issues;

    s.year = book.year;
    s.month = book.month;
    s.selDay = selDay;
    s.weeks = Snap.buildWeeks(book);
    s.workCount = r.counts.work;
    s.restCount = r.counts.rest;
    s.leaveCount = r.counts.personal_leave + r.counts.sick_leave + r.counts.marriage_leave
      + r.counts.bereavement_leave + r.counts.maternity_leave + r.counts.annual_leave
      + r.counts.other;
    const fam: number = r.counts.marriage_leave + r.counts.bereavement_leave
      + r.counts.maternity_leave + r.counts.annual_leave;
    s.calStats = [
      new CalStat('上班', `${r.counts.work}`),
      new CalStat('休息', `${r.counts.rest}`),
      new CalStat('事假', `${r.counts.personal_leave}`),
      new CalStat('病假', `${r.counts.sick_leave}`),
      new CalStat('婚/丧/产/年假', `${fam}`),
      new CalStat('法定节假日', `${r.counts.legal_holiday}`),
      new CalStat('提供正常劳动', `${r.counts.normal_labor_days}`),
      new CalStat('加班', `${pyGroupedFixed(r.total_daily_ot_hours, 1)}h`),
      new CalStat('请假', `${pyGroupedFixed(r.daily_leave_hours, 1)}h`)
    ];

    const ent: DayEntry = book.day(selDay);
    s.selStatus = ent.status;
    s.selMark = ent.mark;
    s.selSubtitle = Snap.buildSubtitle(book, selDay, ent.mark);

    s.groups = Snap.buildReport(r);
    s.deductTotal = pyGroupedFixed(r.personal_deductions_total, 2);
    s.leaveDeductionTotal = pyGroupedFixed(r.leave_deduction_total, 2);

    s.payRows = Snap.buildPayRows(book, r.counts.work);
    s.payTotal = pyGroupedFixed(r.wage_components_total + r.company_subsidies_included
      + r.fixed_allowances_total + r.perday_allowances_total, 2);
    s.otHoursWorkday = book.workday_ot_hours.toString();
    s.otHoursRestday = book.restday_ot_hours.toString();
    s.otHoursHoliday = book.holiday_ot_hours.toString();
    s.otWageWorkday = pyGroupedFixed(r.overtime_wage_workday, 2);
    s.otWageRestday = pyGroupedFixed(r.overtime_wage_restday, 2);
    s.otWageHoliday = pyGroupedFixed(r.overtime_wage_holiday, 2);
    s.otSubtotal = pyGroupedFixed(r.overtime_wage_total + book.fixed_overtime_wage, 2);
    s.otHourlyText = pyGroupedFixed(r.overtime_hourly_wage, 2);
    s.fixedOt = book.fixed_overtime_wage.toString();
    s.otBaseText = book.overtime_base.toString();
    s.personalSocialText = pyGroupedFixed(r.personal_social, 2);
    s.personalFundText = pyGroupedFixed(r.personal_fund, 2);
    s.personalSocialDetail = `${pyGroupedFixed(r.personal_social, 2)}（${book.personal_social_rate} × ${pyGroupedInt(book.social_base)}）`;
    s.personalFundDetail = `${pyGroupedFixed(r.personal_fund, 2)}（${book.personal_fund_rate} × ${pyGroupedInt(book.fund_base)}）`;
    s.bigDisease = book.big_disease.toString();
    s.incomeTax = pyGroupedFixed(r.income_tax, 2);
    s.incomeTaxAuto = book.income_tax_auto;
    return s;
  }

  /** 工资项行（小计：按月固定 = 金额；按出勤 = 金额 × 上班天数）。 */
  private static buildPayRows(book: MonthBook, workDays: number): PayRow[] {
    const out: PayRow[] = [];
    let i: number = 0;
    for (const it of book.pay_items) {
      const row: PayRow = new PayRow();
      row.index = i;
      row.name = it.name;
      row.type = it.type;
      row.amountText = it.amount.toString();
      row.subText = pyGroupedFixed(it.type === 'perday_allow' ? it.amount * workDays : it.amount, 2);
      out.push(row);
      i = i + 1;
    }
    return out;
  }

  /** 报表分组：数值格式化口径与桌面版 `pages_report._fmt_line` 一致。 */
  private static buildReport(r: Result): RecGroup[] {
    const out: RecGroup[] = [];
    for (const g of r.groups) {
      const rg: RecGroup = new RecGroup();
      rg.title = g.title;
      for (const ln of g.lines) {
        const rl: RecLine = new RecLine();
        rl.label = ln.label;
        rl.kind = ln.kind;
        rl.bold = ln.bold;
        if (ln.text !== null) {
          rl.value = ln.text;
        } else if (ln.value === null) {
          rl.value = '';
        } else {
          rl.value = Snap.fmtValue(ln.value, ln.unit);
        }
        rg.lines.push(rl);
      }
      out.push(rg);
    }
    return out;
  }

  private static fmtValue(v: number, unit: string): string {
    let s: string;
    if (unit === '元') {
      // 金额一律两位小数（与桌面版 f"{v:,.2f}" 一致）
      s = pyGroupedFixed(v, 2);
    } else if (Number.isInteger(v)) {
      s = v.toString();
    } else {
      s = pyFixed(v, 2);
      if (s.indexOf('.') >= 0) {
        while (s.charAt(s.length - 1) === '0') {
          s = s.substring(0, s.length - 1);
        }
        if (s.charAt(s.length - 1) === '.') {
          s = s.substring(0, s.length - 1);
        }
      }
    }
    return unit.length > 0 ? `${s} ${unit}` : s;
  }

  /** 按周切格（周一~周日），月初补空位（day=0）。 */
  private static buildWeeks(book: MonthBook): CalCell[][] {
    const first: number = weekdayIndex(book.year, book.month, 1);
    const flat: CalCell[] = [];
    for (let i = 0; i < first; i++) {
      flat.push(new CalCell());
    }
    for (let d = 1; d <= book.n_days; d++) {
      const c: CalCell = new CalCell();
      c.day = d;
      const ent: DayEntry = book.day(d);
      c.status = ent.status;
      c.mark = ent.mark;
      c.weekend = ent.isWeekendDt(book.year, book.month);
      const mid: string[] = [];
      if (ent.status.length > 0) {
        mid.push(ent.status);
      }
      if (ent.mark === 1) {
        mid.push('法定节');
      } else if (ent.mark === 2) {
        mid.push('计劳动');
      }
      c.midText = mid.length > 0 ? mid.join(' · ') : '未填';
      const hd: string[] = [];
      if (ent.overtime_hours !== 0) {
        hd.push(`+${pyGeneral(ent.overtime_hours)}h`);
      }
      if (ent.leave_hours !== 0) {
        hd.push(`-${pyGeneral(ent.leave_hours)}h`);
      }
      c.hoursText = hd.join('  ');
      flat.push(c);
    }
    while (flat.length % 7 !== 0) {
      flat.push(new CalCell());
    }
    const out: CalCell[][] = [];
    for (let i = 0; i < flat.length; i += 7) {
      out.push(flat.slice(i, i + 7));
    }
    return out;
  }

  private static buildSubtitle(book: MonthBook, day: number, mark: number): string {
    const names: string[] = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    const idx: number = weekdayIndex(book.year, book.month, day);
    let s: string = `${book.year}-${pad2(book.month)}-${pad2(day)} · ${names[idx]}`;
    if (idx >= 5) {
      s = s + '（周末）';
    }
    if (mark === 1) {
      s = s + ' · 法定节假日';
    } else if (mark === 2) {
      s = s + ' · 视为提供正常劳动';
    }
    return s;
  }
}
