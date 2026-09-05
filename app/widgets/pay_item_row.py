"""工资项单行 widget —— 替代原 SalaryPageMixin._pi_append_row 巨方法。

类边界的考虑：
* 单条工资项的所有「视觉与交互」都集中在这里一处。
* 复用方不需要关心 chip 怎么画、menu 怎么 build、按钮怎么高亮 —— 全部用信号 + 配置驱动。
* 想换 chip 配色 / 列宽 → 改 :mod:`app.config` 即可，不用进这个文件。

公开信号：
* name_changed(str)：名称被改名
* amount_changed(float)：金额被改
* type_changed(str)：类型被切（ptype key）
* delete_requested()：用户点 ✕

公开槽：
* refresh_totals(work_count, per_day_mode)：外部重算后调用，根据 work 与是否按出勤刷新月小计
* refresh_chip()：强制刷新 chip（重命名后想立即显示也行）
* set_amount(value)：程序设置金额（不触发循环）
* set_name(value)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
)

from .. import config, model
from ..ui import NumberSpin


class PayItemRow(QFrame):
    """工资项一行：紧凑 chip + 名称 + 标准 + 月小计 + 删除。"""

    name_changed = Signal(str)
    amount_changed = Signal(float)
    type_changed = Signal(str)
    delete_requested = Signal()

    def __init__(self, item: model.PayItem, parent=None):
        super().__init__(parent)
        self.setObjectName("pirow")
        self.item = item
        # 锁定状态（默认未锁；外部 set_locked_mode 改）
        self._locked = False

        # —— 控件 ──
        self._chip = self._build_chip()
        self._name = self._build_name()
        self._amount = self._build_amount()
        self._rowsub = self._build_rowsub()
        self._delb = self._build_delb()

        # —— 布局 ──
        hl = QHBoxLayout(self)
        hl.setContentsMargins(10, config.PAYITEM_ROW_PADDING,
                                 10, config.PAYITEM_ROW_PADDING)
        hl.setSpacing(8)
        widths = config.PAYITEM_COL_WIDTHS
        self._chip.setFixedWidth(widths["type"])
        self._amount.setFixedWidth(widths["std"])
        self._amount.setMinimumWidth(110)
        self._amount.setMaximumWidth(180)
        self._rowsub.setFixedWidth(widths["sub"])
        self._delb.setFixedSize(widths["op"], widths["op"])
        hl.addWidget(self._chip)
        hl.addWidget(self._name, 1)
        hl.addWidget(self._amount)
        hl.addWidget(self._rowsub)
        hl.addWidget(self._delb)

        # —— 信号 ──
        self._name.textChanged.connect(self._on_name_changed)
        self._amount.valueChanged.connect(self._on_amount_changed)
        self._delb.clicked.connect(self.delete_requested)

        # —— 初次同步 UI ──
        self._amount.setValue(item.amount)
        self._name.setText(item.name)
        self.refresh_chip()

    # ---------------------------------------------------------------------
    # 控件构造（每个构造方法只做一件事，方便子类覆盖）
    # ---------------------------------------------------------------------
    def _build_chip(self) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("piChip")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(26)
        btn.setMaximumHeight(config.PAYITEM_ROW_BUTTON_HEIGHT)
        menu = QMenu(btn)
        for key, label in model.PAYITEM_TYPES:
            act = menu.addAction(label)
            act.setData(key)
            act.triggered.connect(lambda _checked=False, k=key: self._on_type_changed(k))
        btn.setMenu(menu)
        return btn

    def _build_name(self) -> QLineEdit:
        le = QLineEdit()
        le.setObjectName("piName")
        le.setPlaceholderText("名称")
        return le

    def _build_amount(self) -> NumberSpin:
        sp = NumberSpin(decimals=2, step=10.0, minimum=-1e9, compact=True)
        sp.setObjectName("piAmount")
        sp.setMinimumHeight(26)
        sp.setMaximumHeight(config.PAYITEM_ROW_BUTTON_HEIGHT)
        return sp

    def _build_rowsub(self) -> QLabel:
        lab = QLabel("¥ 0.00")
        lab.setObjectName("piTotal")
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lab

    def _build_delb(self) -> QPushButton:
        btn = QPushButton("✕")
        btn.setObjectName("piDelete")
        btn.setToolTip("删除该工资项")
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    # ---------------------------------------------------------------------
    # 信号回调
    # ---------------------------------------------------------------------
    def _on_name_changed(self, text: str):
        if self._locked:
            return
        self.item.name = text
        self.name_changed.emit(text)

    def _on_amount_changed(self, value: float):
        if self._locked:
            return
        self.item.amount = float(value)
        self.amount_changed.emit(self.item.amount)

    def _on_type_changed(self, ptype: str):
        if self._locked:
            return
        if ptype not in dict(model.PAYITEM_TYPES):
            ptype = "wage"
        self.item.type = ptype
        self.refresh_chip()
        self.type_changed.emit(ptype)

    # ---------------------------------------------------------------------
    # 公开 API
    # ---------------------------------------------------------------------
    def refresh_chip(self):
        """刷新 chip 文字、颜色、tooltip。"""
        ptype = self.item.type
        short = config.TYPE_CHIP.get(ptype, ("?",))[0]
        self._chip.setText(f"{short}  ▾")
        self._chip.setToolTip(model.PAYITEM_TYPE_DESC.get(ptype, ""))

    def refresh_totals(self, work_count: int):
        """根据 work_count 重算月小计与金额框 suffix。"""
        per = self.item.is_per_day()
        self._amount.setSuffix(" 元/天" if per else " 元")
        sub = self.item.amount * work_count if per else self.item.amount
        self._rowsub.setText(config.MONEY_FMT.format(sub))

    def set_amount(self, value: float, *, block_signals: bool = True):
        if block_signals:
            self._amount.blockSignals(True)
        self._amount.setValue(value)
        if block_signals:
            self._amount.blockSignals(False)

    def set_name(self, text: str, *, block_signals: bool = True):
        if block_signals:
            self._name.blockSignals(True)
        self._name.setText(text)
        if block_signals:
            self._name.blockSignals(False)

    def take_focus(self):
        self._amount.setFocus(Qt.OtherFocusReason)
        self._amount.selectAll()

    def set_locked_mode(self, locked: bool):
        """锁定只读：禁用名称/金额/类型切换/删除按钮；回调层面也设 self._locked 防 API 写入。"""
        self._locked = bool(locked)
        for ref in ("_name", "_amount", "_delb"):
            w = getattr(self, ref, None)
            if w is not None:
                try:
                    w.setEnabled(not locked)
                except Exception:
                    pass
        # 类型 chip 是一个带 menu 的按钮：禁用后 menu 也不会弹起
        if hasattr(self, "_chip"):
            try:
                self._chip.setEnabled(not locked)
            except Exception:
                pass
