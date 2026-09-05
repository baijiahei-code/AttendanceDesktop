"""PySide6 主窗口（浅色白底侧栏 + 靛紫→天青品牌 + 工资项列表化）。"""
from __future__ import annotations

import os
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup,
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget, QSizePolicy,
)

from . import calc, model
from .storage import MonthStore
from .style import STYLE
from .ui import PAGES, PAGE_TITLES
from .pages_annual import AnnualPageMixin
from .pages_calendar import CalendarPageMixin
from .pages_overview import OverviewPageMixin
from .pages_params import ParamsPageMixin
from .pages_report import ReportPageMixin
from .pages_salary import SalaryPageMixin

class MainWindow(OverviewPageMixin, CalendarPageMixin, SalaryPageMixin,
                 ParamsPageMixin, ReportPageMixin, AnnualPageMixin, QMainWindow):

    def __init__(self, store: MonthStore):
        super().__init__()
        self.store = store
        self._book: model.MonthBook | None = None
        self._loading = False
        self._last_result = None
        # 同步优化：仅渲染当前页 + 150ms 合并保存
        self._current_page_idx = 0
        self._dirty = False
        # 数据版本：每次 calc 后 +1；每个重数据页记录自己被画到哪个版本
        self._data_version = 0
        self._rendered_versions: dict[int, int] = {}
        # 锁定只读状态机：当前月 self._book.locked 时为 True
        self._is_locked = False
        self._change_timer = QTimer(self)
        self._change_timer.setSingleShot(True)
        self._change_timer.setInterval(150)
        self._change_timer.timeout.connect(self._flush_changed)

        self.setWindowTitle("工资考勤表")
        # 窗口尺寸按屏幕可用区域自适应：过大窗口在小屏上会把右列卡片裁切/挤压
        app0 = QApplication.instance()
        geo = app0.primaryScreen().availableGeometry() if app0 is not None else None
        if geo is not None:
            w = min(1280, geo.width() - 48)
            h = min(860, geo.height() - 80)
            w = max(w, min(1080, geo.width()))
            h = max(h, min(640, geo.height()))
            self.resize(w, h)
            self.setMinimumSize(min(1080, geo.width()), min(640, geo.height()))
        else:
            self.resize(1280, 860)
            self.setMinimumSize(1080, 640)

        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setStyleSheet(STYLE)

        self._build_ui()

        today = datetime.now()
        self._year_spin.setValue(today.year)
        self._month_spin.setValue(today.month)
        self._go(today.year, today.month)
        self._refresh_history()
        self._show_page(0)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        lay.addWidget(self._build_main(), 1)
        self.setCentralWidget(root)

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        # 允许侧栏在窄窗口时收缩为最小可读宽度，宽窗口保留 232px 作为理想宽度
        side.setMinimumWidth(180)
        side.setMaximumWidth(340)
        side.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        v = QVBoxLayout(side)
        v.setContentsMargins(16, 20, 16, 14)
        v.setSpacing(6)

        brand = QLabel("📋 工资考勤表")
        brand.setObjectName("brand")
        sub = QLabel("月度考勤 · 工资核算")
        sub.setObjectName("brandSub")
        v.addWidget(brand)
        v.addWidget(sub)
        v.addSpacing(12)

        sec = QLabel("功 能")
        sec.setObjectName("sideSec")
        v.addWidget(sec)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns = []
        for i, (_, label) in enumerate(PAGES):
            b = QPushButton(label)
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.nav_group.addButton(b, i)
            self.nav_btns.append(b)
            v.addWidget(b)
        self.nav_group.idClicked.connect(self._show_page)
        v.addSpacing(14)

        # 保留 side_month 成员（_go 会 setText），但不再显示到侧栏 UI
        self.side_month = QLabel("—")
        self.side_month.setObjectName("sideMon")
        self.side_month.hide()

        sec2 = QLabel("历史月份")
        sec2.setObjectName("sideSec")
        v.addWidget(sec2)

        self.history = QListWidget()
        self.history.setObjectName("historyList")
        self.history.setMaximumHeight(260)
        self.history.setCursor(Qt.PointingHandCursor)
        self.history.itemClicked.connect(self._on_history)
        self.history.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history.customContextMenuRequested.connect(self._show_history_menu)
        v.addWidget(self.history, 1)

        if hasattr(self.store, "dir"):
            data_label = QLabel("数据：" + self.store.dir)
            data_label.setObjectName("sideData")
            data_label.setWordWrap(True)
            v.addWidget(data_label)
        v.addStretch(0)
        return side

    def _build_main(self):
        col = QWidget()
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # 顶栏
        header = QFrame()
        header.setObjectName("header")
        header.setMinimumHeight(56)
        header.setMaximumHeight(120)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h = QHBoxLayout(header)
        h.setContentsMargins(22, 0, 18, 0)
        tt = QVBoxLayout()
        tt.setSpacing(0)
        self.page_title = QLabel("")
        self.page_title.setObjectName("pageTitle")
        self.page_sub = QLabel("")
        self.page_sub.setObjectName("pageSub")
        tt.addWidget(self.page_title)
        tt.addWidget(self.page_sub)
        h.addLayout(tt)
        h.addStretch(1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusOk")
        h.addWidget(self.status_label, 0, Qt.AlignVCenter)
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._manual_save)
        h.addWidget(self.save_btn)
        # —— 关于 / 免责声明入口 ——
        about_btn = QPushButton("关于")
        about_btn.setToolTip("版本与免责声明")
        about_btn.setCursor(Qt.PointingHandCursor)
        about_btn.setFixedHeight(30)
        about_btn.setStyleSheet(
            "QPushButton{background:#FFFFFF;border:1px solid #E6E8F0;border-radius:8px;"
            "color:#667085;font-size:13px;padding:0 12px;}"
            "QPushButton:hover{background:#F8FAFC;color:#4F46E5;}")
        about_btn.clicked.connect(self._show_about)
        h.addWidget(about_btn)
        self._about_btn = about_btn
        cl.addWidget(header)

        # 月份操作条
        monthbar = QFrame()
        monthbar.setObjectName("monthbar")
        mb = QHBoxLayout(monthbar)
        mb.setContentsMargins(22, 8, 18, 8)
        mb.setSpacing(8)
        pbtn = QPushButton("‹ 上月")
        pbtn.clicked.connect(lambda: self._shift_month(-1))
        nbtn = QPushButton("下月 ›")
        nbtn.clicked.connect(lambda: self._shift_month(1))
        self._year_spin = QSpinBox()  # 保留成员（数据源），不再显示
        self._year_spin.setRange(2000, 2100)
        self._year_spin.valueChanged.connect(self._on_year_spin)
        self._month_spin = QSpinBox()
        self._month_spin.setRange(1, 12)
        self._month_spin.valueChanged.connect(self._on_month_spin)
        self._month_btn = QPushButton("2026 年 9 月 ▾")
        self._month_btn.setMinimumWidth(132)
        self._month_btn.setCursor(Qt.PointingHandCursor)
        self._month_btn.setStyleSheet("font-size:15px;font-weight:700;padding:6px 16px;")
        self._month_btn.clicked.connect(self._open_month_popup)
        self._lock_btn = QPushButton("🔓")
        self._lock_btn.setFixedWidth(36)
        self._lock_btn.setCursor(Qt.PointingHandCursor)
        self._lock_btn.setToolTip("锁定/解锁当前月份（锁定后不会被覆盖）")
        self._lock_btn.clicked.connect(self._toggle_lock_current_month)
        mb.addWidget(pbtn)
        mb.addWidget(self._month_btn)
        mb.addWidget(self._lock_btn)
        mb.addWidget(nbtn)
        mb.addStretch(1)
        del_btn = QPushButton("删除本月")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete_month)
        mb.addWidget(del_btn)
        cl.addWidget(monthbar)

        # 页面
        self.stack = QStackedWidget()
        self.pages_widget = []
        self.params_page = QWidget()
        self.calendar_page = QWidget()
        self.salary_area = QScrollArea()
        self.salary_area.setWidgetResizable(True)
        self.salary_area.setFrameShape(QFrame.NoFrame)
        self.report_page = QWidget()
        cl.addWidget(self.stack, 1)
        return col

    def _show_page(self, idx: int):
        if isinstance(idx, int) and 0 <= idx < len(PAGES):
            key = PAGES[idx][0]
            if not self.stack.count():
                # 首次：装载页面
                self._build_pages()
            # 切页前先 flush 待保存改动，保证目标页看到的是最新数据
            if self._current_page_idx != idx and self._dirty:
                self._flush_changed()
            self.stack.setCurrentIndex(idx)
            self._current_page_idx = idx
            for i, b in enumerate(self.nav_btns):
                b.setChecked(i == idx)
            title, sub = PAGE_TITLES[key]
            self.page_title.setText(title)
            self.page_sub.setText(sub)
            # 进入重数据页时，按版本判断是否要重建——避免每次进来都重画
            if key in ("overview", "report"):
                page_idx = 0 if key == "overview" else 4
                if self._last_result is None:
                    self._recalc()
                elif self._rendered_versions.get(page_idx, -1) < self._data_version:
                    self._render_one_page(page_idx, self._last_result)
                    self._rendered_versions[page_idx] = self._data_version
            elif key == "salary":
                # 参数页改了社保/公积金基数等，切到薪酬页必须刷新自动金额
                if self._last_result is None:
                    self._recalc()
                else:
                    self._sync_salary_ui()
            elif key == "calendar":
                if self._last_result is not None:
                    self._update_cal_count()
            elif key == "annual":
                self._fill_annual()

    # ================= 月份 =================

    def _refresh_history(self):
        if not hasattr(self, "history"):
            return
        self._loading = True
        self.history.blockSignals(True)
        self.history.clear()
        cur = (self._book.year, self._book.month) if self._book else None
        cur_item = None
        for (y, m) in self.store.list_months():
            label = f"{y} 年 {m} 月"
            # 当前月在内存里已知，直接读；其他月轻量读盘判定锁定图标
            if cur == (y, m):
                locked = bool(self._book.locked)
            else:
                b = self.store.load(y, m)
                locked = bool(b and b.locked)
            if locked:
                label = f"🔒 {label}"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, (y, m))
            self.history.addItem(it)
            if cur == (y, m):
                cur_item = it
        if cur_item is not None:
            self.history.setCurrentItem(cur_item)
        self.history.blockSignals(False)
        self._loading = False

    def _on_history(self, item):
        if self._loading:
            return
        data = item.data(Qt.UserRole)
        if data:
            self._go(data[0], data[1])

    def _show_history_menu(self, pos):
        """历史月份列表右键菜单：锁定/解锁某月 + 跳转到该月。"""
        item = self.history.itemAt(pos)
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        y, m = data
        book = self.store.load(y, m)
        if book is None:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self.history)
        head = menu.addAction(f"{y} 年 {m} 月 · {'🔒 已锁定' if book.locked else '🔓 未锁定'}")
        head.setEnabled(False)
        menu.addSeparator()
        goto_act = menu.addAction("↪ 跳转到该月")
        lock_label = "🔓 解除锁定" if book.locked else "🔒 锁定该月"
        lock_act = menu.addAction(lock_label)
        chosen = menu.exec(self.history.mapToGlobal(pos))
        if chosen is goto_act:
            self._go(y, m)
        elif chosen is lock_act:
            self._toggle_lock_history_month(y, m, book.locked)

    def _toggle_lock_history_month(self, year: int, month: int, currently_locked: bool):
        """从历史月份列表右键锁定/解锁某月（不切换当前月份）。"""
        book = self.store.load(year, month)
        if book is None:
            return
        if currently_locked:
            ans = QMessageBox.question(
                self, "解锁月份",
                f"确定要解锁 {year} 年 {month} 月吗？\n解锁后该月份可以被复制、套用模板、删除、清空考勤等操作影响。")
            if ans != QMessageBox.Yes:
                return
            book.locked = False
            self.store.save(book)
            # 如果解锁的是当前月，刷新按钮状态 + 整页 UI 锁态
            if self._book and self._book.year == year and self._book.month == month:
                self._book.locked = False
                self._refresh_lock_btn()
                self._apply_lock_state(False)
            self._refresh_history()
            self._set_status(f"已解锁：{year}-{month:02d}", True)
        else:
            book.locked = True
            self.store.save(book)
            if self._book and self._book.year == year and self._book.month == month:
                self._book.locked = True
                self._refresh_lock_btn()
                self._apply_lock_state(True)
            self._refresh_history()
            self._set_status(f"已锁定：{year}-{month:02d}", True)

    def _on_year_spin(self):
        if not self._loading and self._book:
            self._go(self._year_spin.value(), self._month_spin.value())

    def _on_month_spin(self):
        if not self._loading and self._book:
            self._go(self._year_spin.value(), self._month_spin.value())

    def _shift_month(self, delta: int):
        y, m = self._year_spin.value(), self._month_spin.value()
        m += delta
        while m > 12:
            m -= 12
            y += 1
        while m < 1:
            m += 12
            y -= 1
        self._go(y, m)

    def _open_month_popup(self):
        from PySide6.QtWidgets import QMenu, QWidgetAction
        # 与网页一致的紧凑“选年月”面板（无日期格，避免大弹层遮背景）
        norm = ("QPushButton{background:#FFFFFF;border:1px solid #E6E8F0;"
                "border-radius:9px;color:#475467;font-size:13px;}"
                "QPushButton:hover{border-color:#6366F1;color:#4F46E5;}")
        high = ("QPushButton{background:#6366F1;border:none;border-radius:9px;"
                "color:#FFFFFF;font-size:13px;font-weight:700;}")
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#FFFFFF;border:1px solid #E6E8F0;padding:6px;}")
        panel = QFrame()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 8, 10, 10)
        pv.setSpacing(8)
        head = QHBoxLayout()

        def nav_b(arrow):
            b = QPushButton(arrow)
            b.setFixedSize(26, 26)
            b.setStyleSheet("QPushButton{background:#F1F2F7;border:none;border-radius:8px;"
                            "color:#475467;font-size:14px;font-weight:700;}"
                            "QPushButton:hover{background:#E6E8F0;color:#101828;}")
            return b
        prev_b, nxt_b = nav_b("‹"), nav_b("›")
        year_lab = QLabel("")
        year_lab.setAlignment(Qt.AlignCenter)
        year_lab.setStyleSheet("font-size:14px;font-weight:700;color:#101828;")
        head.addWidget(prev_b)
        head.addWidget(year_lab, 1)
        head.addWidget(nxt_b)
        pv.addLayout(head)
        grid = QGridLayout()
        grid.setSpacing(6)
        buttons = []
        for m in range(1, 13):
            b = QPushButton(f"{m} 月")
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(34)
            grid.addWidget(b, (m - 1) // 4, (m - 1) % 4)
            buttons.append(b)
        pv.addLayout(grid)
        state = {"year": self._year_spin.value()}

        def paint():
            year_lab.setText(f"{state['year']} 年")
            for m in range(1, 13):
                cur = state["year"] == self._year_spin.value() and m == self._month_spin.value()
                buttons[m - 1].setStyleSheet(high if cur else norm)

        def shift(d):
            state["year"] += d
            paint()
        prev_b.clicked.connect(lambda: shift(-1))
        nxt_b.clicked.connect(lambda: shift(1))

        def pick(m):
            y = state["year"]
            menu.close()
            if (y, m) != (self._year_spin.value(), self._month_spin.value()):
                self._go(y, m)
        for m in range(1, 13):
            buttons[m - 1].clicked.connect(lambda _=False, mm=m: pick(mm))
        paint()
        act = QWidgetAction(menu)
        act.setDefaultWidget(panel)
        menu.addAction(act)
        btn = self._month_btn
        menu.popup(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _refresh_month_label(self):
        if hasattr(self, "_month_btn"):
            self._month_btn.setText(
                f"{self._year_spin.value()} 年 {self._month_spin.value()} 月 ▾")
        self._refresh_lock_btn()

    def _refresh_lock_btn(self):
        """根据当前 book.locked 切换 🔒/🔓 显示与样式。"""
        if not hasattr(self, "_lock_btn") or self._book is None:
            return
        if self._book.locked:
            self._lock_btn.setText("🔒")
            self._lock_btn.setToolTip(
                f"{self._book.year}-{self._book.month:02d} 已锁定\n"
                "点击解锁（解锁后允许复制/套用模板/删除/清空考勤）")
            self._lock_btn.setStyleSheet(
                "QPushButton{background:#FEF4E6;border:1px solid #FEDF89;border-radius:8px;"
                "color:#B54708;font-size:14px;font-weight:700;padding:4px 8px;}"
                "QPushButton:hover{background:#FEF3E0;}")
        else:
            self._lock_btn.setText("🔓")
            self._lock_btn.setToolTip(
                f"{self._book.year}-{self._book.month:02d} 未锁定\n"
                "点击锁定（锁定后不会被复制/套用模板等操作影响）")
            self._lock_btn.setStyleSheet(
                "QPushButton{background:#FFFFFF;border:1px solid #E6E8F0;border-radius:8px;"
                "color:#475467;font-size:14px;font-weight:700;padding:4px 8px;}"
                "QPushButton:hover{background:#F8FAFC;}")

    def _toggle_lock_current_month(self):
        """切换当前月份的锁定状态（带确认 + 写盘）。"""
        if not self._book:
            return
        b = self._book
        if b.locked:
            # 解锁：二次确认，避免误操作（锁定状态是"高枕无忧"，解了就失去保护）
            ans = QMessageBox.question(
                self, "解锁月份",
                f"确定要解锁 {b.year} 年 {b.month} 月吗？\n解锁后该月份可以被复制、套用模板、删除、清空考勤等操作影响。")
            if ans != QMessageBox.Yes:
                return
            b.locked = False
            self.store.save(b)
            self._refresh_lock_btn()
            self._set_status(f"已解锁：{b.year}-{b.month:02d}", True)
        else:
            # 锁定：要求至少有数据（防止误操作锁定空白月份）
            has_data = (b.pay_items or b.fixed_overtime_wage > 0
                        or any(d.status or d.mark or d.overtime_hours or d.leave_hours for d in b.days))
            if not has_data:
                ans = QMessageBox.question(
                    self, "锁定空白月份",
                    f"{b.year} 年 {b.month} 月没有任何数据，确定锁定吗？\n"
                    "通常建议先填写数据再锁定。")
                if ans != QMessageBox.Yes:
                    return
            b.locked = True
            self.store.save(b)
            self._refresh_lock_btn()
            self._set_status(f"已锁定：{b.year}-{b.month:02d} · 不再被复制/套用模板等操作影响", True)
        # 立即把整页 UI 锁态同步到新状态（无需切月才生效）
        self._apply_lock_state(bool(self._book.locked))

    def _new_month(self):
        now = datetime.now()
        self._go(now.year, now.month)

    def _delete_month(self):
        if not self._book:
            return
        if self._book.locked:
            QMessageBox.warning(
                self, "月份已锁定",
                f"{self._book.year} 年 {self._book.month} 月已锁定，无法删除。\n请先在月份按钮旁点击 🔒 解锁后再操作。")
            self._set_status("已取消：月份已锁定", False)
            return
        ans = QMessageBox.question(
            self, "删除月份",
            f"确定删除 {self._book.year} 年 {self._book.month} 月的记录吗？此操作不可恢复。")
        if ans == QMessageBox.Yes:
            self.store.delete(self._book.year, self._book.month)
            self._go(self._book.year, self._book.month)
            self._set_status("已删除", True)

    def _apply_lock_state(self, locked: bool):
        """统一处理「锁定只读」状态：
        * UI 层：保存按钮、删除本月按钮 disabled；各页面 _set_xxx_locked
        * API 层：_is_locked 拦截 _changed / _flush_changed / _manual_save 等所有写入入口
        锁定的月份只能查看，保留导出 Excel 与切换月份能力。
        """
        self._is_locked = bool(locked)
        # —— 顶部保存按钮：锁定时禁用 ——
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(not self._is_locked)
            if self._is_locked:
                self.save_btn.setToolTip("月份已锁定，无法保存")
            else:
                self.save_btn.setToolTip("")
        # —— 各页面锁定模式（每个 mixin 实现自己的 _set_xxx_locked，避免方法名冲突）——
        for hook in ("_set_params_locked", "_set_calendar_locked", "_set_salary_locked"):
            fn = getattr(self, hook, None)
            if callable(fn):
                fn(self._is_locked)
        # —— 删除本月按钮：锁定时禁用（即便 _delete_month 内有拦截，UI 一并禁用更明显）——
        for child in self.findChildren(QPushButton):
            if child.objectName() == "danger":
                child.setEnabled(not self._is_locked)

    # ================= 载入/重建 =================

    def _go(self, year: int, month: int):
        # 切换月份前先 flush，避免未保存的改动随旧 _book 写盘/丢失
        if self._dirty:
            self._flush_changed()
        self._loading = True
        # 切月后所有页都按新 book 重新画，旧版本号全部失效
        self._data_version = 0
        self._rendered_versions.clear()
        book = self.store.load(year, month)
        if book is None:
            book = model.create_book(year, month, with_common_pay_items=True)
            err = getattr(self.store, "last_error", None)
            if err:
                self._set_status(f"读取失败（{err}），已新建空账本；原文件未删除", False)
            else:
                self._set_status("新月份：填写后自动保存", True)
        else:
            self._set_status("已载入历史记录", True)
        self._book = book
        self._year_spin.setValue(year)
        self._month_spin.setValue(month)
        self.side_month.setText(f"{year} 年 {month} 月")
        self._refresh_month_label()
        self._build_pages()
        self._annual_year = year  # 切月后年度汇总跟随当前账本年份
        self._loading = False
        self._recalc()
        self._refresh_history()
        # 锁定只读：切月后立即把状态机推到对应模式（UI + API）
        self._apply_lock_state(bool(self._book.locked))

    def _build_pages(self):
        # 参数
        if not hasattr(self, "_params_ready"):
            self._init_page_widgets()
        # 每次重建内容
        self._fill_overview()
        self._fill_params()
        self._fill_calendar()
        self._fill_salary()
        self._fill_report()

    def _init_page_widgets(self):
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        # params
        self.params_scroll = QScrollArea()
        self.params_scroll.setWidgetResizable(True)
        self.params_scroll.setFrameShape(QFrame.NoFrame)
        self.params_root = QWidget()
        self.params_scroll.setWidget(self.params_root)

        def _scroll_for(w: QWidget) -> QScrollArea:
            a = QScrollArea()
            a.setWidgetResizable(True)
            a.setFrameShape(QFrame.NoFrame)
            a.setWidget(w)
            return a

        # overview（工作台）
        self.overview_page = QWidget()
        self.overview_area = _scroll_for(self.overview_page)
        # calendar（考勤）
        self.calendar_page = QWidget()
        self.calendar_area = _scroll_for(self.calendar_page)
        # salary（薪酬）
        self.salary_root = QWidget()
        self.salary_area.setWidget(self.salary_root)
        # report（报表）
        self.report_page = QWidget()
        self.report_area = _scroll_for(self.report_page)
        # annual（年度汇总）：进入页面时才填充
        self.annual_page = QWidget()
        self.annual_lay = QVBoxLayout(self.annual_page)
        self.annual_lay.setContentsMargins(16, 12, 16, 18)
        self.annual_lay.setSpacing(12)
        self._annual_year = None

        self.pages_widget = [self.overview_area, self.calendar_area, self.salary_area,
                             self.params_scroll, self.report_area, self.annual_page]
        for w in self.pages_widget:
            self.stack.addWidget(w)
        self._params_ready = True

    # ---------- 字段辅助（小标签 + 控件的纵向 box）----------

    @staticmethod
    def _field(label: str, w: QWidget):
        box = QVBoxLayout()
        box.setSpacing(3)
        lab = QLabel(label)
        lab.setObjectName("fldLabel")
        box.addWidget(lab)
        box.addWidget(w)
        return box

    def _on_numeric(self, attr):
        if self._loading or not self._book:
            return
        if self._is_locked:
            return  # 锁定只读：API 层也屏蔽
        if attr not in self._param_spins:
            return
        setattr(self._book, attr, self._param_spins[attr].value())
        self._changed()
        # 合规判定 UI 已从参数页移除，不再刷新该卡片

    def _on_note(self, text):
        if self._loading or not self._book:
            return
        if self._is_locked:
            return  # 锁定只读：API 层也屏蔽
        self._book.note = text
        self._changed()

    # ---------- 参数模板 ----------

    def _tpl_path(self):
        return os.path.join(self.store.dir, "templates.json")

    def _render_one_page(self, page_idx: int, r):
        """按需渲染单个重数据页（被 _render_all 和 _show_page 共用）。"""
        if page_idx == 0:
            self._render_overview(r)
        elif page_idx == 4:
            self._render_report(r)

    def _recalc(self):
        if self._book is None:
            return
        try:
            r = calc.compute(self._book)
            self._render_all(r)
        except Exception as ex:
            self._set_status("出错：" + str(ex), False)
            traceback.print_exc()

    def _render_all(self, r):
        """只刷新当前可见页 + 始终刷新的轻量统计。
        避免每次 _changed 都把全部 6 个页面的 widget 拆掉重建。"""
        self._last_result = r
        self._data_version += 1
        # 始终：薪酬 strip / 日历 chip 都要拿到新 _last_result
        if hasattr(self, "_cal_chip_labs"):
            self._update_cal_count()
        if self._current_page_idx == 2:  # salary
            self._sync_salary_ui()
        # 仅当前页做布局级重建
        if self._current_page_idx in (0, 4):
            self._render_one_page(self._current_page_idx, r)
            self._rendered_versions[self._current_page_idx] = self._data_version
        # annual / params / calendar 各自管自己的 widget，年度汇总靠 _fill_annual 在切页时刷新

    def _changed(self):
        """用户输入后：立即刷新可见统计 + 调度合并保存。
        calc 本身是轻量的，widget 重建和写盘才是大头，所以只对后者做合并。
        锁定月份时该 API 整体屏蔽（spin 即使没被 disable，回调也无副作用）。"""
        if self._loading or not self._book:
            return
        if self._is_locked:
            return  # 锁定只读：不重算、不刷新、不调度保存
        self._dirty = True
        try:
            r = calc.compute(self._book)
            self._last_result = r
            self._data_version += 1
            if hasattr(self, "_cal_chip_labs"):
                self._update_cal_count()
            if self._current_page_idx == 2:  # salary
                self._sync_salary_ui()
        except Exception:
            # 静默：合并定时器里会再算一次并报告错误
            pass
        # 150ms 内连改只触发一次：写盘 + 重建报表/概览（如可见）
        self._change_timer.start()

    def _flush_changed(self):
        """合并定时器到点：跑一次真正的重算 + 渲染 + 写盘。
        锁定月份：不写盘，但允许做只读 render（让刷新继续可用）。"""
        self._change_timer.stop()
        if self._loading or not self._book:
            self._dirty = False
            return
        try:
            r = calc.compute(self._book)
            if self._is_locked:
                # 只读模式：只刷新可见统计，不写盘、不置 dirty
                self._last_result = r
                self._data_version += 1
                if hasattr(self, "_cal_chip_labs"):
                    self._update_cal_count()
                if self._current_page_idx == 2:
                    self._sync_salary_ui()
                return
            self._render_all(r)
            self.store.save(self._book)
            self._set_status("已保存 " + datetime.now().strftime("%H:%M:%S"), True)
            self._dirty = False
        except Exception as ex:
            self._set_status("出错：" + str(ex), False)
            traceback.print_exc()

    def _show_about(self):
        """关于 / 免责声明。"""
        QMessageBox.about(
            self, "关于 · 工资考勤表",
            "<h3>工资考勤表（Attendance Desktop）</h3>"
            "<p>本地离线 · 月度考勤与工资核算工具（Python / PySide6）</p>"
            "<p>开源许可：<b>GNU General Public License v3.0</b></p>"
            "<hr>"
            "<p><b>免责声明</b><br>"
            "本软件为免费开源工具，仅作工资核算参考，不构成法律 / 税务 / 财务意见。<br>"
            "内置的节假日、最低工资等数据请以官方最新发布为准；"
            "社保 / 公积金 / 个税等参数需按当地政策自行核对。<br>"
            "<b>用于正式发薪前请务必人工复核。</b></p>")

    def _set_status(self, text, ok=True):
        if not hasattr(self, "status_label"):
            return
        self.status_label.setText(text)
        self.status_label.setObjectName("statusOk" if ok else "statusErr")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _manual_save(self):
        if not self._book:
            return
        if self._is_locked:
            self._set_status("月份已锁定，无法保存", False)
            return
        # 若有合并中的改动，先 flush 再保存
        if self._dirty:
            self._flush_changed()
            return
        self.store.save(self._book)
        self._set_status("已保存 " + datetime.now().strftime("%H:%M:%S"), True)

    # ---------- 工具 ----------

    def _clear_layout(self, layout):
        # 递归清空：嵌套子布局被 takeAt 摘除后其中的控件会失去布局管理，
        # 若不递归删除会残留为“幽灵控件”叠加绘制在页面上（背景杂块的来源）。
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                self._clear_layout(sub)
                sub.deleteLater()
