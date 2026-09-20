"""通用 UI 常量与小组件：导航页表 / 状态配色 / 数字输入 / 锁定控件辅助。

与 design token（style.py）及网页原型配色保持一致。
"""
from __future__ import annotations

import os

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QDoubleSpinBox, QLabel, QPushButton, QSizePolicy

from . import model


def default_export_path(filename: str) -> str:
    """导出对话框的初始路径：优先「文档」目录，取不到再回退用户主目录。

    为什么必须显式给：``QFileDialog.getSaveFileName`` 的初始目录留空时，Qt 会沿用
    “上次使用目录”或进程的当前工作目录 —— 从 ``.desktop`` 启动时 CWD 往往是 ``/``
    或 home，用户会觉得导出的文件“不知道存哪里去了”。
    """
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation)
    if not base or not os.path.isdir(base):
        base = os.path.expanduser("~")
    # normpath：QStandardPaths 返回正斜杠路径，与 os.path.join 拼出来会混用两种
    # 分隔符（Windows 下显示与字符串比较都很别扭）
    return os.path.normpath(os.path.join(base, filename))


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

# 锁定 / 只读态输入框样式（锁定月、跟随最低工资的字段都用它，
# 避免在 pages_* 里重复手写同一串 QSS）
LOCKED_INPUT_QSS = "background:#F5F7FA;color:#667085;"

# 锁定月的只读提示横幅
LOCK_BANNER_TEXT = "🔒  当前月份已锁定 · 仅供查看，所有修改操作已屏蔽"

# 「跟随最低工资」类字段的切锁按钮文案（最低工资 / 加班费基数 / 公积金基数共用）
LOCK_BTN_LOCKED_TEXT = "🔒 已锁定 · 冻结当前值"
LOCK_BTN_UNLOCKED_TEXT = "🔓 已解锁 · 可手动修改"


def make_lock_button(tooltip: str, on_click=None) -> QPushButton:
    """统一的字段级切锁按钮（🔒 已锁定 / 🔓 已解锁）。

    文案随状态变化，请配合 :func:`set_lock_button_state` 使用。
    """
    btn = QPushButton(LOCK_BTN_LOCKED_TEXT)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setObjectName("ghost")
    btn.setToolTip(tooltip)
    if on_click is not None:
        btn.clicked.connect(on_click)
    return btn


def set_lock_button_state(btn, locked: bool) -> None:
    """按锁定态刷新切锁按钮文案（按钮不存在时忽略）。"""
    if btn is None:
        return
    try:
        btn.setText(LOCK_BTN_LOCKED_TEXT if locked else LOCK_BTN_UNLOCKED_TEXT)
    except RuntimeError:
        pass


def make_lock_banner(parent=None) -> QLabel:
    """锁定月的只读提示横幅（考勤 / 薪酬 / 参数三页共用，默认隐藏）。"""
    lab = QLabel(LOCK_BANNER_TEXT, parent)
    lab.setStyleSheet(
        "background:#FEF4E6;color:#B54708;border:1px solid #FEDF89;"
        "border-radius:8px;padding:8px 14px;font-weight:600;font-size:13px;")
    lab.setWordWrap(True)
    lab.hide()
    return lab


def show_lock_banner(lab, visible: bool) -> None:
    """按锁定态显隐只读横幅（横幅尚未创建 / 已销毁时安全忽略）。"""
    if lab is None:
        return
    try:
        lab.setVisible(bool(visible))
    except RuntimeError:
        pass


def set_busy_button(btn, busy: bool, busy_text: str, idle_text: str,
                    enabled: bool = True) -> None:
    """切换按钮的「进行中」态（文案 + 可用性）。

    :param enabled: 任务结束后按钮是否可用（锁定月传 False，避免解锁被忽略）
    按钮可能已随页面重建而销毁，此时静默忽略。
    """
    if btn is None:
        return
    try:
        btn.setText(busy_text if busy else idle_text)
        btn.setEnabled(not busy and enabled)
    except RuntimeError:
        pass


def set_field_locked(spin, locked: bool) -> None:
    """切换输入框的「字段级锁定」态：锁定时禁用 + 灰底，解锁时恢复。

    与整月只读（Card.set_locked）不是一回事：最低工资 / 加班费基数 /
    公积金基数在月份未锁定时也可能处于「跟随最低工资」的锁定态。
    """
    if spin is None:
        return
    try:
        spin.setEnabled(not locked)
        spin.setStyleSheet(LOCKED_INPUT_QSS if locked else "")
    except RuntimeError:
        pass


def set_fields_locked(spins, locked: bool) -> None:
    """批量版 :func:`set_field_locked`（None 项自动跳过）。"""
    for sp in spins:
        set_field_locked(sp, locked)


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
