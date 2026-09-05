"""集中存放「用户想改时只需要碰这一个文件」的常量。

⚠️ 这是「样式 / 数值」单一来源 —— 改了这里，所有用到的页面自动生效。

下列常量按用途分组，全部是「修改高频」的视觉/UI 参数：

* :data:`TYPE_CHIP`         —— 4 类工资项的 chip 配色（短名 / 前景 / 浅底 / 边框）
* :data:`PAYITEM_COL_WIDTHS`—— 工资项表格列宽（与 _pi_append_row 中的控件一致）
* :data:`OVERTIME_RATE`     —— 加班三档倍率、显示文、配色
* :data:`KEY_COLORS`        —— 其他高频键值映射（删除按钮 / 名称输入框 / 卡头条）

不放在这里的内容：
* 工资项名称目录（→ model.PAYITEM_CATALOG）
* 状态标签 / 调休规则（→ model）
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
    "name": 0,    # 0 = stretch，列宽跟容器伸缩
    "std":  150,  # 标准（月固定/元/天）
    "sub":  110,  # 月小计
    "op":   36,   # 操作（删除按钮）
}
PAYITEM_ROW_BUTTON_HEIGHT: int = 30   # 行内按钮/chip 高度上限
PAYITEM_CHIP_FONT_PX: float = 11.5    # chip 字号
PAYITEM_NAME_INPUT_BG: str = "transparent"  # 名称输入框常态背景
PAYITEM_DELETE_COLOR: str = "#98A2B3"
PAYITEM_DELETE_HOVER_BG: str = "#FEE2E2"
PAYITEM_DELETE_HOVER_FG: str = "#B91C1C"


# ─── 加班倍率（三档：显示文 / 倍数 / 配色）───
# 想加一档「×4 病假」？复制一行就 OK。
#   key     ：model / calc 中的小时字段后缀
#   display ：卡片里展示的徽章文字
#   multiplier：用于报表计算（如果改了显示文，记得同步 model/calc）
#   fg / bg ：徽章前景与底色
OVERTIME_RATE: dict[str, tuple[str, float, str, str]] = {
    "workday": ("×1.5", 1.5, "#15803D", "#DCFCE7"),  # 工作日 × 1.5
    "restday": ("×2.0", 2.0, "#C2410C", "#FFEDD5"),  # 休息日 × 2
    "holiday": ("×3.0", 3.0, "#B91C1C", "#FEE2E2"),  # 法定节假日 × 3
}
OVERTIME_TIPS: str = "时薪 = 加班费基数 ÷（21.75 × 8 = 174 小时）"


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
PAYITEM_LINEEDIT_BORDER: str = "1px solid #E6E8F0"     # 名称输入框 hover 边框
PAYITEM_LINEEDIT_FOCUS: str = "1px solid #6366F1"       # 名称输入框 focus 边框


# ─── 头部列头 ───
PAYITEM_HEADER_HEIGHT: int = 22
PAYITEM_HEADER_FONT_PX: float = 10.5
PAYITEM_HEADER_FG: str = "#98A2B3"
PAYITEM_HEADER_RULE: str = "1px solid #E6E8F0"          # 头部下方分隔线


# ─── 通用空提示 ───
EMPTY_HINT_BG: str = "#FEF4E6"
EMPTY_HINT_FG: str = "#B54708"
EMPTY_HINT_BORDER: str = "1px solid #FEDF89"
