"""薪酬构成页渲染：工资项列表 / 加班工资 / 个人扣除 / 顶部金额 strip / 小计同步。

设计要点：
* 视觉/列宽/加班倍率/按钮配色……所有「用户可能想调」的常量都在 :mod:`app.config`。
* 单条工资项 UI 收在 :class:`widgets.PayItemRow`。
* 添加菜单收在 :class:`widgets.PayItemCatalogMenu`。
* 左卡（标题+列头+行列表）收在 :class:`widgets.PayItemListWidget`。
* 加班 / 个人扣除 / 顶部 strip 也分别有自己的 widget。
* 本 mixin 只做：页面级连线 ↔ 调用 widget ↔ 同步 ↔ 状态协调。

想换样式 → 改 :mod:`app.config`（配色 / 列宽 / 加班倍率）+ :mod:`style.py`（QSS）。
想加 1 条新的工资项分类 → 改 :mod:`model.PAYITEM_TYPES` + :data:`model.PAYITEM_CATALOG`。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QMessageBox, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from . import model
from .widgets import (
    DeductionCardWidget, OvertimeCardWidget, PayItemListWidget, SalaryStripWidget,
)


class SalaryPageMixin:
    # ---------------------------------------------------------------------
    # 整页布局
    # ---------------------------------------------------------------------
    def _fill_salary(self):
        b = self._book
        root = self.salary_root

        # —— 整个 salary 页的纵向 layout（首次进入时构造）——
        if not hasattr(self, "_salary_lay"):
            self._salary_lay = QVBoxLayout(root)
            self._salary_lay.setContentsMargins(16, 12, 16, 18)
            self._salary_lay.setSpacing(12)
        lay = self._salary_lay
        self._clear_layout(lay)
        # 锁定月：批量禁用以下修改类控件
        self._salary_modify_widgets: list = []

        # —— 🔒 只读模式提示横幅（锁定时才显示）——
        self._lock_banner = QLabel("🔒  当前月份已锁定 · 仅供查看，所有修改操作已屏蔽")
        self._lock_banner.setStyleSheet(
            "background:#FEF4E6;color:#B54708;border:1px solid #FEDF89;"
            "border-radius:8px;padding:8px 14px;font-weight:600;font-size:13px;")
        self._lock_banner.setWordWrap(True)
        self._lock_banner.hide()
        lay.addWidget(self._lock_banner)

        # —— 顶部金额 strip ——
        self._salary_strip = SalaryStripWidget()
        lay.addWidget(self._salary_strip)

        # —— 两栏：左 工资项；右 加班+扣除 ——
        body = QHBoxLayout()
        body.setSpacing(14)

        # 左：工资项列表卡片
        self.pay_items = PayItemListWidget()
        self.pay_items.changed.connect(self._pi_touched)
        self.pay_items.copy_requested.connect(self._on_copy_pay_items)
        self.pay_items.insert_requested_at.connect(
            lambda _i: self._focus_new_row(self.pay_items))
        self.pay_items.set_add_callback(self._add_pay_item_at_back_of_type)
        self.pay_items.set_remove_callback(self._on_pay_item_removed)
        body.addWidget(self.pay_items, 1)

        # 右：加班 / 个人扣除
        right = QWidget()
        right.setMinimumWidth(300)
        right.setMaximumWidth(520)
        right.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(14)
        self._ot_card = OvertimeCardWidget(b)
        self._ded_card = DeductionCardWidget(b)
        rv.addWidget(self._ot_card)
        rv.addWidget(self._ded_card)
        rv.addStretch(1)
        body.addWidget(right, 0)

        lay.addLayout(body, 1)

        # —— 给所有 spin / 复选框接联动：写回 book + 触发刷新 ——
        self._salary_spins: dict = {}
        self._salary_spins.update(self._ot_card.spins)
        self._salary_spins.update(self._ded_card.spins)
        for attr, sp in self._salary_spins.items():
            sp.valueChanged.connect(lambda _v, a=attr: self._on_salary_attr(a))
        # 加班数三档被 ot_auto 锁开关控制时启用状态
        self._ot_auto_chk = self._get_ot_auto_chk()    # 参数页是开关源；薪酬页只 mirror
        self._ded_card.tax_auto.toggled.connect(self._on_tax_auto)

        # 加班费基数锁按钮：复用主页面 _toggle_ot_base_lock
        self._ot_card.lock_btn.clicked.connect(self._toggle_ot_base_lock_salary)
        self._ot_base_lock_btn_salary = self._ot_card.lock_btn

        # —— 重建当月工资项 ——
        self.pay_items.rebuild_from_book(b)

        # —— 状态 & 计算 ——
        self._apply_auto_states()
        self._sync_ot_base_locked_ui_salary()
        self._update_salary_sums()
        self._sync_salary_strip()
        # 收集修改类控件（PayItemListWidget 自己的 set_locked_mode 会处理行内控件）
        self._salary_modify_widgets.extend([
            self._ot_card.lock_btn,         # 加班费基数锁按钮
            self._ded_card.tax_auto,        # 自动个税 checkbox
            *self._salary_spins.values(),   # 所有加班/扣除 spin
        ])

    def _set_salary_locked(self, locked: bool):
        """锁定只读模式：禁用所有修改类控件 + 锁定工资项列表 widget（含每行）。"""
        if hasattr(self, "_salary_modify_widgets"):
            for w in self._salary_modify_widgets:
                try:
                    w.setEnabled(not locked)
                except Exception:
                    pass
        if hasattr(self, "pay_items"):
            try:
                self.pay_items.set_locked_mode(locked)
            except Exception:
                pass
        if hasattr(self, "_lock_banner") and self._lock_banner is not None:
            self._lock_banner.setVisible(bool(locked))
        # 月份解锁（非整月只读）后：重放字段级锁，避免 ot_auto / 个税自动 / 加班基数锁
        # 对应的输入框被 setEnabled(True) 一并放开。
        if not locked:
            if hasattr(self, "_apply_auto_states"):
                try:
                    self._apply_auto_states()
                except Exception:
                    pass
            if hasattr(self, "_sync_ot_base_locked_ui_salary"):
                try:
                    self._sync_ot_base_locked_ui_salary()
                except Exception:
                    pass

    # ---------------------------------------------------------------------
    # 用户操作回调（被 widget 通过回调 / 信号转发到这里）
    # ---------------------------------------------------------------------
    def _add_pay_item_at_back_of_type(self, ptype: str, name: str | None = None):
        """菜单选择项回调：创建 + 按类型分组插入 + 焦点跳到金额框。"""
        if self._loading or not self._book:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        valid = dict(model.PAYITEM_TYPES)
        if ptype not in valid:
            ptype = "wage"
        if not name:
            used = {r.item.name for r in self.pay_items.rows}
            name = model.PAYITEM_DEFAULT_NAME.get(ptype, "工资项")
            if name in used:
                # 默认名被占：顺延到常用列表中第一个未用名
                for cand in model.PAYITEM_COMMON.get(ptype, []):
                    if cand not in used:
                        name = cand
                        break
        # 计算插入位置（同名 type 的最后一行之后，保持颜色分组）
        idx = len(self._book.pay_items)
        for i in range(len(self._book.pay_items) - 1, -1, -1):
            if self._book.pay_items[i].type == ptype:
                idx = i + 1
                break
        item = model.PayItem(name=name, type=ptype, amount=0.0)
        self._book.pay_items.insert(idx, item)
        row = self.pay_items.add_row(item, index=idx, focus_amount=True)
        self._pi_touched()
        self._set_status(f"已添加工资项：{name}（{valid[ptype]}）", True)
        return row

    def _focus_new_row(self, lw):
        """新行已可见 + 焦点 → 滚到可见区域。"""
        if lw.rows:
            lw.ensure_visible_row(lw.rows[-1])

    def _on_pay_item_removed(self, item: "model.PayItem"):
        """删除回调 —— PayItemListWidget 删行后，同步从 book.pay_items 移除。"""
        if self._book is None:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读：删除即写入，API 层也屏蔽
        try:
            self._book.pay_items.remove(item)
        except ValueError:
            pass  # 不在列表里（重复删除），忽略

    # ---------------------------------------------------------------------
    # 删除 / 改名 / 改金额 / 改类型（行 widget 已经直接改 self.item，再触发 _pi_touched）
    # ---------------------------------------------------------------------
    def _pi_touched(self):
        self._update_salary_sums()
        self._changed()
        self._sync_salary_strip()

    # _pi_delete / _pi_rename / _pi_amount / _pi_chtype 在 widget 内部直接写回
    # self.item，并通过信号传到本 mixin 的 _pi_touched。这里保留空方法以维持
    # 旧名字的兼容（未来若你写自动化测试可能用到）。
    def _pi_delete(self, *_):       pass  # 兼容：见 PayItemRow.delete_requested
    def _pi_rename(self, *_):       pass  # 兼容：见 PayItemRow.name_changed
    def _pi_amount(self, *_):       pass  # 兼容：见 PayItemRow.amount_changed
    def _pi_chtype(self, *_):       pass  # 兼容：见 PayItemRow.type_changed

    # ---------------------------------------------------------------------
    # 加班基数锁 / 自动开关
    # ---------------------------------------------------------------------
    def _get_ot_auto_chk(self) -> QCheckBox:
        """参数页是 ot_auto 开关的拥有者，薪酬页只是镜像其状态。
        若主页面尚未就绪（极少发生），返回空 CheckBox 占位。"""
        chk = getattr(self, "_ot_auto_chk_main", None)
        if isinstance(chk, QCheckBox):
            return chk
        chk = QCheckBox()
        chk.setVisible(False)
        chk.setChecked(bool(getattr(self._book, "ot_auto", False)))
        return chk

    def _on_salary_attr(self, attr: str):
        """任一 spin 改值：写回 book，并对 overtime_base 同步参数页。"""
        if self._loading or not self._book or attr not in self._salary_spins:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        v = self._salary_spins[attr].value()
        setattr(self._book, attr, v)
        if attr == "overtime_base":
            psp = getattr(self, "_param_spins", {}).get("overtime_base")
            if psp is not None and abs(psp.value() - v) > 1e-6:
                psp.blockSignals(True)
                psp.setValue(v)
                psp.blockSignals(False)
        self._pi_touched()

    def _on_ot_auto(self, checked: bool):
        if self._loading or self._book is None:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        self._book.ot_auto = bool(checked)
        self._apply_auto_states()
        self._pi_touched()

    def _on_tax_auto(self, checked: bool):
        if self._loading or self._book is None:
            return
        if getattr(self, "_is_locked", False):
            return  # 锁定只读
        self._book.income_tax_auto = bool(checked)
        self._apply_auto_states()
        self._pi_touched()

    def _apply_auto_states(self):
        """根据 ot_auto / income_tax_auto 启用/停用对应输入框。"""
        if not hasattr(self, "_salary_spins") or self._book is None:
            return
        ot_auto = bool(getattr(self._book, "ot_auto", False))
        for attr in ("workday_ot_hours", "restday_ot_hours", "holiday_ot_hours"):
            sp = self._salary_spins.get(attr)
            if sp is not None:
                sp.setEnabled(not ot_auto)
        if hasattr(self, "_ot_auto_chk") and self._ot_auto_chk.isChecked() != ot_auto:
            self._ot_auto_chk.setChecked(ot_auto)
        tax_auto = bool(getattr(self._book, "income_tax_auto", False))
        sp = self._salary_spins.get("income_tax")
        if sp is not None:
            sp.setEnabled(not tax_auto)
        if hasattr(self, "_ded_card") and self._ded_card.tax_auto.isChecked() != tax_auto:
            self._ded_card.tax_auto.setChecked(tax_auto)

    # ---------------------------------------------------------------------
    # 同步：从 calc 结果刷到 UI
    # ---------------------------------------------------------------------
    def _update_salary_sums(self):
        if not hasattr(self, "pay_items") or self._book is None:
            return
        r = self._last_result
        work = r.counts.work if (r and r.counts) else 0
        if hasattr(self, "pay_items"):
            self.pay_items.refresh_totals(work)

    def _sync_salary_strip(self):
        r = self._last_result
        if r is None or not hasattr(self, "_salary_strip"):
            return
        self._salary_strip.sync(r)
        self._ot_card.sync(r, self._book, auto_write_hours=True)
        self._ded_card.sync(r, self._book)

    def _sync_salary_ui(self):
        if hasattr(self, "_salary_strip"):
            self._update_salary_sums()
            self._sync_salary_strip()

    # ---------------------------------------------------------------------
    # 加班费基数锁态（参数页与薪酬页共享）
    # ---------------------------------------------------------------------
    def _sync_ot_base_locked_ui_salary(self):
        if not hasattr(self, "_salary_spins") or "overtime_base" not in self._salary_spins:
            return
        sp = self._salary_spins["overtime_base"]
        locked = bool(getattr(self, "_ot_base_locked", True))
        sp.setEnabled(not locked)
        if locked:
            sp.setStyleSheet("background:#F5F7FA;color:#667085;")
        else:
            sp.setStyleSheet("")
        if self._book is not None:
            cur = float(getattr(self._book, "overtime_base") or 0.0)
            if abs(sp.value() - cur) > 1e-6:
                sp.blockSignals(True)
                sp.setValue(cur)
                sp.blockSignals(False)
        btn = getattr(self, "_ot_card", None)
        if btn is not None:
            btn.lock_btn.setText("🔒 已锁定 · 冻结当前值" if locked
                                  else "🔓 已解锁 · 可手动修改")

    def _on_copy_pay_items(self):
        """复制当前月工资项 + 固定加班工资 + 大病医疗补助到其它月份。

        复制范围：
          - 工资项列表（pay_items）：金额直接复制；按出勤津贴的目标月会按
            其实际上班天数自动重算，无需手动处理
          - 固定加班工资（fixed_overtime_wage）：随源月金额复制
          - 大病医疗补助（big_disease）：随源月金额复制
        不复制：社保/公积金/最低工资/工时/约定工作天数/税率等参数（这些是
        公司/员工约定，不随月份变动）
        """
        if self._book is None:
            return
        src_y, src_m = self._book.year, self._book.month
        dlg = _CopyPayItemsDialog(self, src_y, src_m)
        if dlg.exec() != QDialog.Accepted:
            return
        tgt_y, tgt_m = dlg.year(), dlg.month()
        if (tgt_y, tgt_m) == (src_y, src_m):
            self._set_status("不能复制到当前月份", False)
            return
        tgt = self.store.load(tgt_y, tgt_m)
        created = False
        if tgt is None:
            tgt = model.create_book(tgt_y, tgt_m, with_common_pay_items=False)
            created = True
        elif tgt.locked:
            # 已锁定的目标月：拒绝覆盖（即使是空白月，锁定就是"不要再碰"的信号）
            QMessageBox.warning(
                self, "目标月份已锁定",
                f"{tgt_y} 年 {tgt_m} 月已锁定，无法复制到该月。\n请先在历史月份列表里右键解锁该月，或换一个目标月。")
            self._set_status("已取消：目标月份已锁定", False)
            return
        elif tgt.pay_items or (tgt.fixed_overtime_wage or 0.0) > 0 or abs((tgt.big_disease or 0.0) - 0.0) > 1e-9:
            ans = QMessageBox.question(
                self, "覆盖确认",
                f"{tgt_y} 年 {tgt_m} 月已有工资项 / 固定加班工资 / 大病医疗补助，确定覆盖吗？")
            if ans != QMessageBox.Yes:
                return
        # 深拷贝工资项（含按出勤津贴的金额，目标月自动按实际上班天数重算）
        copied = [model.PayItem(name=it.name, type=it.type, amount=it.amount)
                  for it in self._book.pay_items]
        tgt.pay_items = copied
        # 同步复制固定加班工资与大病医疗补助（金额直接复制，无需按考勤重算）
        tgt.fixed_overtime_wage = float(self._book.fixed_overtime_wage or 0.0)
        tgt.big_disease = float(self._book.big_disease or 0.0)
        self.store.save(tgt)
        self._refresh_history()
        if created:
            self._set_status(
                f"已新建 {tgt_y} 年 {tgt_m} 月并复制工资项 + 固定加班工资 + 大病医疗补助", True)
        else:
            self._set_status(
                f"已覆盖 {tgt_y} 年 {tgt_m} 月的工资项 + 固定加班工资 + 大病医疗补助", True)

    def _toggle_ot_base_lock_salary(self):
        """薪酬页锁按钮：直接复用参数页的 _toggle_ot_base_lock()。"""
        if getattr(self, "_is_locked", False):
            return  # 锁定只读：不允许再切换 lock 状态
        if not hasattr(self, "_toggle_ot_base_lock"):
            return
        self._toggle_ot_base_lock()
        self._sync_ot_base_locked_ui_salary()

    def _sync_ot_base_value_salary(self, new_val: float):
        if not hasattr(self, "_salary_spins") or "overtime_base" not in self._salary_spins:
            return
        sp = self._salary_spins["overtime_base"]
        if abs(sp.value() - new_val) > 1e-6:
            sp.blockSignals(True)
            sp.setValue(new_val)
            sp.blockSignals(False)


class _CopyPayItemsDialog(QDialog):
    """复制工资项：选择目标年月。"""

    def __init__(self, parent, src_year: int, src_month: int):
        super().__init__(parent)
        self.setWindowTitle("复制工资项")
        self.setMinimumWidth(340)
        self._parent_window = parent

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(18, 14, 18, 14)

        info = QLabel(
            f"将 {src_year} 年 {src_month} 月的「工资项 + 固定加班工资 + 大病医疗补助」复制到：")
        info.setStyleSheet("color:#475467;font-size:13px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # 年月选择
        row = QHBoxLayout()
        row.setSpacing(8)
        self._year = QSpinBox()
        self._year.setRange(2000, 2100)
        self._year.setValue(src_year)
        self._month = QSpinBox()
        self._month.setRange(1, 12)
        self._month.setValue(src_month)
        row.addWidget(QLabel("年份"))
        row.addWidget(self._year, 1)
        row.addSpacing(8)
        row.addWidget(QLabel("月份"))
        row.addWidget(self._month, 1)
        lay.addLayout(row)

        # 目标月锁定状态提示（实时反馈）
        self._target_status = QLabel("")
        self._target_status.setStyleSheet("color:#B54708;font-size:11px;font-weight:600;")
        self._target_status.setWordWrap(True)
        self._target_status.hide()
        lay.addWidget(self._target_status)
        self._year.valueChanged.connect(self._refresh_target_status)
        self._month.valueChanged.connect(self._refresh_target_status)
        self._refresh_target_status()

        # 说明：按出勤津贴的金额直接复制，目标月自动用上班天数重算
        hint = QLabel(
            "提示：按出勤津贴（如伙食/交通）会随目标月实际上班天数自动重算。")
        hint.setStyleSheet("color:#98A2B3;font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        # 让 OK 按钮使用主色
        ok_btn = btns.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setText("复制")
            ok_btn.setObjectName("primary")
        cancel_btn = btns.button(QDialogButtonBox.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("取消")
        lay.addWidget(btns)

    def year(self) -> int:
        return self._year.value()

    def month(self) -> int:
        return self._month.value()

    def _refresh_target_status(self):
        """实时检查目标月状态：已锁定时显示警告。"""
        if not hasattr(self, "_target_status"):
            return
        store = getattr(self._parent_window, "store", None) if self._parent_window else None
        if store is None:
            self._target_status.hide()
            return
        y, m = self.year(), self.month()
        b = store.load(y, m)
        if b is not None and b.locked:
            self._target_status.setText(f"⚠️ {y} 年 {m} 月已锁定，无法复制到该月")
            self._target_status.show()
        else:
            self._target_status.hide()
