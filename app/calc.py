"""计算引擎：工资考勤核算公式（加班费/社保公积金/请假扣款/合规判定）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from . import model

PAYABLE_DAYS = 21.75  # 月计薪天数（国家规定，固定值不可改）

# ====== 工时与加班合规阈值 ======
# 法定标准：每日加班不超过 3 小时（《劳动法》第 41 条）；
#           每月工作时长上限 220 小时（含标准工时 + 加班）；
#           每月加班小时不超过 36 小时；每月上班天数不超过 26 天。
MAX_DAILY_OVERTIME_H = 3.0
MAX_MONTHLY_WORK_HOURS = 220.0
MAX_MONTHLY_OVERTIME_HOURS = 36.0
MAX_MONTHLY_WORK_DAYS = 26


def _f(v: float) -> float:
    """只保留 6 位精度的纯数处理。小时数、天数、比例等非金额字段用此函数。"""
    return round(float(v or 0.0), 6)


def _round2(v: float) -> float:
    """四舍五入保留 2 位小数。

    用 Decimal + ROUND_HALF_UP，避免浮点 + Python 内置 round() 的
    「银行家舍入」误差（如 443.835 因 IEEE 754 实际表示为 443.83499...
    在 round-half-to-even 下变成 443.83 而不是 443.84）。
    所有金额字段（包括派生单价如加班时薪、请假每日扣）均使用此函数，
    保证存储值与 UI 显示 (:,.2f) 完全一致。
    """
    return float(Decimal(str(v or 0.0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class Counts:
    work: int = 0
    rest: int = 0
    personal_leave: int = 0
    sick_leave: int = 0
    marriage_leave: int = 0
    bereavement_leave: int = 0
    maternity_leave: int = 0
    annual_leave: int = 0
    other: int = 0
    weekend: int = 0
    legal_holiday: int = 0
    provided_normal_labor: int = 0
    normal_labor_days: int = 0          # B15
    diff_agreed_normal_labor: float = 0.0  # B16


@dataclass
class Result:
    counts: Counts = field(default_factory=Counts)
    # 工时
    total_daily_ot_hours: float = 0.0      # B46
    monthly_work_hours: float = 0.0        # B47
    daily_leave_hours: float = 0.0         # SUM(D7:AH7)
    # 工资链
    wage_components_total: float = 0.0     # B34
    perday_allowances_total: float = 0.0   # SUM(D12:AH12)
    fixed_allowances_total: float = 0.0    # SUM(D15:AH15)
    overtime_wage_total: float = 0.0
    overtime_wage_workday: float = 0.0
    overtime_wage_restday: float = 0.0
    overtime_wage_holiday: float = 0.0
    # 实际参与计算的加班小时（手动或按逐日自动汇总）
    ot_hours_workday: float = 0.0
    ot_hours_restday: float = 0.0
    ot_hours_holiday: float = 0.0
    company_subsidies_included: float = 0.0
    in_wage_part: float = 0.0              # B24
    not_in_wage_part: float = 0.0          # B25
    gross_wage: float = 0.0                # B23
    # 个人扣除
    personal_social: float = 0.0           # D23
    big_disease: float = 0.0               # E23
    personal_fund: float = 0.0             # F23
    income_tax: float = 0.0                # G23
    personal_deductions_total: float = 0.0
    after_deduction: float = 0.0           # B26
    # 公司承担
    company_social: float = 0.0            # D26
    company_fund: float = 0.0              # F26
    # 请假扣款
    leave_deduction_days: float = 0.0      # B28
    leave_deduction_hours: float = 0.0     # B29
    leave_deduction_total: float = 0.0     # B27
    leave_per_day: float = 0.0             # B31
    leave_per_hour: float = 0.0            # B32
    # 加班
    overtime_daily_wage: float = 0.0       # B20
    overtime_hourly_wage: float = 0.0      # B21
    # 实发
    take_home: float = 0.0                 # B37
    take_home_hourly: float = 0.0          # B38
    company_hourly_cost: float = 0.0       # B40
    # 合规
    min_wage_status: str = ""
    work_time_legality: str = ""
    company_cost_status: str = ""
    # 工时合规明细（违法时 UI / 报表可以逐条展示）
    work_time_issues: list = field(default_factory=list)  # [str,...]
    daily_ot_over3_days: int = 0                            # 单日加班超 3h 的天数
    groups: list = field(default_factory=list)


# 个税月度预扣率表：(级距上限, 税率, 速算扣除数)
_TAX_BRACKETS = [(3000, 0.03, 0.0), (12000, 0.10, 210.0), (25000, 0.20, 1410.0),
                 (35000, 0.25, 2660.0), (55000, 0.30, 4410.0), (80000, 0.35, 7160.0)]


def _monthly_tax(taxable: float) -> float:
    """按月度税率表计算个税（简化单月预扣，不含专项附加扣除）。"""
    if taxable <= 0:
        return 0.0
    for cap, rate, deduct in _TAX_BRACKETS:
        if taxable <= cap:
            return max(0.0, taxable * rate - deduct)
    return max(0.0, taxable * 0.45 - 15160.0)


def compute(book: model.MonthBook) -> Result:
    s = book
    counts = _count_attendance(book)
    r = Result(counts=counts)

    # 工时 + 加班分类：合并为单次遍历（原为 4 次独立遍历 book.days）
    total_ot = 0.0
    total_leave = 0.0
    over3_days: list[int] = []           # 单日加班 > 3h 的日号列表（留着算明细）
    wd = rd = hd = 0.0  # 加班小时分类：工作日/休息日/法定节假日
    ot_auto = bool(s.ot_auto)
    for d in book.days:
        h = float(d.overtime_hours or 0.0)
        total_ot += h
        total_leave += float(d.leave_hours or 0.0)
        if h > MAX_DAILY_OVERTIME_H:
            over3_days.append(d.day)
        if ot_auto and h > 0:
            if d.mark == 1:
                hd += h
            elif d.is_weekend_dt(book.year, book.month):
                rd += h
            else:
                wd += h
    r.total_daily_ot_hours = _f(total_ot)
    r.daily_leave_hours = _f(total_leave)
    r.monthly_work_hours = _f(counts.work * s.hours_per_day + r.total_daily_ot_hours)
    r.daily_ot_over3_days = len(over3_days)

    # 工资项分类（按 PayItem.type 归并）
    pi_wages, pi_subsidies, pi_fixed, pi_perday = _pay_item_totals(book)
    r.wage_components_total = _round2(pi_wages)
    r.company_subsidies_included = _round2(pi_subsidies)
    r.fixed_allowances_total = _round2(pi_fixed)
    r.perday_allowances_total = _round2(pi_perday * counts.work)

    # 加班
    payable8 = PAYABLE_DAYS * 8.0
    r.overtime_hourly_wage = _round2(s.overtime_base / payable8 if payable8 else 0.0)
    r.overtime_daily_wage = _round2(s.overtime_base / PAYABLE_DAYS)
    if ot_auto:
        r.ot_hours_workday, r.ot_hours_restday, r.ot_hours_holiday = _f(wd), _f(rd), _f(hd)
    else:
        r.ot_hours_workday = _f(s.workday_ot_hours)
        r.ot_hours_restday = _f(s.restday_ot_hours)
        r.ot_hours_holiday = _f(s.holiday_ot_hours)
    r.overtime_wage_workday = _round2(1.5 * r.ot_hours_workday * r.overtime_hourly_wage)
    r.overtime_wage_restday = _round2(2.0 * r.ot_hours_restday * r.overtime_hourly_wage)
    r.overtime_wage_holiday = _round2(3.0 * r.ot_hours_holiday * r.overtime_hourly_wage)
    r.overtime_wage_total = _round2(r.overtime_wage_workday + r.overtime_wage_restday + r.overtime_wage_holiday)

    # 计入最低工资标准的：仅 wage 类型工资项（不含加班工资、不含公司补贴/津贴）
    r.in_wage_part = _round2(r.wage_components_total)
    # 不计入最低工资标准的：津贴、补贴、各类加班工资
    r.not_in_wage_part = _round2(r.perday_allowances_total + r.fixed_allowances_total
                                 + r.company_subsidies_included + s.fixed_overtime_wage
                                 + r.overtime_wage_total)
    r.gross_wage = _round2(r.in_wage_part + r.not_in_wage_part)

    # 个人扣除
    r.personal_social = _round2(s.personal_social_rate * s.social_base)
    r.big_disease = _round2(s.big_disease)
    r.personal_fund = _round2(s.personal_fund_rate * s.fund_base)
    taxable = r.gross_wage - 5000.0 - r.personal_social - r.personal_fund  # 个税计税基数（5000 元起征）
    r.income_tax = _round2(_monthly_tax(taxable) if s.income_tax_auto else s.income_tax)
    r.personal_deductions_total = _round2(r.personal_social + r.big_disease + r.personal_fund + r.income_tax)
    r.after_deduction = _round2(r.gross_wage - r.personal_deductions_total)

    # 公司承担
    r.company_social = _round2(s.company_social_rate * s.social_base)
    r.company_fund = _round2(s.company_fund_rate * s.fund_base)

    # 请假扣款
    agreed = s.agreed_work_days or 1.0
    r.leave_per_day = _round2(r.after_deduction / agreed if agreed else 0.0)
    r.leave_per_hour = _round2(r.after_deduction / agreed / 8.0 if agreed else 0.0)
    r.leave_deduction_days = _round2(counts.diff_agreed_normal_labor * r.leave_per_day
                                     if counts.diff_agreed_normal_labor > 0 else 0.0)
    r.leave_deduction_hours = _round2(r.daily_leave_hours * r.leave_per_hour)
    r.leave_deduction_total = _round2(r.leave_deduction_days + r.leave_deduction_hours)

    # 实发
    r.take_home = _round2(r.after_deduction - r.leave_deduction_total)
    r.take_home_hourly = _round2((r.after_deduction - r.leave_deduction_total) / r.monthly_work_hours
                                  if r.after_deduction > 0 and r.monthly_work_hours > 0 else 0.0)
    r.company_hourly_cost = _round2((r.gross_wage + (r.company_social + r.company_fund))
                                    / (counts.normal_labor_days * s.hours_per_day)
                                    if counts.normal_labor_days > 0 else 0.0)

    # 合规
    r.min_wage_status = "不低于月最低工资标准" if r.wage_components_total >= s.min_wage else "低于月最低工资标准"

    # 工时与加班合规：分别检查 4 条维度，任一命中 → 违法 + 写入 issues 明细
    issues: list[str] = []
    if r.monthly_work_hours > MAX_MONTHLY_WORK_HOURS:
        issues.append(f"月工时 {r.monthly_work_hours:,.1f}h > {MAX_MONTHLY_WORK_HOURS:g}h 上限")
    if r.total_daily_ot_hours > MAX_MONTHLY_OVERTIME_HOURS:
        issues.append(
            f"月加班总时长 {r.total_daily_ot_hours:,.1f}h > {MAX_MONTHLY_OVERTIME_HOURS:g}h 上限")
    if counts.work > MAX_MONTHLY_WORK_DAYS:
        issues.append(f"实际上班天数 {counts.work} 天 > {MAX_MONTHLY_WORK_DAYS} 天上限")
    if over3_days:
        # 单日加班 > 3h 违法（《劳动法》第 41 条）
        days_label = ",".join(str(d) for d in over3_days)
        if len(over3_days) > 6:
            days_label = ",".join(str(d) for d in over3_days[:6]) + f"…共 {len(over3_days)} 天"
        issues.append(f"单日加班超过 {MAX_DAILY_OVERTIME_H:g}h 的日期：{days_label} 号")
    r.work_time_issues = issues
    r.work_time_legality = "违法" if issues else "不违法"

    r.company_cost_status = ("大于非全日制小时最低工资标准"
                             if r.company_hourly_cost >= s.parttime_min
                             else "小于非全日制小时最低工资标准")

    r.groups = _build_groups(book, r)
    return r


def _pay_item_totals(book: model.MonthBook) -> tuple[float, float, float, float]:
    """按 PayItem.type 归并：工资构成 / 公司补贴 / 固定津贴 / 按出勤标准合计。"""
    wages = subsidies = fixed_allow = perday = 0.0
    for it in book.pay_items:
        amt = float(it.amount or 0.0)
        if it.type == "wage":
            wages += amt
        elif it.type == "subsidy":
            subsidies += amt
        elif it.type == "fixed_allow":
            fixed_allow += amt
        elif it.type == "perday_allow":
            perday += amt
    return wages, subsidies, fixed_allow, perday


# 考勤状态 → Counts 计数字段
_STATUS_COUNT_FIELDS = {
    "上班": "work", "休息": "rest", "事假": "personal_leave",
    "病假": "sick_leave", "婚假": "marriage_leave", "丧假": "bereavement_leave",
    "产假": "maternity_leave", "年假": "annual_leave", "其他": "other",
}


def _count_attendance(book: model.MonthBook) -> Counts:
    c = Counts()
    mapping = _STATUS_COUNT_FIELDS
    for d in book.days:
        f = mapping.get(d.status)
        if f is not None:
            setattr(c, f, getattr(c, f) + 1)
        if d.mark == 1:
            c.legal_holiday += 1
        elif d.mark == 2:
            c.provided_normal_labor += 1
        if d.is_weekend_dt(book.year, book.month):
            c.weekend += 1
    c.normal_labor_days = (c.work + c.marriage_leave + c.bereavement_leave
                           + c.maternity_leave + c.annual_leave
                           + c.legal_holiday + c.provided_normal_labor)
    c.diff_agreed_normal_labor = _f(book.agreed_work_days - c.normal_labor_days)
    return c


def _line(label: str, *, value: float | None = None, unit: str = "元",
          text: str | None = None, kind: str = "n", bold: bool = False) -> dict:
    return {"label": label, "value": value, "unit": unit, "text": text,
            "kind": kind, "bold": bold}


def _build_groups(book: model.MonthBook, r: Result) -> list:
    c = r.counts
    g = []

    g.append({"title": "出勤统计（天）", "lines": [
        _line("上班", value=c.work, unit="天"),
        _line("休息", value=c.rest, unit="天"),
        _line("事假", value=c.personal_leave, unit="天"),
        _line("病假", value=c.sick_leave, unit="天"),
        _line("婚假", value=c.marriage_leave, unit="天"),
        _line("丧假", value=c.bereavement_leave, unit="天"),
        _line("产假", value=c.maternity_leave, unit="天"),
        _line("年假", value=c.annual_leave, unit="天"),
        _line("其他", value=c.other, unit="天"),
        _line("周末", value=c.weekend, unit="天", kind="i"),
        _line("法定节假日", value=c.legal_holiday, unit="天", kind="i"),
        _line("其他视为提供正常劳动", value=c.provided_normal_labor, unit="天", kind="i"),
    ]})

    g.append({"title": "工时核算", "lines": [
        _line("约定工作天数", value=book.agreed_work_days, unit="天", kind="i"),
        _line("提供正常劳动天数", value=c.normal_labor_days, unit="天", bold=True),
        _line("缺勤天数（约定 − 实出勤）", value=c.diff_agreed_normal_labor, unit="天"),
        _line("工作日加班时长", value=r.ot_hours_workday, unit="小时"),
        _line("休息日加班时长", value=r.ot_hours_restday, unit="小时"),
        _line("法定节假日加班时长", value=r.ot_hours_holiday, unit="小时"),
        _line("月加班总时长", value=r.total_daily_ot_hours, unit="小时"),
        _line("月工作总时长", value=r.monthly_work_hours, unit="小时", bold=True),
    ]})

    g.append({"title": "工资核算（应发）", "lines": [
        _line("津贴合计（按出勤天数）", value=r.perday_allowances_total),
        _line("固定津贴/一次性奖励合计", value=r.fixed_allowances_total),
        _line("工作日加班工资", value=r.overtime_wage_workday),
        _line("休息日加班工资", value=r.overtime_wage_restday),
        _line("法定节假日加班工资", value=r.overtime_wage_holiday),
        _line("固定加班工资", value=book.fixed_overtime_wage),
        _line("计入最低工资标准的工资", value=r.in_wage_part),
        _line("不计入最低工资标准的工资", value=r.not_in_wage_part),
        _line("应发工资合计", value=r.gross_wage, bold=True),
    ]})

    g.append({"title": "个人扣除", "lines": [
        _line("个人社保", value=r.personal_social),
        _line("大病医疗补助", value=r.big_disease),
        _line("个人公积金", value=r.personal_fund),
        _line("个人所得税", value=r.income_tax),
        _line("扣除合计", value=r.personal_deductions_total, bold=True),
        _line("应发扣除个人项目后", value=r.after_deduction, bold=True),
    ]})

    g.append({"title": "请假扣款", "lines": [
        _line("请假每天扣", value=r.leave_per_day, kind="i"),
        _line("请假每小时扣", value=r.leave_per_hour, kind="i"),
        _line("缺勤天数扣款", value=r.leave_deduction_days),
        _line("请假小时扣款", value=r.leave_deduction_hours),
        _line("请假扣款小计", value=r.leave_deduction_total, bold=True),
    ]})

    g.append({"title": "实发结果", "lines": [
        _line("实际到手工资", value=r.take_home, bold=True),
        _line("到手小时工资", value=r.take_home_hourly),
        _line("公司社保", value=r.company_social, kind="i"),
        _line("公司公积金", value=r.company_fund, kind="i"),
        _line("公司每小时成本", value=r.company_hourly_cost, kind="i"),
    ]})

    g.append({"title": "合规判定", "lines": [
        _line("计入最低工资标准的工资与月最低工资标准比较", text=r.min_wage_status,
              kind="ok" if "不低于" in r.min_wage_status else "bad"),
        _line("工作时间是否违法", text=r.work_time_legality,
              kind="ok" if "不违法" in r.work_time_legality else "bad"),
    ] + [
        _line(f"  · {issue}", kind="bad") for issue in r.work_time_issues
    ] + ([
        _line("  · 判定标准：月工时≤220h / 加班≤36h / 上班≤26天 / 单日加班≤3h", kind="i")
    ] if not r.work_time_issues else []) + [
        # 公司雇佣成本比较为参考信息，不作为合规判定的强制依据
        _line("公司雇佣成本与小时最低工资比较（仅参考）", text=r.company_cost_status, kind="i"),
    ]})
    return g
