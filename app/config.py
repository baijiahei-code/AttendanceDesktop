"""集中存放「用户想改时只需要碰这一个文件」的常量。

⚠️ 这里是「样式 / 数值」单一来源 —— 列在下面的常量都是**真被代码读到的**，
改了立刻生效。（改不生效的“看着像旋钮”的常量一律不留，避免浪费时间。）

下列常量按用途分组，全部是「修改高频」的视觉/UI 参数：

* :data:`TYPE_CHIP`         —— 4 类工资项的 chip 配色（短名 / 前景 / 浅底 / 边框）
* :data:`PAYITEM_COL_WIDTHS`—— 工资项表格列宽（表头与数据行读同一份，见
  ``widgets/pay_item_list.py`` 与 ``widgets/pay_item_row.py``）
* :data:`OVERTIME_RATE`     —— 加班三档的**显示文 / 配色**（显示文由 :data:`OT_RATE_*`
  派生，不单独存倍率 —— 倍率的唯一出处是下面那三个常量）
* :data:`OK_COLOR` / :data:`BAD_COLOR` —— 「合规 / 违规」文本色（UI 与 Excel 共用）

不放在这里的内容：
* 工资项名称目录（→ model.PAYITEM_CATALOG）
* 状态标签 / 调休规则（→ model）
* 控件级 QSS（→ style.py；那里用的是独立字面量，不读本文件）
"""
from __future__ import annotations

# ─── 类型 chip（替代宽大 QComboBox，靠颜色+位置传递分类信息）───
# 想换一种类型的颜色或简称？改这里即可。
#   key：与 model.PAYITEM_TYPES 的内部 key 同步
#   value：(短名 / 前景色 / 浅底色 / 边框色) — 4 个字符串
TYPE_CHIP: dict[str, tuple[str, str, str, str]] = {
    "wage":         ("最低工资", "#4F46E5", "#EEF2FF", "#C7D2FE"),  # 紫
    "subsidy":      ("公司补贴", "#0E7490", "#ECFEFF", "#A5F3FC"),  # 青
    "fixed_allow":  ("固定津贴", "#B54708", "#FEF4E6", "#FEDF89"),  # 橙
    "perday_allow": ("按出勤",   "#027A48", "#DCFCE7", "#BBF7D0"),  # 绿
}
# 4 类类型对应的彩色色点（比 chip 小一圈，用于菜单表头）
TYPE_DOT: dict[str, str] = {k: v[1] for k, v in TYPE_CHIP.items()}


# ─── 工资项表格列宽（像素，与 header / data row 同时引用）───
# 想让「名称」列更宽？改 :data:`PAYITEM_COL_WIDTHS["name"]`。
PAYITEM_COL_WIDTHS: dict[str, int] = {
    "type": 86,   # 类型 chip
    # 名称列**恒为 stretch**（表头与数据行都传固定值 0/伸展因子 1），
    # 这里的 0 只是占位说明「不设固定宽度」——改数值不会生效。
    "name": 0,
    "std":  150,  # 标准（月固定/元/天）
    "sub":  110,  # 月小计
    "op":   36,   # 操作（删除按钮）
}
PAYITEM_ROW_BUTTON_HEIGHT: int = 30   # 行内按钮/chip 高度上限
# 表头与数据行的左右内边距（像素）—— 必须是**同一个值**，否则列对不齐
PAYITEM_ROW_PAD_X: int = 10


# ─── 加班倍率（三档：显示文 / 倍数 / 配色）───
# 想加一档「×4 病假」？复制一行就 OK。
#   key     ：model / calc 中的小时字段后缀
#   display ：卡片里展示的徽章文字
#   OT_RATE_*：三档倍率的**唯一出处** —— ``calc.compute`` 用它算三档加班工资，
#             ``calc.overtime_rate_text`` 用它拼报表文案，改这里金额与文案同步变
#   fg / bg ：徽章前景与底色
OT_RATE_WORKDAY: float = 1.5
OT_RATE_RESTDAY: float = 2.0
OT_RATE_HOLIDAY: float = 3.0
OVERTIME_RATE: dict[str, tuple[str, str, str]] = {
    # (徽章文字, 前景色, 底色)；徽章文字由上面的 OT_RATE_* **派生** —— 改倍率时
    # 徽章文字会自动跟着变（不会一个变一个不变）。
    # ⚠ 倍率的唯一出处就是 OT_RATE_*（calc 算钱、overtime_rate_text 拼文案都念它）；
    #    这里不再存一份倍率 —— 存了也会被当成“改了能改钱”的假旋钮。
    "workday": (f"×{OT_RATE_WORKDAY:.1f}", "#15803D", "#DCFCE7"),  # 工作日 × 1.5
    "restday": (f"×{OT_RATE_RESTDAY:.1f}", "#C2410C", "#FFEDD5"),  # 休息日 × 2
    "holiday": (f"×{OT_RATE_HOLIDAY:.1f}", "#B91C1C", "#FEE2E2"),  # 法定节假日 × 3
}

# 「合规 / 违规」文本色（单一来源：工作台 / 报表 / 年度汇总的 UI 与 Excel 导出都读这里）
OK_COLOR: str = "#0B7A3B"
BAD_COLOR: str = "#C00000"


# ─── 顶栏 strip 4 个数值的显示文 ───
# 想让「应发合计」改成别的？改这里。
SALARY_STRIP_TITLES: dict[str, str] = {
    "gross": "应发合计",
    "in":    "计入最低工资",
    "out":   "不计入最低工资（津贴/加班等）",
    "hand":  "预计到手",
}


# ─── 卡片标题常量（pages 通用）───
# 想把「工资项」改成别的？或者新增一个分类？改这里。
PAYITEM_CARD_TITLE: str = "工资项"
PAYITEM_CARD_TOOLTIP: str = "名称可改 · 行可删 · 按出勤项填「每日标准」自动 × 上班天数"
PAYITEM_EMPTY_HINT: str = "本月还没有工资项：点「＋ 添加工资项」开始录入。"
OT_CARD_TITLE: str = "加班工资"
DED_CARD_TITLE: str = "个人扣除"
ADD_BUTTON_TEXT: str = "＋ 添加工资项"
COPY_BUTTON_TEXT: str = "📋 复制工资项"
COPY_BUTTON_TOOLTIP: str = "把当前月工资项复制到其它月份；按出勤津贴会按目标月实际上班天数自动重算"


# ─── 数字格式化 ───
MONEY_FMT: str = "¥ {:,.2f}"  # 月小计 / 应发 / 扣除 等都用这个格式


# ─── 行行为 ───
PAYITEM_ROW_SPACING: int = 3     # 工资项列表中每行之间的间距
PAYITEM_ROW_PADDING: int = 2     # 工资项单行的上下内边距


# ─── 头部列头 ───
PAYITEM_HEADER_HEIGHT: int = 22
