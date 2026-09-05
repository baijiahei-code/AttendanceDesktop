"""参数页渲染与参数模板（保存/套用）。"""
from __future__ import annotations

import json
import os
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from . import calc, wages
from .ui import NumberSpin
from .widgets import Card


class ParamsPageMixin:
    def _fill_params(self):
        b = self._book
        root = self.params_root
        if not hasattr(self, "_params_lay"):
            self._params_lay = QVBoxLayout(root)
            self._params_lay.setContentsMargins(20, 16, 20, 20)
            self._params_lay.setSpacing(12)
        lay = self._params_lay
        # 清空旧子项
        self._clear_layout(lay)
        # 所有由 Card 承载的卡片（用于统一锁定）
        self._params_cards: list[Card] = []
        # 模板条 / 非卡片内的「修改类」控件（保留单独列表，因为模板条是 QHBoxBar 不是 Card）
        self._params_extra_modify_widgets: list = []

        # —— 🔒 只读模式提示横幅（锁定时才显示）——
        self._lock_banner = QLabel("🔒  当前月份已锁定 · 仅供查看，所有修改操作已屏蔽")
        self._lock_banner.setStyleSheet(
            "background:#FEF4E6;color:#B54708;border:1px solid #FEDF89;"
            "border-radius:8px;padding:8px 14px;font-weight:600;font-size:13px;")
        self._lock_banner.setWordWrap(True)
        self._lock_banner.hide()
        lay.addWidget(self._lock_banner)

        # —— 参数模板条 ——
        tpl = Card(title="", variant="default", margins=(16, 10, 16, 10))
        tpl_inner = QHBoxLayout()
        tpl_inner.setSpacing(10)
        tpl_inner.setContentsMargins(0, 0, 0, 0)
        ttl = QLabel("参数模板")
        ttl.setObjectName("cardTitle")
        self.tpl_combo = QComboBox()
        self.tpl_combo.setMinimumWidth(230)
        save_tpl = QPushButton("存为模板…")
        save_tpl.clicked.connect(self._save_template)
        rename_tpl = QPushButton("重命名")
        rename_tpl.setToolTip("为当前选中模板更改名称")
        rename_tpl.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#475467;border:1px solid #E6E8F0;"
            "border-radius:8px;padding:5px 10px;}"
            "QPushButton:hover{background:#F8FAFC;}")
        rename_tpl.clicked.connect(self._rename_template)
        delete_tpl = QPushButton("删除")
        delete_tpl.setToolTip("删除当前选中模板（不可恢复）")
        delete_tpl.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#D92D20;border:1px solid #FCD0CB;"
            "border-radius:8px;padding:5px 10px;font-weight:600;}"
            "QPushButton:hover{background:#FEF3F2;}")
        delete_tpl.clicked.connect(self._delete_template)
        apply_tpl = QPushButton("套用到本月")
        apply_tpl.setObjectName("primary")
        apply_tpl.clicked.connect(self._apply_template)
        hint_tpl = QLabel("整组参数存为模板，新建月份 / 换人时一键套用")
        hint_tpl.setObjectName("secHint")
        tpl_inner.addWidget(ttl)
        tpl_inner.addWidget(self.tpl_combo)
        tpl_inner.addWidget(save_tpl)
        tpl_inner.addWidget(rename_tpl)
        tpl_inner.addWidget(delete_tpl)
        tpl_inner.addWidget(apply_tpl)
        tpl_inner.addStretch(1)
        tpl_inner.addWidget(hint_tpl)
        tpl.add_layout(tpl_inner)
        lay.addWidget(tpl)
        self._refresh_templates()
        # 模板条的所有"修改类"控件（combo + 4 个按钮）锁定时禁用 —— Card 不追踪，
        # 因为模板条是横向工具条不是内容卡，由独立列表管理。
        self._params_extra_modify_widgets.extend([
            self.tpl_combo, save_tpl, rename_tpl, delete_tpl, apply_tpl,
        ])
        # 模板条本身也是 Card，参与锁定（即便没有可禁用控件，保留一致性）
        self._params_cards.append(tpl)

        # —— 主题卡（对齐高保真原型：社保公积金 / 工资与工时 / 计薪与请假 / 合规判定）——
        self._param_spins = {}
        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(12)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        social_card = self._make_social_card()
        wage_card = self._make_wage_card()
        leave_card = self._make_leave_card()
        note_card = self._make_note_card(b)
        cards.addWidget(social_card, 0, 0)
        cards.addWidget(wage_card, 0, 1)
        cards.addWidget(leave_card, 1, 0)
        cards.addWidget(note_card, 1, 1)
        lay.addLayout(cards)
        lay.addStretch(1)
        # 4 张内容卡 + 1 张工具条卡
        self._params_cards.extend([social_card, wage_card, leave_card, note_card])

    def _set_params_locked(self, locked: bool):
        """锁定只读模式：所有 Card.set_locked 统一禁用内部控件 + 工具条独立禁用。"""
        # 1) 5 张卡片（含模板条）统一禁用内部交互控件
        for card in getattr(self, "_params_cards", []):
            try:
                card.set_locked(locked)
            except Exception:
                pass
        # 2) 模板条额外控件（Card 不追踪，由列表兜底）
        for w in getattr(self, "_params_extra_modify_widgets", []):
            try:
                w.setEnabled(not locked)
            except Exception:
                pass
        # 3) 所有 spin 视觉反馈（背景变灰 + 文本变深灰；锁定月必须 override）
        for sp in (getattr(self, "_param_spins", {}) or {}).values():
            try:
                if locked:
                    sp.setStyleSheet("background:#F5F7FA;color:#667085;")
                else:
                    sp.setStyleSheet("")
            except Exception:
                pass
        # 4) 锁定横幅
        if hasattr(self, "_lock_banner") and self._lock_banner is not None:
            self._lock_banner.setVisible(bool(locked))
        # 5) 月份解锁（非整月只读）后：重放字段级锁定，避免最低工资相关字段被一并解锁
        if not locked:
            self._apply_param_field_locks()

    def _apply_param_field_locks(self):
        """月份解锁后，重放「跟随最低工资」的字段级锁定状态。

        解锁月份 ≠ 解除字段自身锁定：最低工资 / 加班费基数 / 公积金缴费基数
        默认仍处于跟随月最低工资的锁定态（_wage_locked / _ot_base_locked /
        _fund_base_locked）。Card.set_locked(False) 会无条件恢复卡片内所有控件
        可编辑，因此这里把仍处于字段级锁定的输入框重新禁用 + 置灰。
        """
        if getattr(self, "_is_locked", False):
            return
        spins = getattr(self, "_param_spins", {}) or {}
        # 1) 最低工资两行
        wage_locked = bool(getattr(self, "_wage_locked", True))
        for attr in ("min_wage", "parttime_min"):
            sp = spins.get(attr)
            if sp is None:
                continue
            sp.setEnabled(not wage_locked)
            sp.setStyleSheet("background:#F5F7FA;color:#667085;" if wage_locked else "")
        # 2) 加班费计算基数
        ot_locked = bool(getattr(self, "_ot_base_locked", True))
        sp = spins.get("overtime_base")
        if sp is not None:
            sp.setEnabled(not ot_locked)
            sp.setStyleSheet("background:#F5F7FA;color:#667085;" if ot_locked else "")
        # 3) 公积金缴费基数
        fund_locked = bool(getattr(self, "_fund_base_locked", True))
        sp = spins.get("fund_base")
        if sp is not None:
            sp.setEnabled(not fund_locked)
            sp.setStyleSheet("background:#F5F7FA;color:#667085;" if fund_locked else "")

    def _make_social_card(self):
        """社保 / 公积金卡。
        仅 fund_base（公积金缴费基数）默认上锁跟随 min_wage；
        其余字段（社保基数、比例等）保持普通可编辑。"""
        card = Card("社保 / 公积金",
                    hint="五险一金基数与比例（比例填小数，0.105 = 10.5%；公积金基数默认=最低工资，可点 🔓 解锁手动改）")
        b = self._book

        # —— 普通字段：社保缴费基数 + 4 个比例 ——
        plain_fields = [
            ("社保缴费基数", "social_base", 2, 100, "元"),
            ("个人社保比例", "personal_social_rate", 3, 0.001, "", "小数，0.105 = 10.5%"),
            ("公司社保比例", "company_social_rate", 3, 0.001, "", "小数，0.24 = 24%"),
            ("个人公积金比例", "personal_fund_rate", 3, 0.001, "", "小数，0.07 = 7%"),
            ("公司公积金比例", "company_fund_rate", 3, 0.001, "", "小数，0.07 = 7%"),
        ]
        for field in plain_fields:
            lab, attr, dec, step, suf = field[:5]
            tip = field[5] if len(field) > 5 else ""
            box = QVBoxLayout()
            box.setSpacing(3)
            lab_l = QLabel(lab)
            lab_l.setObjectName("fldLabel")
            spin = NumberSpin(decimals=dec, step=step)
            spin.setValue(float(getattr(b, attr) or 0.0))
            if suf:
                spin.setSuffix(f" {suf}")
            spin.valueChanged.connect(lambda _, a=attr: self._on_numeric(a))
            self._param_spins[attr] = spin
            box.addWidget(lab_l)
            box.addWidget(spin)
            if tip:
                t = QLabel(tip)
                t.setObjectName("secHint")
                box.addWidget(t)
            card.add_layout(box)

        # —— 公积金缴费基数：带锁，默认锁定跟随 min_wage ——
        self._fund_base_locked = True
        self._fund_base_lock_btn = QPushButton("🔒 已锁定 · 冻结当前值")
        self._fund_base_lock_btn.setCursor(Qt.PointingHandCursor)
        self._fund_base_lock_btn.setObjectName("ghost")
        self._fund_base_lock_btn.setToolTip(
            "锁定时自动等于月最低工资；点击解锁可手动改为不同值")
        self._fund_base_lock_btn.clicked.connect(self._toggle_fund_base_lock)

        box = QVBoxLayout()
        box.setSpacing(3)
        lab_l = QLabel("公积金缴费基数")
        lab_l.setObjectName("fldLabel")
        fund_spin = NumberSpin(decimals=2, step=100)
        # 如果被锁定，立即同步当前 min_wage；否则保留 book 里的值
        fund_init = float(getattr(b, "fund_base") or 0.0)
        if self._fund_base_locked and b is not None:
            mw = float(getattr(b, "min_wage") or 0.0)
            if mw > 0:
                fund_init = mw
                setattr(b, "fund_base", mw)
        fund_spin.setValue(fund_init)
        fund_spin.setSuffix(" 元")
        fund_spin.setEnabled(not self._fund_base_locked)
        if self._fund_base_locked:
            fund_spin.setStyleSheet("background:#F5F7FA;color:#667085;")
        fund_spin.valueChanged.connect(lambda _, a="fund_base": self._on_numeric(a))
        self._param_spins["fund_base"] = fund_spin
        self._fund_base_spin = fund_spin
        box.addWidget(lab_l)
        row = QHBoxLayout()
        row.addWidget(fund_spin, 1)
        row.addWidget(self._fund_base_lock_btn)
        box.addLayout(row)
        tip = QLabel("默认与本地月最低工资同步；如需特殊基数，请点击右侧「🔒」解锁后修改")
        tip.setObjectName("secHint")
        tip.setWordWrap(True)
        box.addWidget(tip)
        card.add_layout(box)
        return card

    def _make_leave_card(self):
        """计薪与请假卡：约定工作天数 + 一键填入「提供正常劳动天数」。"""
        card = Card("计薪与请假",
                    hint="月计薪天数按国家规定固定 21.75 天；缺勤扣款基准：约定工作天数 − 提供正常劳动天数")
        b = self._book

        box = QVBoxLayout()
        box.setSpacing(3)
        lab_l = QLabel("约定工作天数")
        lab_l.setObjectName("fldLabel")

        row = QHBoxLayout()
        row.setSpacing(8)
        spin = NumberSpin(decimals=2, step=0.5)
        spin.setValue(float(getattr(b, "agreed_work_days") or 0.0))
        spin.setSuffix(" 天")
        spin.valueChanged.connect(lambda _, a="agreed_work_days": self._on_numeric(a))
        self._param_spins["agreed_work_days"] = spin

        fill_btn = QPushButton("一键填入提供正常劳动天数")
        fill_btn.setToolTip("按当前考勤统计，自动把「提供正常劳动天数」填入约定工作天数")
        fill_btn.setCursor(Qt.PointingHandCursor)
        fill_btn.setObjectName("ghost")
        fill_btn.clicked.connect(self._on_fill_agreed_work_days)

        row.addWidget(spin, 1)
        row.addWidget(fill_btn)
        box.addWidget(lab_l)
        box.addLayout(row)
        card.add_layout(box)
        self._fill_agreed_btn = fill_btn  # 锁定时禁用
        return card

    def _make_note_card(self, b):
        """备注 / 姓名卡。"""
        card = Card("备注 / 姓名", hint="用于区分历史月份")
        note = QLineEdit(b.note)
        note.setPlaceholderText("例如：张三 · 工资核算")
        note.textChanged.connect(self._on_note)
        card.add_widget(note)
        self._note_edit = note  # 锁定时禁用
        return card

    def _make_wage_card(self):
        """工资与工时标准卡：省份+地区级联，API 可用时自动填最低工资。"""
        card = Card("工资与工时标准",
                    hint="选择工作地，点击\"获取最低工资\"按钮填入（优先 API，失败用本地官方表）")

        # —— API 配置提示行 ——
        apis = self.store.load_settings()
        api_url = apis.get("api_url", "")
        if api_url:
            model = apis.get("api_model") or wages.DEFAULT_API_MODEL
            api_row = QLabel(f"✅ API 已连接：{api_url} · 模型 {model}")
            api_row.setObjectName("secHint")
        else:
            api_row = QLabel("⚠️ 未配置最低工资 API，选地区后需手动输入")
            api_row.setObjectName("secHint")
        api_row.setWordWrap(True)
        card.add_widget(api_row)
        self._api_hint_label = api_row  # 保存引用供刷新

        api_btn = QPushButton("⚙️ API 设置")
        api_btn.setObjectName("ghost")
        api_btn.setCursor(Qt.PointingHandCursor)
        api_btn.clicked.connect(self._open_api_settings)
        card.add_widget(api_btn)
        self._api_settings_btn = api_btn  # 锁定时禁用

        # —— 省份 + 地区 级联行 + 获取按钮 ——
        prow = QHBoxLayout()
        prow.setSpacing(8)
        plab = QLabel("工作地")
        plab.setObjectName("fldLabel")
        self._province_combo = QComboBox()
        self._province_combo.setMinimumWidth(120)
        self._province_combo.addItem("请选择省份")
        for p in wages.PROVINCES:
            self._province_combo.addItem(p)
        self._region_combo = QComboBox()
        self._region_combo.setMinimumWidth(150)
        self._region_combo.setEnabled(False)  # 未选省份前禁用
        self._province_combo.currentTextChanged.connect(self._on_province_changed)
        self._region_combo.currentTextChanged.connect(self._on_region_changed)
        fetch_btn = QPushButton("🔄 获取最低工资")
        fetch_btn.setToolTip("按当前年份月份拉取最低工资：优先 API，失败则用本地已录入的官方标准")
        fetch_btn.setCursor(Qt.PointingHandCursor)
        fetch_btn.clicked.connect(self._on_click_fetch_wage)
        prow.addWidget(plab)
        prow.addWidget(self._province_combo, 1)
        prow.addWidget(self._region_combo, 1)
        prow.addWidget(fetch_btn)
        card.add_layout(prow)
        self._fetch_wage_btn = fetch_btn  # 锁定时禁用

        # 从 settings 恢复上次选择；若无则默认 安徽 · 池州
        # 恢复期间用 blockSignals 跳过级联信号（此时卡片状态变量如 _ot_base_locked 尚未创建）
        self._province_combo.blockSignals(True)
        self._region_combo.blockSignals(True)
        saved_p = apis.get("province")
        saved_r = apis.get("region")
        if saved_p and self._province_combo.findText(saved_p) >= 0:
            self._province_combo.setCurrentText(saved_p)
            # 重建地区下拉
            regions = wages.get_regions(saved_p)
            self._region_combo.clear()
            for r in regions:
                self._region_combo.addItem(r)
            self._region_combo.setEnabled(len(regions) > 0)
            if saved_r is not None:
                idx = self._region_combo.findText(saved_r)
                self._region_combo.setCurrentIndex(max(0, idx))
            elif regions:
                self._region_combo.setCurrentIndex(0)
        else:
            # 默认选 安徽 · 池州
            idx_p = self._province_combo.findText("安徽")
            if idx_p >= 0:
                self._province_combo.setCurrentIndex(idx_p)
                regions = wages.get_regions("安徽")
                self._region_combo.clear()
                for r in regions:
                    self._region_combo.addItem(r)
                self._region_combo.setEnabled(True)
                idx_r = self._region_combo.findText("池州")
                self._region_combo.setCurrentIndex(max(0, idx_r))
        self._province_combo.blockSignals(False)
        self._region_combo.blockSignals(False)

        # —— 最低工资两行（默认锁定；API 成功填充前值为 model 默认 2170/22.0）——
        self._wage_locked = True
        self._wage_lock_btn = QPushButton("🔒 已锁定 · 冻结当前值")
        self._wage_lock_btn.setCursor(Qt.PointingHandCursor)
        self._wage_lock_btn.setObjectName("ghost")
        self._wage_lock_btn.setToolTip("锁定时保持 API 自动填充值；点击解锁可手动修改")
        self._wage_lock_btn.clicked.connect(self._toggle_wage_lock)

        self._min_wage_spin = None
        for attr, label, dec, step, suf in [
            ("min_wage", "月最低工资", 2, 1, "元"),
            ("parttime_min", "非全日制小时最低工资", 2, 1, "元/时"),
        ]:
            box = QVBoxLayout()
            box.setSpacing(3)
            lab_l = QLabel(label)
            lab_l.setObjectName("fldLabel")
            spin = NumberSpin(decimals=dec, step=step)
            spin.setValue(float(getattr(self._book, attr) or 0.0))
            spin.setSuffix(f" {suf}")
            spin.setEnabled(not self._wage_locked)
            if self._wage_locked:
                spin.setStyleSheet("background:#F5F7FA;color:#667085;")
            if attr == "min_wage":
                spin.valueChanged.connect(lambda v, a=attr: (
                    self._on_numeric(a), self._sync_ot_base_with_min_wage(v),
                    self._sync_fund_base_with_min_wage(v)))
                self._min_wage_spin = spin
            else:
                spin.valueChanged.connect(lambda _, a=attr: self._on_numeric(a))
            self._param_spins[attr] = spin
            box.addWidget(lab_l)
            row = QHBoxLayout()
            row.addWidget(spin, 1)
            if attr == "min_wage":
                row.addWidget(self._wage_lock_btn)
            box.addLayout(row)
            card.add_layout(box)

        # —— 加班费计算基数（独立锁，默认锁定=最低工资）——
        self._ot_base_locked = True
        self._ot_base_lock_btn = QPushButton("🔒 已锁定 · 冻结当前值")
        self._ot_base_lock_btn.setCursor(Qt.PointingHandCursor)
        self._ot_base_lock_btn.setObjectName("ghost")
        self._ot_base_lock_btn.setToolTip("锁定时自动等于月最低工资；点击解锁可手动改为不同值")
        self._ot_base_lock_btn.clicked.connect(self._toggle_ot_base_lock)

        box = QVBoxLayout()
        box.setSpacing(3)
        lab_l = QLabel("加班费计算基数")
        lab_l.setObjectName("fldLabel")
        ot_spin = NumberSpin(decimals=2, step=1)
        ot_init = float(getattr(self._book, "overtime_base") or 0.0)
        # 锁态初始化：如果已有有效值 min_wage，则立即跟随
        if self._ot_base_locked and self._book is not None:
            mw = float(getattr(self._book, "min_wage") or 0.0)
            if mw > 0:
                ot_init = mw
                setattr(self._book, "overtime_base", mw)
        ot_spin.setValue(ot_init)
        ot_spin.setSuffix(" 元")
        ot_spin.setEnabled(not self._ot_base_locked)
        if self._ot_base_locked:
            ot_spin.setStyleSheet("background:#F5F7FA;color:#667085;")
        ot_spin.valueChanged.connect(lambda _, a="overtime_base": self._on_numeric(a))
        self._param_spins["overtime_base"] = ot_spin
        self._ot_base_spin = ot_spin
        box.addWidget(lab_l)
        row = QHBoxLayout()
        row.addWidget(ot_spin, 1)
        row.addWidget(self._ot_base_lock_btn)
        box.addLayout(row)
        tip = QLabel("默认与本地月最低工资同步；如需特殊基数，请点击右侧「🔒」解锁后修改")
        tip.setObjectName("secHint")
        tip.setWordWrap(True)
        box.addWidget(tip)
        card.add_layout(box)

        # —— 其余字段（始终可编辑）——
        for lab, attr, dec, step, suf in [
            ("每日工时", "hours_per_day", 2, 0.5, "小时"),
        ]:
            box = QVBoxLayout()
            box.setSpacing(3)
            lab_l = QLabel(lab)
            lab_l.setObjectName("fldLabel")
            spin = NumberSpin(decimals=dec, step=step)
            spin.setValue(float(getattr(self._book, attr) or 0.0))
            if suf:
                spin.setSuffix(f" {suf}")
            spin.valueChanged.connect(lambda _, a=attr: self._on_numeric(a))
            self._param_spins[attr] = spin
            box.addWidget(lab_l)
            box.addWidget(spin)
            card.add_layout(box)

        # 初始化：如果已有 min_wage 且 overtime_base 仍锁定，同步一下
        if self._ot_base_locked and self._min_wage_spin is not None:
            self._sync_ot_base_with_min_wage(self._min_wage_spin.value())

        # 初始化完成：按已选的省+区自动填入本地表数值（作为默认值）
        default_p = self._province_combo.currentText() if hasattr(self, "_province_combo") else ""
        default_r = self._region_combo.currentText() if hasattr(self, "_region_combo") else ""
        if default_p and default_p != "请选择省份" and default_r:
            self._apply_region_local(default_p, default_r)

        return card

    def _on_fill_agreed_work_days(self):
        """点击「一键填入提供正常劳动天数」：用 calc 统计出的 normal_labor_days 填充。"""
        if self._loading or not self._book:
            return
        if getattr(self, "_is_locked", False):
            return
        try:
            r = self._last_result if self._last_result is not None else calc.compute(self._book)
            normal_days = float(r.counts.normal_labor_days or 0.0)
        except Exception as ex:
            self._set_status(f"统计提供正常劳动天数失败：{ex}", False)
            return
        spin = self._param_spins.get("agreed_work_days")
        if spin is None:
            return
        spin.blockSignals(True)
        spin.setValue(normal_days)
        spin.blockSignals(False)
        setattr(self._book, "agreed_work_days", normal_days)
        self._changed()
        self._set_status(f"已按考勤填入约定工作天数：{normal_days:g} 天", True)

    def _on_click_fetch_wage(self):
        """用户点击「🔄 获取最低工资」按钮：优先调 API（若配置），失败 fallback 本地。"""
        if getattr(self, "_is_locked", False):
            return
        province = self._province_combo.currentText() if hasattr(self, "_province_combo") else ""
        region = self._region_combo.currentText() if hasattr(self, "_region_combo") else ""
        if not province or province == "请选择省份" or not region:
            self._set_status("请先选择省份和地区", False)
            return
        self._apply_region(province, region)  # → wages.fetch：先 API 后本地

    def _apply_region_local(self, province: str, region: str):
        """只从本地静态表取值填入（切省/区、初始化时使用），不调 API。"""
        if self._book is None:
            return
        local = wages.get(province, region)
        if local is None:
            self._set_status(f"{province} · {region} 暂无本地数据，请手动输入或点击获取按钮", False)
            return
        monthly, hourly = local
        for attr, v in [("min_wage", monthly), ("parttime_min", hourly)]:
            spin = self._param_spins.get(attr)
            if spin is None:
                continue
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            setattr(self._book, attr, v)
        if self._ot_base_locked:
            self._sync_ot_base_with_min_wage(monthly, from_region=True)
        if getattr(self, "_fund_base_locked", False):
            self._sync_fund_base_with_min_wage(monthly)
        self._changed()
        self._set_status(f"已按 {province} · {region} 填入本地官方最低工资标准", True)

    def _open_api_settings(self):
        """弹出 API 设置对话框：服务商模板 + API 地址 + 模型名 + Key + 测试连接。"""
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        settings = self.store.load_settings()
        dlg = QDialog(self)
        dlg.setWindowTitle("最低工资 / 节假日 API 设置")
        dlg.setMinimumWidth(480)
        form = QFormLayout(dlg)

        # OpenAI 兼容服务商模板（不含本地服务；「手动输入」可接任意 https 兼容端点）
        providers = [
            # (显示名, api_base, 默认 model)
            ("Agnes（默认）", "https://apihub.agnes-ai.com/v1", "agnes-2.5-flash"),
            ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
            ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-max"),
            ("Kimi (Moonshot)", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
            ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
            ("硅基流动", "https://api.siliconflow.cn/v1", "Qwen2.5-7B-Instruct"),
            ("火山方舟 (豆包)", "https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-1-32k"),
            ("腾讯混元", "https://api.hunyuan.cloud.tencent.com/v1", "hunyuan-turbos-latest"),
            ("零一万物", "https://api.lingyiwanwu.com/v1", "yi-lightning"),
        ]
        current_url = (settings.get("api_url") or "").rstrip("/")
        current_model = settings.get("api_model") or wages.DEFAULT_API_MODEL

        prov_combo = QComboBox()
        prov_combo.addItem("手动输入", "")
        for name, base, _m in providers:
            prov_combo.addItem(f"{name} · {base}", base)
        # 若已存地址命中某服务商，自动选中它（便于修改 Key/模型）
        matched = next((i for i, (_n, base, _m) in enumerate(providers)
                        if current_url == base.rstrip("/")), -1)
        if matched >= 0:
            prov_combo.setCurrentIndex(matched + 1)
        form.addRow("服务商", prov_combo)

        url_edit = QLineEdit(settings.get("api_url", ""))
        url_edit.setPlaceholderText("https://api.deepseek.com/v1")
        model_edit = QLineEdit(current_model)
        model_edit.setPlaceholderText("如 deepseek-chat / qwen-max / glm-4-plus")
        key_edit = QLineEdit(settings.get("api_key", ""))
        key_edit.setPlaceholderText("可选（云端服务需填 Key）")
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API 地址", url_edit)
        form.addRow("模型名", model_edit)
        form.addRow("API Key", key_edit)

        def _on_provider_changed(idx: int):
            base = prov_combo.itemData(idx)
            if not base:
                return  # 手动输入：不覆盖已有填写
            url_edit.setText(base)
            for _n, _b, m in providers:
                if _b == base:
                    model_edit.setText(m)
                    break

        prov_combo.currentIndexChanged.connect(_on_provider_changed)

        def _run_test():
            url_text = url_edit.text().strip()
            if not url_text:
                QMessageBox.warning(dlg, "测试连接", "请先填写 API 地址")
                return
            ok, msg = wages.test_connection(
                url_text, key_edit.text().strip(),
                api_model=model_edit.text().strip() or None)
            if ok:
                QMessageBox.information(dlg, "测试连接", msg)
            else:
                QMessageBox.warning(dlg, "测试连接失败", msg)

        test_btn = QPushButton("测试连接")
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.setToolTip("用当前填写的地址/Key/模型发一条消息验证能否连通")
        test_btn.clicked.connect(_run_test)
        form.addRow("", test_btn)

        hint = QLabel("保存后可在「🔄 获取最低工资」与节假日「API 一键铺」中使用该服务；失败会自动回退本地数据。")
        hint.setObjectName("secHint")
        hint.setWordWrap(True)
        form.addRow("", hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            url_text = url_edit.text().strip()
            # 强制 HTTPS：禁止 http://，避免 Bearer Token 在网络中明文传输
            if url_text and not url_text.lower().startswith("https://"):
                QMessageBox.warning(self, "不安全的 API 地址",
                                    "为保护 API Key 传输安全，API 地址必须以 https:// 开头。\n"
                                    "请改用 HTTPS 地址后重试。")
                return
            settings["api_url"] = url_text
            model_text = model_edit.text().strip()
            if model_text:
                settings["api_model"] = model_text
            else:
                settings.pop("api_model", None)
            key_text = key_edit.text().strip()
            if key_text:
                settings["api_key"] = key_text
            else:
                settings.pop("api_key", None)
            self.store.save_settings(settings)
            self._refresh_api_hint()
            # 配置完 API 不再自动获取，用户点按钮才取

    def _refresh_api_hint(self):
        """刷新 API 状态提示文字。"""
        if not hasattr(self, "_api_hint_label"):
            return
        settings = self.store.load_settings()
        api_url = settings.get("api_url", "")
        if api_url:
            model = settings.get("api_model") or wages.DEFAULT_API_MODEL
            self._api_hint_label.setText(f"✅ API 已连接：{api_url} · 模型 {model}")
        else:
            self._api_hint_label.setText("⚠️ 未配置最低工资 API，选地区后需手动输入")

    def _on_province_changed(self, text: str):
        """省份下拉切换 → 重建地区列表 → 保存 settings → 自动用本地表填最低工资。"""
        if getattr(self, "_is_locked", False):
            return
        settings = self.store.load_settings()
        if text and text != "请选择省份":
            settings["province"] = text
            # 重建地区下拉
            regions = wages.get_regions(text)
            self._region_combo.blockSignals(True)
            self._region_combo.clear()
            for r in regions:
                self._region_combo.addItem(r)
            self._region_combo.setEnabled(len(regions) > 0)
            self._region_combo.blockSignals(False)
            # 默认选第一个地区
            if regions:
                default_r = regions[0]
                settings["region"] = default_r
                self._region_combo.blockSignals(True)
                self._region_combo.setCurrentIndex(0)
                self._region_combo.blockSignals(False)
                self._apply_region_local(text, default_r)
        else:
            settings.pop("province", None)
            settings.pop("region", None)
            self._region_combo.blockSignals(True)
            self._region_combo.clear()
            self._region_combo.setEnabled(False)
            self._region_combo.blockSignals(False)
        self.store.save_settings(settings)

    def _on_region_changed(self, text: str):
        """地区下拉切换 → 保存 settings → 自动用本地表填最低工资。"""
        if getattr(self, "_is_locked", False):
            return
        province = self._province_combo.currentText()
        if not province or province == "请选择省份" or not text:
            return
        settings = self.store.load_settings()
        settings["region"] = text
        self.store.save_settings(settings)
        self._apply_region_local(province, text)

    def _apply_region(self, province: str, region: str):
        """选地区时触发：优先 API 获取，失败则 fallback 本地静态表。
        同时同步 overtime_base（若锁定）。"""
        if self._book is None:
            return
        settings = self.store.load_settings()
        api_url = settings.get("api_url", "")
        api_key = settings.get("api_key", "")
        api_model = settings.get("api_model") or None
        # fetch 内部先试 API，失败自动 fallback 本地静态表
        data = wages.fetch(api_url, api_key, self._book.year, self._book.month,
                           province, region, api_model=api_model)
        if data is None:
            self._set_status(f"已选择 {province} · {region}，但未获最低工资数据，需手动输入", False)
            return
        source = data.get("source", "?")
        monthly = float(data.get("min_wage") or 0)
        hourly = float(data.get("parttime_min") or 0)
        for attr, v in [("min_wage", monthly), ("parttime_min", hourly)]:
            spin = self._param_spins.get(attr)
            if spin is None:
                continue
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            setattr(self._book, attr, v)
        if self._ot_base_locked:
            self._sync_ot_base_with_min_wage(monthly, from_region=True)
        if getattr(self, "_fund_base_locked", False):
            self._sync_fund_base_with_min_wage(monthly)
        self._changed()
        tag = "API" if source == "api" else "本地"
        self._set_status(f"已按 {province} · {region}（{self._book.year}-{self._book.month:02d}）拉取最低工资 · {tag}", True)

    def _sync_ot_base_with_min_wage(self, min_wage_val: float, from_region: bool = False):
        """overtime_base 锁定时跟随 min_wage 值更新。
        from_region=True 时绕过 valueChanged 递归（调用方已 blockSignals 过 min_wage）。"""
        ot_spin = self._param_spins.get("overtime_base")
        if ot_spin is None or not self._ot_base_locked:
            return
        ot_spin.blockSignals(True)
        ot_spin.setValue(min_wage_val)
        ot_spin.blockSignals(False)
        setattr(self._book, "overtime_base", min_wage_val)
        # 同步到薪酬构成页加班费基数 spin
        if hasattr(self, "_sync_ot_base_value_salary"):
            self._sync_ot_base_value_salary(min_wage_val)

    def _toggle_ot_base_lock(self):
        """锁定 / 解锁加班费计算基数。
        重锁时仅冻结用户值（禁用编辑），不立即用 min_wage 覆盖；
        之后若 min_wage 变化，锁定态仍会跟随同步。"""
        if getattr(self, "_is_locked", False):
            return
        self._ot_base_locked = not self._ot_base_locked
        ot_spin = self._param_spins.get("overtime_base")
        if ot_spin is not None:
            ot_spin.setEnabled(not self._ot_base_locked)
            if self._ot_base_locked:
                ot_spin.setStyleSheet("background:#F5F7FA;color:#667085;")
            else:
                ot_spin.setStyleSheet("")
        if self._ot_base_locked:
            self._ot_base_lock_btn.setText("🔒 已锁定 · 冻结当前值")
            self._set_status("已锁定：加班费计算基数保持当前值（后续最低工资变化会同步）", True)
        else:
            self._ot_base_lock_btn.setText("🔓 已解锁 · 可手动修改")
            self._set_status("已解锁：可手动设置加班费计算基数", True)
        # 广播锁态变化到薪酬构成页
        if hasattr(self, "_sync_ot_base_locked_ui_salary"):
            self._sync_ot_base_locked_ui_salary()

    def _sync_fund_base_with_min_wage(self, min_wage_val: float):
        """公积金缴费基数锁定时跟随 min_wage 更新（spin + book 同步）。"""
        fund_spin = getattr(self, "_fund_base_spin", None)
        locked = getattr(self, "_fund_base_locked", False)
        if fund_spin is None or not locked or self._book is None:
            return
        fund_spin.blockSignals(True)
        fund_spin.setValue(min_wage_val)
        fund_spin.blockSignals(False)
        setattr(self._book, "fund_base", min_wage_val)

    def _toggle_fund_base_lock(self):
        """锁定 / 解锁公积金缴费基数。
        重锁时仅冻结用户值（禁用编辑），不立即用 min_wage 覆盖；
        之后若 min_wage 变化，锁定态仍会跟随同步。"""
        if getattr(self, "_is_locked", False):
            return
        self._fund_base_locked = not getattr(self, "_fund_base_locked", True)
        fund_spin = getattr(self, "_fund_base_spin", None)
        if fund_spin is not None:
            fund_spin.setEnabled(not self._fund_base_locked)
            if self._fund_base_locked:
                fund_spin.setStyleSheet("background:#F5F7FA;color:#667085;")
            else:
                fund_spin.setStyleSheet("")
        btn = getattr(self, "_fund_base_lock_btn", None)
        if btn is not None:
            if self._fund_base_locked:
                btn.setText("🔒 已锁定 · 冻结当前值")
                self._set_status("已锁定：公积金缴费基数保持当前值（后续最低工资变化会同步）", True)
            else:
                btn.setText("🔓 已解锁 · 可手动修改")
                self._set_status("已解锁：可手动设置公积金缴费基数", True)

    def _toggle_wage_lock(self):
        """锁定 / 解锁最低工资输入。
        重锁时仅冻结用户值（禁用编辑），不立即重拉省份自动值；
        之后点"获取最低工资"或切换地区时，锁定态仍会同步更新。"""
        if getattr(self, "_is_locked", False):
            return
        self._wage_locked = not self._wage_locked
        for attr in ("min_wage", "parttime_min"):
            spin = self._param_spins.get(attr)
            if spin is not None:
                spin.setEnabled(not self._wage_locked)
                if self._wage_locked:
                    spin.setStyleSheet("background:#F5F7FA;color:#667085;")
                else:
                    spin.setStyleSheet("")
        if self._wage_locked:
            self._wage_lock_btn.setText("🔒 已锁定 · 冻结当前值")
            self._set_status("已锁定：最低工资保持当前值（后续获取最低工资/切换地区时会同步）", True)
        else:
            self._wage_lock_btn.setText("🔓 已解锁 · 可手动修改")
            self._set_status("已解锁：可手动修改最低工资标准", True)

    # 合规判定相关 UI 已彻底移除，保留后台逻辑在计算引擎中（如需要，Overview/Report 会展示结果）

    def _load_templates(self) -> list:
        try:
            with open(self._tpl_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            out = data.get("templates") or []
            return [t for t in out if isinstance(t, dict)]
        except FileNotFoundError:
            return []  # 首次使用尚无模板文件，属正常
        except Exception:
            traceback.print_exc()  # 文件损坏/权限异常时保留可见线索
            return []

    def _save_templates(self, tpls) -> bool:
        try:
            os.makedirs(self.store.dir, exist_ok=True)
            with open(self._tpl_path(), "w", encoding="utf-8") as f:
                json.dump({"templates": tpls}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _refresh_templates(self):
        if not hasattr(self, "tpl_combo"):
            return
        cur = self.tpl_combo.currentText()
        self.tpl_combo.clear()
        for t in self._load_templates():
            self.tpl_combo.addItem(t.get("name") or "未命名模板")
        if self.tpl_combo.count() == 0:
            self.tpl_combo.addItem("（暂无已存模板）")
        idx = self.tpl_combo.findText(cur)
        if idx >= 0:
            self.tpl_combo.setCurrentIndex(idx)

    def _collect_params(self) -> dict:
        out = {}
        if hasattr(self, "_param_spins"):
            for attr, spin in self._param_spins.items():
                out[attr] = spin.value()
        if self._book is not None:
            out["note"] = self._book.note
        return out

    def _save_template(self):
        if not self._book:
            return
        name, ok = QInputDialog.getText(
            self, "保存参数模板", "模板名称：",
            text=f"{self._book.year}-{self._book.month:02d} 参数")
        if not ok or not name.strip():
            return
        name = name.strip()
        tpls = self._load_templates()
        for t in tpls:
            if (t.get("name") or "") == name:
                t["params"] = self._collect_params()
                if not self._save_templates(tpls):
                    self._set_status("模板保存失败，请检查数据目录权限", False)
                    return
                self._refresh_templates()
                self._set_status(f"模板已更新：{name}", True)
                return
        tpls.append({"name": name, "params": self._collect_params()})
        if not self._save_templates(tpls):
            self._set_status("模板保存失败，请检查数据目录权限", False)
            return
        self._refresh_templates()
        self._set_status(f"模板已保存：{name}", True)

    def _apply_template(self):
        if not self._book:
            return
        if self._book.locked:
            QMessageBox.warning(
                self, "月份已锁定",
                f"{self._book.year} 年 {self._book.month} 月已锁定，无法套用模板。\n请先在月份按钮旁点击 🔓 解锁后再操作。")
            self._set_status("已取消：月份已锁定", False)
            return
        name = self.tpl_combo.currentText()
        if not name or name.startswith("（暂无"):
            self._set_status("还没有已存模板", False)
            return
        for t in self._load_templates():
            if (t.get("name") or "") == name:
                p = t.get("params") or {}
                self._loading = True
                if hasattr(self, "_param_spins"):
                    for attr, spin in self._param_spins.items():
                        if attr in p:
                            try:
                                v = float(p[attr])
                            except Exception:
                                v = spin.value()
                            spin.setValue(v)
                            setattr(self._book, attr, v)
                if "note" in p:
                    self._book.note = str(p.get("note") or "")
                self._loading = False
                self._changed()
                self._set_status(f"已套用模板：{name}", True)
                return
        self._set_status("模板不存在", False)

    def _rename_template(self):
        """重命名下拉框里当前选中的模板。"""
        if not hasattr(self, "tpl_combo"):
            return
        old_name = self.tpl_combo.currentText()
        if not old_name or old_name.startswith("（暂无"):
            self._set_status("还没有可重命名的模板", False)
            return
        new_name, ok = QInputDialog.getText(
            self, "重命名参数模板", "新模板名称：", text=old_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == old_name:
            return
        tpls = self._load_templates()
        if any((t.get("name") or "") == new_name for t in tpls):
            self._set_status(f"已存在同名模板：{new_name}", False)
            return
        for t in tpls:
            if (t.get("name") or "") == old_name:
                t["name"] = new_name
                break
        if not self._save_templates(tpls):
            self._set_status("重命名失败，请检查数据目录权限", False)
            return
        self._refresh_templates()
        self._set_status(f"模板已重命名：{old_name} → {new_name}", True)

    def _delete_template(self):
        """删除下拉框里当前选中的模板，二次确认。"""
        if not hasattr(self, "tpl_combo"):
            return
        name = self.tpl_combo.currentText()
        if not name or name.startswith("（暂无"):
            self._set_status("还没有可删除的模板", False)
            return
        ans = QMessageBox.question(
            self, "删除参数模板",
            f"确定要删除模板「{name}」吗？\n删除后无法恢复。")
        if ans != QMessageBox.Yes:
            return
        tpls = self._load_templates()
        before = len(tpls)
        tpls = [t for t in tpls if (t.get("name") or "") != name]
        if len(tpls) == before:
            self._set_status(f"模板不存在：{name}", False)
            return
        if not self._save_templates(tpls):
            self._set_status("删除失败，请检查数据目录权限", False)
            return
        self._refresh_templates()
        self._set_status(f"模板已删除：{name}", True)
