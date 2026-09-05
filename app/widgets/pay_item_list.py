"""工资项列表容器 —— 标题 / 列头 / 行列表 / 空提示 / 添加按钮。

职责：
* 持有 N 个 :class:`PayItemRow` 与一个空提示标签
* 把添加按钮的弹菜单交给 :class:`PayItemCatalogMenu`
* 转发所有 row 信号给父类，子类只关心「条目变化」事件
* :meth:`rebuild_from_book` —— 整月切换或首次渲染时使用
* :meth:`refresh_totals(work_count)` —— 上班天数变化时统一刷新
"""
from __future__ import annotations

import traceback

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .. import config, model
from .pay_item_menu import PayItemCatalogMenu
from .pay_item_row import PayItemRow


class PayItemListWidget(QFrame):
    """工资项列表卡片（左半侧的主卡片）。

    Signals
    -------
    changed()
        任意一条工资项的 name / amount / type / 新增 / 删除引发该信号，外部做小计重算。
    insert_requested_at(str, int)
        外部插入新数据后，希望把光标滚动到该 index 的行可见。
    """

    changed = Signal()
    insert_requested_at = Signal(int)
    copy_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        # 锁定状态（外部 set_locked_mode 改）
        self._locked = False

        # —— 顶部：标题 + 添加按钮 ──
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(config.PAYITEM_CARD_TITLE)
        title.setObjectName("cardTitle")
        self._add_btn = QPushButton(config.ADD_BUTTON_TEXT)
        self._add_btn.setObjectName("primary")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setToolTip(config.PAYITEM_CARD_TOOLTIP)
        self._copy_btn = QPushButton(config.COPY_BUTTON_TEXT)
        self._copy_btn.setObjectName("ghost")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setToolTip(config.COPY_BUTTON_TOOLTIP)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self._copy_btn)
        title_row.addWidget(self._add_btn)

        # —— 列表容器 ──
        self._rows_lay = QVBoxLayout()
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(config.PAYITEM_ROW_SPACING)
        self._rows_box = QWidget()
        self._rows_box.setLayout(self._rows_lay)

        # —— 主布局 ──
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 10)
        lay.setSpacing(2)
        lay.addLayout(title_row)
        lay.addWidget(self._header())
        lay.addWidget(self._rows_box)

        # —— 运行时状态 ──
        self.rows: list[PayItemRow] = []
        self._empty_tip: QLabel | None = None
        self._catalog_menu = PayItemCatalogMenu(self)
        self._catalog_menu.item_chosen.connect(self._on_chosen)
        self._catalog_menu.custom_requested.connect(self._on_custom)
        self._add_btn.clicked.connect(self._open_catalog)
        self._copy_btn.clicked.connect(self.copy_requested.emit)

    # ---------------------------------------------------------------------
    # 列表管理
    # ---------------------------------------------------------------------
    def _header(self) -> QFrame:
        """列头：与下方行的列宽严格对齐。"""
        h = QFrame()
        h.setObjectName("piHeader")
        h.setFixedHeight(config.PAYITEM_HEADER_HEIGHT)
        hl = QHBoxLayout(h)
        hl.setContentsMargins(10, 0, 10, 1)
        hl.setSpacing(8)
        widths = config.PAYITEM_COL_WIDTHS

        def _lab(text: str, w: int) -> QLabel:
            lab = QLabel(text)
            lab.setObjectName("piHdrCell")
            lab.setFixedHeight(16)
            if w:
                lab.setFixedWidth(w)
            return lab

        hl.addWidget(_lab("类型",  widths["type"]))
        hl.addWidget(_lab("名称",  0), 1)
        hl.addWidget(_lab("标准",  widths["std"]))
        hl.addWidget(_lab("月小计", widths["sub"]))
        hl.addWidget(_lab("", widths["op"]))
        return h

    def add_row(self, item: model.PayItem, *, index: int | None = None,
                focus_amount: bool = False) -> PayItemRow:
        """向列表里插入一行。

        Parameters
        ----------
        item
            要显示的 PayItem（行会保存一份引用回写到 item）
        index
            None 表示追加；否则插入到该位置。
        focus_amount
            True 时把光标定位到金额输入框（用于「+ 添加工资项」后立刻能输入数字）。
        """
        # 清理空提示
        if self._empty_tip is not None:
            self._empty_tip.setParent(None)
            self._empty_tip.deleteLater()
            self._empty_tip = None
        row = PayItemRow(item)
        row.name_changed.connect(lambda _t: self.changed.emit())
        row.amount_changed.connect(lambda _v: self.changed.emit())
        row.type_changed.connect(lambda _t: self.changed.emit())
        row.delete_requested.connect(lambda r=row: self._remove(r))
        if index is None or index >= len(self.rows):
            self._rows_lay.addWidget(row)
            self.rows.append(row)
            inserted = len(self.rows) - 1
        else:
            self._rows_lay.insertWidget(index, row)
            self.rows.insert(index, row)
            inserted = index
        if focus_amount:
            row.take_focus()
            self.insert_requested_at.emit(inserted)
        return row

    def remove_row(self, row: PayItemRow):
        """删除给定 row（兼容旧 API；新代码可直接连 delete_requested）。"""
        self._remove(row)

    def _remove(self, row: PayItemRow):
        if self._locked:
            return  # 锁定只读：删除是写入操作，整 widget 屏蔽
        if row not in self.rows:
            return
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        if not self.rows and self._empty_tip is None:
            self._show_empty_tip()
        # 同步：把对应的 PayItem 从 book.pay_items 移除（owner 注册的回调）
        cb = getattr(self, "_on_remove_callback", None)
        if cb is not None:
            try:
                cb(row.item)
            except Exception:
                traceback.print_exc()
        self.changed.emit()

    def _show_empty_tip(self):
        tip = QLabel(config.PAYITEM_EMPTY_HINT)
        tip.setObjectName("emptyTip")
        tip.setWordWrap(True)
        self._empty_tip = tip
        self._rows_lay.addWidget(tip)

    def refresh_totals(self, work_count: int):
        """重新计算每行的「月小计」。"""
        for r in self.rows:
            r.refresh_totals(work_count)

    def rebuild_from_book(self, book: model.MonthBook):
        """整月切换 / 首次渲染：清空并按 book.pay_items 重建。"""
        # 清空
        for r in list(self.rows):
            r.setParent(None)
            r.deleteLater()
        self.rows.clear()
        for it in book.pay_items:
            self.add_row(it)
        if not book.pay_items:
            self._show_empty_tip()

    def ensure_visible_row(self, row: PayItemRow):
        """滚到指定行可见（聚焦时调用）。"""
        if self.parent() is not None:
            area = self.parent().parent()
            if isinstance(area, QWidget) and hasattr(area, "ensureWidgetVisible"):
                area.ensureWidgetVisible(row)

    # ---------------------------------------------------------------------
    # 添加按钮 / 菜单
    # ---------------------------------------------------------------------
    def _open_catalog(self, *_):
        self._catalog_menu.set_used_names({r.item.name for r in self.rows})
        self._catalog_menu.popup_for(self._add_btn)

    def _on_chosen(self, ptype: str, name: str):
        """菜单里选中标准项 —— 转发给父 mixin。"""
        # 让父 mixin 处理「插入位置 + 默认名顺延」逻辑（仍是 mixin 关心的事）。
        # 这里我们只接住信号，转发给注册到自己的「add_listener」。
        cb = getattr(self, "_on_add_callback", None)
        if cb is not None:
            cb(ptype, name)

    def _on_custom(self, ptype: str):
        """菜单里点自定义 —— 弹出输入框后回调 add_listener。"""
        if self._locked:
            return  # 锁定只读：自定义菜单不弹
        label = model.PAYITEM_TYPE_NAMES.get(ptype, "工资项")
        default = model.PAYITEM_DEFAULT_NAME.get(ptype, "工资项")
        name, ok = QInputDialog.getText(self, "添加工资项",
                                        f"{label} · 名称：", text=default)
        if not ok or not name.strip():
            return
        cb = getattr(self, "_on_add_callback", None)
        if cb is not None:
            cb(ptype, name.strip())

    # 注册回调：pages_salary 在初始化时调用
    def set_add_callback(self, cb):
        """注册「点添加菜单后该怎么新增一条」的回调。"""
        self._on_add_callback = cb

    def set_remove_callback(self, cb):
        """注册「删除某行后该怎么从 book 里同步移除」的回调。
        widget 自己只管 UI；数据同步交给 owner，避免遗漏 book.pay_items。"""
        self._on_remove_callback = cb

    def reopen_menu(self):
        """供外部在添加后重新弹起菜单（暂未使用，保留作扩展）。"""
        self._open_catalog()

    # ---------------------------------------------------------------------
    # 锁定模式（页面级联动）：禁用所有"修改类"控件
    # ---------------------------------------------------------------------
    def set_locked_mode(self, locked: bool):
        """锁定只读：禁用标题栏添加/复制按钮 + 所有行的修改控件；widget 内部 _locked
        会让 _remove / _on_custom 等 API 写入路径也整体短路。"""
        self._locked = bool(locked)
        # 标题栏添加/复制
        for btn in (getattr(self, "_add_btn", None), getattr(self, "_copy_btn", None)):
            if btn is not None:
                btn.setEnabled(not locked)
        # 所有行
        for row in self.rows:
            try:
                row.set_locked_mode(locked)
            except Exception:
                if hasattr(row, "_delb"):
                    row._delb.setEnabled(not locked)
