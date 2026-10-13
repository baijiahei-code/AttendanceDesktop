"""工资考勤数据模型（月度账本 / 每日考勤 / 工资项）。"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field, fields
from datetime import date

# ====== 常量：考勤状态 / 工资项类型 ======

STATUS_LABELS = ["上班", "休息", "事假", "病假", "婚假", "丧假", "产假", "年假", "其他"]
# 视为「提供正常劳动」的状态（Excel B15 口径）。⚠ 改这里必须同步
# calc._count_attendance 的字段汇总，否则合规天数与报表会不一致。
# 注：本集合目前无代码引用，保留作为业务规则的显式声明。
NORMAL_LABOR_STATUSES = {"上班", "婚假", "丧假", "产假", "年假"}
MARK_LABELS = ["", "法定节假日", "其他视为提供正常劳动的天数"]

# 工资项类型：内部 key → 显示名（只改显示名不改 key，向后兼容）
PAYITEM_TYPES = [
    ("wage", "计入最低工资标准的工资"),
    ("subsidy", "公司补贴"),
    ("fixed_allow", "固定津贴"),
    ("perday_allow", "按出勤津贴"),
]
PAYITEM_TYPE_NAMES = {t: n for t, n in PAYITEM_TYPES}
PAYITEM_TYPE_KEYS = frozenset(PAYITEM_TYPE_NAMES)
# 每类的详细说明（悬浮提示 / 向导用）
PAYITEM_TYPE_DESC = {
    "wage": "月固定 · 计入最低工资标准（参与最低工资判定）",
    "subsidy": "月固定 · 计入应发，不属最低工资标准",
    "fixed_allow": "月固定 · 不计入最低工资标准",
    "perday_allow": "每日标准 × 上班天数 · 不计入最低工资标准",
}
# 计入「最低工资」判定口径的工资项类型（实际汇总见 calc._pay_item_totals；
# 本集合目前无代码引用，保留作为业务规则的显式声明）
PAYITEM_COUNTS_IN_MIN = frozenset({"wage"})
# 新增一项时的默认名称
PAYITEM_DEFAULT_NAME = {
    "wage": "基本工资",
    "subsidy": "竞业限制补偿",
    "fixed_allow": "一次性奖励",
    "perday_allow": "伙食补贴",
}
# 每类「一键带入」常用模板（金额 0，用户再填）
PAYITEM_COMMON = {
    "wage": ["基本工资", "岗位工资", "绩效工资", "奖金", "工龄工资", "全勤奖"],
    "perday_allow": ["伙食补贴", "交通补贴", "通讯补贴", "高温津贴"],
    "fixed_allow": ["一次性奖励"],
    "subsidy": [],
}
# 「添加工资项」菜单的完整可选目录（按类型分组，常用项排在前面）。
PAYITEM_CATALOG = {
    "wage": [
        "基本工资", "岗位工资", "绩效工资", "奖金", "工龄工资", "全勤奖",
        "职级工资", "学历工资", "生活补贴", "技能津贴", "子女教育补贴",
    ],
    "subsidy": [
        "竞业限制补偿", "保密费", "公司社保补贴",
    ],
    "fixed_allow": [
        "一次性奖励", "官方社保补贴",
        "伙食补贴（固定）", "交通补贴（固定）", "通讯补贴（固定）", "住房补贴（固定）",
        "中班津贴（固定）", "夜班津贴（固定）", "高温津贴（固定）", "低温津贴（固定）",
        "井下津贴（固定）", "有毒有害津贴（固定）", "特殊环境津贴（固定）", "培训补贴（固定）",
    ],
    "perday_allow": [
        "伙食补贴", "交通补贴", "通讯补贴", "高温津贴",
        "住房补贴", "中班津贴", "夜班津贴", "低温津贴",
        "井下津贴", "有毒有害津贴", "特殊环境津贴", "培训补贴",
    ],
}


# ====== 相关单位：同一段劳动关系里可能涉及多家单位 ======
#
# 现实中「签合同的公司」「缴社保的公司」「发工资的公司」「实际干活的单位」
# 经常不是同一个（集团 / 分公司 / 劳务派遣 / 社保代缴 / 工资代发等），
# 分开登记便于核对，也便于判断工龄、社保连续性与责任主体。
#
# 每项 = (key, 显示名, 第二列占位文字, 说明)。key 一旦发布不要改（存档兼容）。
UNIT_ROLES = [
    ("contract", "劳动合同签订单位", "统一社会信用代码",
     "劳动合同上的用人单位（甲方）"),
    ("social", "社保缴纳单位", "统一社会信用代码",
     "实际缴纳社会保险的参保单位（代缴时可能与签订单位不同）"),
    ("fund", "公积金缴纳单位", "统一社会信用代码",
     "住房公积金缴存单位"),
    ("wage", "工资发放单位", "统一社会信用代码",
     "实际发放工资的主体（委托代发 / 由集团统一发放时不同于签订单位）"),
    ("tax", "个税扣缴单位", "统一社会信用代码",
     "个人所得税代扣代缴义务人"),
    ("work", "实际用工单位", "统一社会信用代码",
     "员工实际工作 / 被派驻的单位（如考勤与工资不在同一主体）"),
    ("dispatch", "劳务派遣单位", "统一社会信用代码",
     "派遣方（非劳务派遣时不用添加）"),
    ("outsourcing", "外包单位", "统一社会信用代码",
     "业务外包的承包方（非外包时不用添加）"),
    ("superior", "上级单位", "统一社会信用代码",
     "上级主管单位（选填）"),
    ("group", "集团单位", "统一社会信用代码",
     "母公司 / 集团总部（选填）"),
    ("bank", "工资代发银行", "联行号／账号",
     "代发工资的开户银行或支行（选填）"),
]
UNIT_ROLE_KEYS = [k for k, _, _, _ in UNIT_ROLES]
UNIT_ROLE_LABELS = {k: lab for k, lab, _, _ in UNIT_ROLES}
UNIT_ROLE_CODE_LABELS = {k: c for k, _, c, _ in UNIT_ROLES}
UNIT_ROLE_HINTS = {k: h for k, _, _, h in UNIT_ROLES}
UNIT_ROLE_DEFAULT = "contract"
# 工资代发银行：这一项的「编号」是联行号 / 账号，**不能**去企业信用查询站查，
# 所以页面把它那行的行尾按钮做成「复制」（见 pages_units）。
UNIT_ROLE_BANK = "bank"

# 「其他相关单位」= 非内置类型的落点：
# 用户的要求是「自定义内容填在**名称**栏」——
# 所以它**可选择**（在类型下拉里），但添加菜单里用「✏️ 自定义（填在名称栏）…」这个动作代替。
UNIT_ROLE_OTHER = "other"
# 类型下拉用（= 11 个内置类型 + 其他相关单位）
UNIT_SELECTABLE_KEYS = UNIT_ROLE_KEYS + [UNIT_ROLE_OTHER]
UNIT_ROLE_LABELS[UNIT_ROLE_OTHER] = "其他相关单位"
UNIT_ROLE_CODE_LABELS[UNIT_ROLE_OTHER] = "统一社会信用代码"
UNIT_ROLE_HINTS[UNIT_ROLE_OTHER] = "其它单位：具体是什么写在「单位名称」栏，例如「补充医疗保险公司」"


def resolve_unit_role(text: str) -> str:
    """把类型文字解析成类型 key（不认识的一律归 :data:`UNIT_ROLE_OTHER`）。

    供相关单位页的类型下拉（不可编辑）使用；纯函数，便于单测。
    """
    t = (text or "").strip()
    for key, lab in UNIT_ROLE_LABELS.items():
        if t == lab:
            return key
    return UNIT_ROLE_OTHER


@dataclass
class RelatedUnit:
    """一家「相关单位」：类型 + 名称 + 可选编号。

    * ``role``：类型 key（见 :data:`UNIT_ROLES`；不属于内置类型时用
      :data:`UNIT_ROLE_OTHER`「其他相关单位」）；
    * ``name``：单位名称。**自定义的具体内容也写在这里**（类型选「其他相关单位」，
      名称写「补充医疗保险公司」）；
    * ``code``：统一社会信用代码；工资代发银行一行填联行号 / 账号。
    """

    role: str = UNIT_ROLE_DEFAULT
    name: str = ""
    code: str = ""

    def type_name(self) -> str:
        """类型显示名（``other`` 即「其他相关单位」）。"""
        return UNIT_ROLE_LABELS.get(self.role, "") or UNIT_ROLE_LABELS[UNIT_ROLE_OTHER]

    def to_dict(self) -> dict:
        return {"role": self.role, "name": self.name, "code": self.code}

    @classmethod
    def from_dict(cls, raw: dict) -> "RelatedUnit":
        role = str(raw.get("role") or UNIT_ROLE_OTHER)
        if role not in UNIT_ROLE_LABELS:
            role = UNIT_ROLE_OTHER
        return cls(role=role,
                   name=str(raw.get("name") or "").strip(),
                   code=str(raw.get("code") or "").strip())


def default_units() -> list["RelatedUnit"]:
    """默认单位表：**内置类型各一行**（名称 / 编号留空，等用户填）。

    ⚠ **不含**「其他相关单位」—— 那是「列表里都没有」的落点，
    需要时在「＋ 添加单位」里选「✏️ 自定义（填在名称栏）…」添加。
    """
    return [RelatedUnit(role=k) for k in UNIT_ROLE_KEYS]


# ====== PayItem：一条工资项 ======

def _safe_float(v, default: float = 0.0) -> float:
    """把任意值转成 float，失败返回 default。"""
    try:
        return float(v)
    except Exception:
        return default


@dataclass
class PayItem:
    """一条工资项。
    type：PAYITEM_TYPES 中的 key；
    amount：月固定项为每月金额，按出勤项(perday_allow)为每日标准。"""

    name: str = "基本工资"
    type: str = "wage"
    amount: float = 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type, "amount": float(self.amount)}

    @classmethod
    def from_dict(cls, raw: dict) -> "PayItem":
        t = str(raw.get("type") or "wage")
        if t not in PAYITEM_TYPE_KEYS:
            t = "wage"
        default_name = PAYITEM_DEFAULT_NAME.get(t, "工资项")
        return cls(
            name=str(raw.get("name") or default_name),
            type=t,
            amount=_safe_float(raw.get("amount"), 0.0),
        )

    def is_per_day(self) -> bool:
        """是否为每日标准 × 上班天数 汇总。"""
        return self.type == "perday_allow"


def build_common_pay_items() -> list[PayItem]:
    """常用项模板（金额 0），供新建月份一键带入。"""
    return [
        PayItem(name=n, type=t, amount=0.0)
        for t, names in PAYITEM_COMMON.items()
        for n in names
    ]


# ====== DayEntry：每日考勤 ======


@dataclass
class DayEntry:
    day: int = 1
    status: str = ""              # 空=未填写；取值见 STATUS_LABELS
    mark: int = 0                 # 0=无  1=法定节假日  2=其他视为提供正常劳动
    overtime_hours: float = 0.0
    leave_hours: float = 0.0

    def is_weekend_dt(self, year: int, month: int) -> bool:
        """该日是否为自然周的周六 / 周日。

        ⚠ 只看自然周，**不查调休表**（调休补班的周六在此仍算「周末」）。
        唯一使用者是 `calc._count_attendance`（累计 `Counts.weekend`，仅用于报表展示）；
        三档加班小时由用户手填、不经过这里，故无需处理调休。
        """
        return date(year, month, self.day).weekday() >= 5


def days_in_month(year: int, month: int) -> int:
    """当月天数；year / month 非法（无法转 int 或 month 越界）时返回 0。"""
    try:
        y, m = int(year), int(month)
    except Exception:
        return 0
    if m < 1 or m > 12:
        return 0
    return calendar.monthrange(y, m)[1]


# ====== MonthBook：月度账本 ======

# days / pay_items 是对象列表，序列化单独处理（不走通用字段循环）
_MONTHBOOK_SKIP = frozenset({"days", "pay_items"})
_MONTHBOOK_FLOAT_FIELDS = None  # 首次计算缓存


def _float_fields() -> frozenset:
    """MonthBook 中「声明类型为 float」的字段名集合（排除 days / pay_items），首次调用后缓存。

    `from_dict()` 用它决定哪些字段需要走 `_safe_float` 解析（而不是直接 setattr）。
    """
    global _MONTHBOOK_FLOAT_FIELDS
    if _MONTHBOOK_FLOAT_FIELDS is None:
        fs = [f.name for f in fields(MonthBook)
              if f.type in (float, "float") and f.name not in _MONTHBOOK_SKIP]
        _MONTHBOOK_FLOAT_FIELDS = frozenset(fs)
    return _MONTHBOOK_FLOAT_FIELDS


def create_book(year: int, month: int, note: str = "", *, with_common_pay_items: bool = False) -> "MonthBook":
    """创建空账本并预填当月所有天。
    with_common_pay_items=True：同时带入常用工资项模板（金额 0），
        通常只有「从 UI 新建新月」才用，测试/反序列化请保持默认 False。"""
    b = MonthBook()
    b.year, b.month, b.note = year, month, note
    b.days = [DayEntry(day=d) for d in range(1, days_in_month(year, month) + 1)]
    if with_common_pay_items:
        b.pay_items = build_common_pay_items()
    return b


@dataclass
class MonthBook:
    # —— 基本信息 ——
    year: int = 0
    month: int = 0
    note: str = ""
    days: list[DayEntry] = field(default_factory=list)

    # —— 参数（五险一金 / 工时 / 最低工资 / 加班基数）——
    social_base: float = 0.0            # 社保缴费基数
    fund_base: float = 0.0              # 公积金缴费基数（默认跟随 min_wage，UI 锁控制）
    personal_social_rate: float = 0.0
    personal_fund_rate: float = 0.0
    company_social_rate: float = 0.0
    company_fund_rate: float = 0.0
    min_wage: float = 2170.0             # 本地最低工资标准（元/月）
    parttime_min: float = 22.0           # 非全日制最低工资标准（元/时）
    agreed_work_days: float = 26.0       # 约定工作天数（与员工约定，不影响计薪天数 21.75）
    hours_per_day: float = 8.0          # 24 小时内工时（第 N 次下班 → 第 N+1 次上班结束，正常周期=24h）
    overtime_base: float = 0.0           # 加班费计算基数（默认跟随 min_wage）

    # —— 加班 / 个税 / 个人扣项 ——
    fixed_overtime_wage: float = 0.0     # 固定加班工资（不按小时算的）
    # 三档加班小时：**由用户在薪酬页手工填写**（不按考勤自动推算）。
    workday_ot_hours: float = 0.0        # 工作日加班小时（×1.5）
    restday_ot_hours: float = 0.0        # 休息日加班小时（×2）
    holiday_ot_hours: float = 0.0        # 法定节假日加班小时（×3）
    big_disease: float = 0.0              # 大病医疗补助（元/月）
    income_tax: float = 0.0               # 手动覆盖个税；income_tax_auto=True 时忽略
    income_tax_auto: bool = False         # 个税自动按「当月预扣率表」算

    # —— 月份状态标记 ——
    locked: bool = False                  # 整月只读：UI 全面禁用 + 写入拦截（双保险）；
                                          # 仍可浏览、切月、导出 Excel，并可手动解锁

    # —— 工资项（可增删，type 见 PAYITEM_TYPES）——
    pay_items: list[PayItem] = field(default_factory=list)

    # ========= 相关单位不在这里 =========
    # 相关单位（劳动合同签订 / 社保缴纳 / 工资发放 …… 涉及的公司）是**单位档案**，
    # 与月份无关 → 全月共用一份，存在 settings.json 的 "units"（见 storage.MonthStore）。
    # 月度存档**不保存也不读取**它（老存档里残留的 units 键会被直接忽略）。
    # ===== 便捷 =====
    @property
    def n_days(self) -> int:
        return days_in_month(self.year, self.month)

    def day(self, day: int) -> DayEntry:
        """按号取考勤日（缺号则返回一个 DayEntry 占位，注意不会存回 days）。"""
        for d in self.days:
            if d.day == day:
                return d
        return DayEntry(day=day)

    # ===== 序列化 =====
    def to_dict(self) -> dict:
        """转成可 JSON 化的 dict（**不包含相关单位**：它是全局数据，见上文）。"""
        d = {
            "year": self.year, "month": self.month, "note": self.note,
            "days": [{"day": x.day, "status": x.status, "mark": x.mark,
                      "overtime_hours": x.overtime_hours, "leave_hours": x.leave_hours}
                     for x in self.days],
            "pay_items": [x.to_dict() for x in self.pay_items],
        }
        for f in fields(self):
            name = f.name
            if name in _MONTHBOOK_SKIP:
                continue
            d[name] = getattr(self, name)
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> "MonthBook":
        b = cls()
        # 1) 纯字段：float 字段用 _safe_float 解析；
        #    如果 raw 值本身是非法 / 空 → 保持 dataclass 默认值不动，不清零
        floats = _float_fields()
        for f in fields(cls):
            name = f.name
            if name in _MONTHBOOK_SKIP or name not in raw:
                continue
            val = raw[name]
            try:
                if name in floats:
                    # None / 空字符串 → 跳过（保持默认）
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        continue
                    parsed = _safe_float(val, None)
                    if parsed is None:
                        continue  # 解析失败 → 保持默认
                    setattr(b, name, parsed)
                elif isinstance(val, bool):
                    setattr(b, name, bool(val))
                else:
                    setattr(b, name, val)
            except Exception:
                pass
        # 2) 工资项
        items = raw.get("pay_items")
        if isinstance(items, list):
            b.pay_items = [PayItem.from_dict(x) for x in items if isinstance(x, dict)]
        else:
            b.pay_items = []
        # 2b) 相关单位不按月存（全局数据在 settings.json）→ 老存档里残留的 units 键直接忽略
        # 3) 天数：按 b.n_days 补全（如果 year/month 非法则 n_days=0，days 留空）
        n_days = b.n_days
        b.days = []
        existing: dict[int, DayEntry] = {}
        raw_days = raw.get("days")
        if isinstance(raw_days, list):
            for x in raw_days:
                if not isinstance(x, dict):
                    continue
                try:
                    d_num = int(x.get("day") or 0)
                    if d_num <= 0 or (n_days and d_num > n_days):
                        continue
                    existing[d_num] = DayEntry(
                        day=d_num,
                        status=str(x.get("status") or ""),
                        mark=int(x.get("mark") or 0),
                        overtime_hours=_safe_float(x.get("overtime_hours"), 0.0),
                        leave_hours=_safe_float(x.get("leave_hours"), 0.0),
                    )
                except Exception:
                    continue
        for d in range(1, n_days + 1):
            b.days.append(existing.get(d, DayEntry(day=d)))
        return b


def fix_days(book: MonthBook) -> None:
    """保证 days 覆盖整月，已有 day 对象保留引用。"""
    existing = {x.day: x for x in book.days if x.day > 0}
    book.days = [existing.get(d, DayEntry(day=d)) for d in range(1, book.n_days + 1)]
