"""通用 UI 常量与小组件：导航页表 / 状态配色 / 数字输入 / 可点击卡片。

与 design token（style.py）及网页原型配色保持一致。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QFrame, QSizePolicy

from . import model

# 左侧导航六区（顺序即页面索引）
PAGES = [
    ("overview", "🏠  工作台"),
    ("calendar", "📅  考勤"),
    ("salary", "💰  薪酬构成"),
    ("params", "⚙️  参数"),
    ("report", "📊  报表"),
    ("annual", "📆  年度汇总"),
]
PAGE_TITLES = {
    "overview": ("工作台", "本月关键数据 · 合规判定"),
    "calendar": ("考勤", "逐日标记状态，点选后右侧编辑加班 / 请假"),
    "salary": ("薪酬构成", "工资项可增删；补贴只需一条，按出勤自动折算"),
    "params": ("参数", "社保公积金基数 / 比例与各项标准，可存为模板"),
    "report": ("报表", "应发、扣除、实发与合规判定明细"),
    "annual": ("年度汇总", "全年 12 个月考勤与工资一览，可打印"),
}

# 考勤状态 → (底色, 前景色)，与设计令牌一致
DAY_PALETTE = {
    "上班": ("#DCFCE7", "#15803D"),
    "休息": ("#F1F5F9", "#475569"),
    "事假": ("#FEF3C7", "#B45309"),
    "病假": ("#FFE4E6", "#BE123C"),
    "婚假": ("#FCE7F3", "#BE185D"),
    "丧假": ("#E2E8F0", "#334155"),
    "产假": ("#EDE9FE", "#6D28D9"),
    "年假": ("#E0F2FE", "#0369A1"),
    "其他": ("#CCFBF1", "#0F766E"),
}
# 状态顺序与标签单一来源：model.STATUS_LABELS（勿再各自维护一份）
STATUS_ORDER = list(model.STATUS_LABELS)


class NumberSpin(QDoubleSpinBox):
    """带千分位、可设精度/步长/前后缀的数字输入框。"""

    def __init__(self, decimals=2, step=1.0, prefix="", suffix="", minimum=-1e12, compact=False):
        super().__init__()
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setRange(minimum, 1e12)
        self.setGroupSeparatorShown(True)
        if prefix:
            self.setPrefix(prefix)
        if suffix:
            self.setSuffix(suffix)
        if compact:
            # 使用最小宽度替代固定宽度，以便在窄屏上允许挤压布局
            self.setMinimumWidth(80)
            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)


class ClickTile(QFrame):
    """可点击的卡片（hover 高亮 + 点击回调）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cb = None

    def set_click(self, cb):
        self._cb = cb

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._cb is not None:
            self._cb()
        super().mouseReleaseEvent(e)

    def enterEvent(self, e):
        self.setProperty("hover", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(e)
