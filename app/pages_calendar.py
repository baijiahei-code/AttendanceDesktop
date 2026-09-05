"""考勤页渲染：彩色月历/当日面板/状态与加班编辑/一键铺。"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QGridLayout,
    QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QVBoxLayout, QSizePolicy,
)

from . import model, wages
from .ui import DAY_PALETTE, STATUS_ORDER, NumberSpin
from .widgets import Card


class CalendarPageMixin:
    def _fill_calendar(self):
        b = self._book
        page = self.calendar_page
        if not hasattr(self, "_calendar_lay"):
            self._calendar_lay = QVBoxLayout(page)
            self._calendar_lay.setContentsMargins(18, 14, 18, 18)
            self._calendar_lay.setSpacing(12)
        lay = self._calendar_lay
        self._clear_layout(lay)
        # 锁定月：批量禁用以下修改类控件
        self._calendar_modify_widgets: list = []
        # 由 Card 承载的卡片（用于统一锁定）
        self._calendar_cards: list[Card] = []

        # —— 🔒 只读模式提示横幅（锁定时才显示）——
        self._lock_banner = QLabel("🔒  当前月份已锁定 · 仅供查看，所有修改操作已屏蔽")
        self._lock_banner.setStyleSheet(
            "background:#FEF4E6;color:#B54708;border:1px solid #FEDF89;"
            "border-radius:8px;padding:8px 14px;font-weight:600;font-size:13px;")
        self._lock_banner.setWordWrap(True)
        self._lock_banner.hide()
        lay.addWidget(self._lock_banner)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        fill_btn = QPushButton("✨ 一键铺（周末休/工作日上）")
        fill_btn.setToolTip(
            "按普通日历铺设：周末标为休息，其余工作日标为上班。"
            "法定节假日/调休请使用旁边的「API 一键铺」。"
            "已填过的日期不会被覆盖。")
        fill_btn.setStyleSheet(
            "QPushButton{background:#EEF2FF;color:#4F46E5;border:1px solid #C7D2FE;"
            "border-radius:9px;padding:5px 10px;font-weight:600;}"
            "QPushButton:hover{background:#E0E7FF;}")
        fill_btn.clicked.connect(self._fill_default_calendar)
        api_fill_btn = QPushButton("🌐 API 一键铺（法定节假日/调休）")
        api_fill_btn.setToolTip(
            "优先调用 API 获取某年节假日/调休安排（失败用内置表），"
            "只铺设周末、法定节假日、调休三类日期，其余日期保持不变。")
        api_fill_btn.setStyleSheet(
            "QPushButton{background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0;"
            "border-radius:9px;padding:5px 10px;font-weight:600;}"
            "QPushButton:hover{background:#D1FAE5;}")
        api_fill_btn.clicked.connect(self._api_fill_holidays)
        clear_btn = QPushButton("清空考勤")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear_days)
        bar.addStretch(1)
        bar.addWidget(api_fill_btn)
        bar.addWidget(fill_btn)
        bar.addWidget(clear_btn)
        lay.addLayout(bar)
        self._calendar_modify_widgets.extend([fill_btn, api_fill_btn, clear_btn])

        chip_meta = [("work", "上班"), ("rest", "休息"), ("personal", "事假"),
                     ("sick", "病假"), ("family", "婚/丧/产/年假"),
                     ("holi", "法定节假日"), ("labor", "提供正常劳动"),
                     ("ot", "加班"), ("leave", "请假")]
        self._cal_chip_names = dict(chip_meta)
        self._cal_chip_labs = {}
        cg = QGridLayout()
        cg.setHorizontalSpacing(6)
        cg.setVerticalSpacing(6)
        for i, (k, t) in enumerate(chip_meta):
            lab = QLabel(f"{t} 0")
            lab.setStyleSheet(
                "background:#F8FAFC;border:1px solid #E6E8F0;border-radius:999px;"
                "color:#475467;padding:4px 8px;font-size:11px;font-weight:600;min-height:24px;")
            self._cal_chip_labs[k] = lab
            cg.addWidget(lab, i // 5, i % 5)
        lay.addLayout(cg)

        row = QHBoxLayout()
        row.setSpacing(14)

        # —— 月历卡片（Card 化）——
        cal_card = Card(title=f"考勤 · {b.year} 年 {b.month} 月",
                        variant="default", margins=(14, 12, 14, 12))
        cv = cal_card.body_layout()
        cv.setSpacing(8)
        self.day_grid = QGridLayout()
        self.day_grid.setSpacing(5)
        cv.addLayout(self.day_grid)
        leg = QHBoxLayout()
        leg.setSpacing(6)
        for s in STATUS_ORDER:
            bg, fg = DAY_PALETTE[s]
            lab = QLabel(s)
            lab.setStyleSheet(
                f"background:{bg};color:{fg};border-radius:4px;padding:1px 7px;font-size:10px;font-weight:600;")
            leg.addWidget(lab)
        leg.addStretch(1)
        cv.addLayout(leg)
        row.addWidget(cal_card, 1)
        self._calendar_cards.append(cal_card)

        # —— 右侧当日编辑面板（Card 化）——
        self.sel_day = 0
        self.edit_panel = self._build_day_panel()
        row.addWidget(self.edit_panel, 0)
        lay.addLayout(row, 1)
        # 编辑面板也是 Card，参与统一锁定
        self._calendar_cards.append(self.edit_panel)
        # 收集右侧面板所有可写控件（Card 已自动追踪，这里保留兼容旧 API）
        self._calendar_modify_widgets.extend([
            self.status_clear, *self.status_btns,
            self.panel_ot, self.panel_lv, self.panel_mark,
        ])

        self._render_calendar()

    def _set_calendar_locked(self, locked: bool):
        """锁定只读模式：所有 Card 一键禁用 + 顶栏按钮 + 日期格子禁用。"""
        # 1) 2 张卡片统一禁用内部交互
        for card in getattr(self, "_calendar_cards", []):
            try:
                card.set_locked(locked)
            except Exception:
                pass
        # 2) 非卡片控件（顶栏按钮）
        for w in getattr(self, "_calendar_modify_widgets", []):
            try:
                w.setEnabled(not locked)
            except Exception:
                pass
        # 3) 日期格子按钮单独处理（它们不是 Card 的追踪对象）
        if hasattr(self, "_day_btns"):
            for bt in self._day_btns.values():
                try:
                    bt.setEnabled(not locked)
                except Exception:
                    pass
        # 4) 锁定横幅
        if hasattr(self, "_lock_banner") and self._lock_banner is not None:
            self._lock_banner.setVisible(bool(locked))

    def _build_day_panel(self):
        panel = Card(title="", variant="default", margins=(14, 12, 14, 12))
        # 允许编辑面板在窄窗口时收缩，但保持最小可用宽度
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(420)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        pl = panel.body_layout()
        pl.setSpacing(7)
        self.panel_title = QLabel("选择日期")
        self.panel_title.setObjectName("cardTitle")
        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        self.panel_sub = QLabel("")
        self.panel_sub.setStyleSheet("color:#98A2B3;font-size:11px;")
        head_row.addWidget(self.panel_title)
        head_row.addStretch(1)
        head_row.addWidget(self.panel_sub)
        pl.addLayout(head_row)

        pl.addWidget(self._fld_label("出勤状态"))
        self.status_group = QButtonGroup(self)
        self.status_group.setExclusive(True)
        chips = QGridLayout()
        chips.setSpacing(5)
        self.status_clear = QPushButton("未填")
        self.status_clear.setCheckable(True)
        self.status_clear.setObjectName("chip")
        self.status_clear.setCursor(Qt.PointingHandCursor)
        self.status_clear.setMinimumHeight(28)
        self.status_group.addButton(self.status_clear, -1)
        chips.addWidget(self.status_clear, 0, 0)
        for i, s in enumerate(STATUS_ORDER):
            btn = QPushButton(s)
            btn.setCheckable(True)
            btn.setObjectName("chip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(28)
            self.status_group.addButton(btn, i)
            chips.addWidget(btn, (i + 1) // 4, (i + 1) % 4)
        self.status_group.idClicked.connect(self._on_pick_status)
        pl.addLayout(chips)
        self.status_btns = self.status_group.buttons()
        # 把整组 chips（含所有 status_btns）交给 Card 追踪，
        # 否则 set_locked 时按钮不会被禁用。
        panel.track_extra(chips)

        hrow = QHBoxLayout()
        hrow.setSpacing(10)
        ot = NumberSpin(decimals=1, step=0.5, minimum=0, compact=False)
        ot.setSuffix(" 小时")
        lv = NumberSpin(decimals=1, step=0.5, minimum=0, compact=False)
        lv.setSuffix(" 小时")
        ot.valueChanged.connect(lambda v: self._on_pick_hours(v, True))
        lv.valueChanged.connect(lambda v: self._on_pick_hours(v, False))
        v1 = self._field("加班 +", ot)
        v2 = self._field("请假 -", lv)
        hrow.addLayout(v1)
        hrow.addLayout(v2)
        pl.addLayout(hrow)
        # 加班/请假 spin 走 _field 包装在嵌套 layout 里 → 显式 track
        panel.track_extra(hrow)
        self.panel_ot, self.panel_lv = ot, lv

        mk = QComboBox()
        for lab_txt in model.MARK_LABELS:
            mk.addItem(lab_txt if lab_txt else "（无标记）")
        mk.currentIndexChanged.connect(self._on_pick_mark)
        pl.addLayout(self._field("标记", mk))
        # mark combo 也在嵌套 layout 里 → 显式 track
        panel.track_extra(mk)
        self.panel_mark = mk

        self.panel_footer = QLabel("")
        self.panel_footer.setObjectName("secHint")
        self.panel_footer.setWordWrap(True)
        pl.addWidget(self.panel_footer)
        pl.addStretch(1)
        return panel

    @staticmethod
    def _fld_label(text):
        lab = QLabel(text)
        lab.setObjectName("fldLabel")
        return lab

    def _render_calendar(self):
        b = self._book
        grid = self.day_grid
        if hasattr(self, "_day_btns"):
            for bt in self._day_btns.values():
                bt.deleteLater()
        self._day_btns = {}
        while grid.count():
            grid.takeAt(0)
        for i, wn in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            lab = QLabel(wn)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet("color:#98A2B3;font-size:11px;font-weight:700;")
            grid.addWidget(lab, 0, i)
        offset = date(b.year, b.month, 1).weekday()  # 0=周一
        cell = offset
        for ent in b.days:
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(60)
            btn.setMinimumWidth(50)
            row = cell // 7 + 1
            col = cell % 7
            cell += 1
            btn.clicked.connect(lambda _=False, day=ent.day: self._select_day(day))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _pos, day=ent.day: self._show_day_menu(day))
            grid.addWidget(btn, row, col)
            self._day_btns[ent.day] = btn
        self._select_day(self.sel_day if self.sel_day else 1)
        self._update_cal_count()

    def _style_day_btn(self, btn, ent):
        is_sel = ent.day == self.sel_day
        is_wk = ent.is_weekend_dt(self._book.year, self._book.month)
        bg, fg = DAY_PALETTE.get(ent.status or "", ("#FCFCFD", "#475569"))
        border = ("2px solid #6366F1" if is_sel
                  else ("1px dashed #FDA29B" if is_wk and not ent.status else "1px solid #E6E8F0"))
        seg = [str(ent.day)]
        mid = []
        if ent.status:
            mid.append(ent.status)
        if ent.mark == 1:
            mid.append("法定节")
        elif ent.mark == 2:
            mid.append("计劳动")
        seg.append(" · ".join(mid) if mid else "未填")
        bd = []
        if ent.overtime_hours:
            bd.append(f"+{ent.overtime_hours:g}h")
        if ent.leave_hours:
            bd.append(f"-{ent.leave_hours:g}h")
        seg.append("  ".join(bd))
        btn.setText("\n".join(seg))
        btn.setStyleSheet(
            f"QPushButton{{background:{bg};color:{fg};border:{border};border-radius:9px;"
            f"padding:3px 2px;font-size:10.5px;font-weight:600;text-align:center;}}"
            "QPushButton:hover{border:2px solid #6366F1;}")

    def _select_day(self, day):
        if not self._book or day not in self._day_btns:
            return
        self.sel_day = day
        b = self._book
        ent = b.day(day)
        for d, bt in self._day_btns.items():
            self._style_day_btn(bt, b.day(d))
        wd = ["一", "二", "三", "四", "五", "六", "日"][date(b.year, b.month, day).weekday()]
        suffix = "（周末）" if ent.is_weekend_dt(b.year, b.month) else ""
        self.panel_title.setText(f"{day} 日 · 周{wd}{suffix}")
        self.panel_sub.setText(f"{b.year}-{b.month:02d}-{day:02d}")
        # 同步控件（block 避免误触发保存；保存/恢复 _loading，不破坏外层加载保护）
        prev_loading = self._loading
        self._loading = True
        self.status_clear.setChecked(not ent.status)
        for bt in self.status_btns:
            if bt is self.status_clear:
                continue
            bt.setChecked(bt.text() == ent.status)
        self.panel_ot.blockSignals(True)
        self.panel_lv.blockSignals(True)
        self.panel_mark.blockSignals(True)
        self.panel_ot.setValue(ent.overtime_hours)
        self.panel_lv.setValue(ent.leave_hours)
        self.panel_mark.setCurrentIndex(ent.mark)
        self.panel_ot.blockSignals(False)
        self.panel_lv.blockSignals(False)
        self.panel_mark.blockSignals(False)
        self._loading = prev_loading

    def _on_pick_status(self, idx):
        if self._loading or not self._book or not self.sel_day:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        self._book.day(self.sel_day).status = "" if idx < 0 else STATUS_ORDER[idx]
        self._after_day_change(self.sel_day)

    def _on_pick_mark(self, idx):
        if self._loading or not self._book or not self.sel_day:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        self._book.day(self.sel_day).mark = idx
        self._after_day_change(self.sel_day)

    def _on_pick_hours(self, value, is_ot):
        if self._loading or not self._book or not self.sel_day:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        ent = self._book.day(self.sel_day)
        if is_ot:
            ent.overtime_hours = value
        else:
            ent.leave_hours = value
        self._after_day_change(self.sel_day)

    def _after_day_change(self, day):
        bt = self._day_btns.get(day)
        if bt is not None:
            self._style_day_btn(bt, self._book.day(day))
        self._update_cal_count()
        self._changed()

    def _update_cal_count(self):
        r = self._last_result
        if r is None or not hasattr(self, "_cal_chip_labs"):
            return
        c = r.counts
        fam = (c.marriage_leave + c.bereavement_leave
               + c.maternity_leave + c.annual_leave)
        vals = {
            "work": str(c.work), "rest": str(c.rest),
            "personal": str(c.personal_leave), "sick": str(c.sick_leave),
            "family": str(fam), "holi": str(c.legal_holiday),
            "labor": str(c.normal_labor_days),
            "ot": f"{r.total_daily_ot_hours:.1f}h",
            "leave": f"{r.daily_leave_hours:.1f}h",
        }
        names = self._cal_chip_names
        for k, lab in self._cal_chip_labs.items():
            lab.setText(f"{names.get(k, k)} {vals.get(k, '')}")

    def _fill_default_calendar(self):
        """普通一键铺：只区分周末/工作日，不处理法定节假日与调休。
        - 空白周末 → 休息
        - 空白工作日（周一到周五）→ 上班
        已填过的日期不覆盖。法定节假日和调休的精确铺法请用 API 一键铺。
        """
        if self._loading or not self._book:
            return
        if getattr(self, "_is_locked", False):
            self._set_status("月份已锁定，无法一键铺", False)
            return
        y, m = self._book.year, self._book.month
        wk_count = 0
        work_count = 0
        for d in self._book.days:
            if d.status:
                continue
            if d.is_weekend_dt(y, m):
                d.status = "休息"
                wk_count += 1
            else:
                d.status = "上班"
                work_count += 1
        self._render_calendar()
        self._changed()
        if wk_count or work_count:
            self._set_status(f"已铺设：工作日上班 {work_count} 天，周末休息 {wk_count} 天（已填日期未覆盖）", True)
        else:
            self._set_status("本月没有可铺设的空白日期", True)

    def _api_fill_holidays(self):
        """API 一键铺：调用 API（失败 fallback 本地），只铺三类日期，其余保持不变。
        处理对象：
          - makeup 调休补班日 → 强制 status=上班
          - statutory 法定节假日 → 强制 status=休息 + mark=1（×3加班）
          - rest 放假调休日（除法定已处理） → 强制 status=休息
          - 周末 → 强制 status=休息
        已填日期 **会被覆盖**（节假日/调休类日期需要精确值）。
        """
        if self._loading or not self._book:
            return
        if getattr(self, "_is_locked", False):
            self._set_status("月份已锁定，无法 API 铺设", False)
            return
        y, m = self._book.year, self._book.month
        settings = self.store.load_settings()
        api_url = settings.get("api_url", "")
        api_key = settings.get("api_key", "")
        api_model = settings.get("api_model") or None
        data = wages.fetch_holidays(api_url, api_key, y, api_model=api_model)
        if data is None:
            self._set_status(f"{y} 年节假日数据未找到（API 和本地表都没有），无法铺设", False)
            return
        statutory = set(data.get("statutory", []))
        rest = set(data.get("rest", []))
        makeup = set(data.get("makeup", []))
        source = data.get("source", "?")
        changed_count = 0
        for d in self._book.days:
            key = f"{m:02d}-{d.day:02d}"
            is_weekend = d.is_weekend_dt(y, m)
            old_status = d.status
            old_mark = d.mark
            new_status = None
            new_mark = d.mark
            if key in makeup:
                # 调休补班日：上班
                new_status = "上班"
            elif key in statutory:
                # 法定节假日：休息 + 法定标记
                new_status = "休息"
                new_mark = 1
            elif key in rest:
                # 放假调休区间（非法定的拼假休息日）：休息
                new_status = "休息"
            elif is_weekend:
                # 普通周末：休息
                new_status = "休息"
            if new_status is not None and (old_status != new_status or old_mark != new_mark):
                d.status = new_status
                d.mark = new_mark
                changed_count += 1
        self._render_calendar()
        self._changed()
        tag = "API" if source == "api" else "本地"
        self._set_status(
            f"节假日铺设完成 · {tag} 来源 · {y} 年 · 影响 {changed_count} 天", True)

    def _show_day_menu(self, day):
        """日历格子右键：快捷设置状态 / 法定节假日标记。"""
        if self._loading or not self._book or day not in self._day_btns:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读：右键菜单直接不开
        self._select_day(day)
        menu = QMenu(self)
        head = menu.addAction(f"{self._book.year}-{self._book.month:02d}-{day:02d}")
        head.setEnabled(False)
        menu.addSeparator()
        status_actions = [(menu.addAction("未填"), "")]
        for s in STATUS_ORDER:
            status_actions.append((menu.addAction(s), s))
        menu.addSeparator()
        ent = self._book.day(day)
        mark_action = menu.addAction("标记为法定节假日" if ent.mark != 1 else "取消法定节假日标记")
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        if chosen is mark_action:
            ent.mark = 0 if ent.mark == 1 else 1
        else:
            for act, s in status_actions:
                if act is chosen:
                    ent.status = s
                    break
        self._after_day_change(day)
        self._select_day(day)

    def _clear_days(self):
        if self._loading or not self._book:
            return
        if self._book.locked:
            QMessageBox.warning(
                self, "月份已锁定",
                f"{self._book.year} 年 {self._book.month} 月已锁定，无法清空考勤。\n请先在月份按钮旁点击 🔓 解锁后再操作。")
            return
        ans = QMessageBox.question(
            self, "清空考勤", "确定清空本月所有出勤状态与加班/请假记录吗？")
        if ans != QMessageBox.Yes:
            return
        for d in self._book.days:
            d.status = ""
            d.mark = 0
            d.overtime_hours = 0.0
            d.leave_hours = 0.0
        self._render_calendar()
        self._changed()
