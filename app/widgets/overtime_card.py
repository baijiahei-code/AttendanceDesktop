"""加班工资卡片 —— 替代原 SalaryPageMixin._build_ot_card 内联方法。

结构：
* 标题 + 提示
* 固定加班工资 spin
* 三档小时数 spin（各带倍率徽章）
* 加班费基数 spin + 锁按钮
* 三档金额 + 加班小计

公开 signals / attrs：
* :attr:`spins`：所有 NumberSpin 的字典（外部按 attr 读写 book）
* :attr:`ot_totals`：dict[str, QLabel]，每档的金额标签
* :attr:`total`：加班小计标签
* :attr:`lock_btn`：锁按钮（外部监听点击）
* :meth:`sync(r)`：根据 calc 结果刷新金额
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import config, model
from ..ui import NumberSpin


class OvertimeCardWidget(QFrame):
    """加班工资卡片。"""

    def __init__(self, book: model.MonthBook, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._book = book
        self._spins: dict[str, NumberSpin] = {}
        self._ot_vals: dict[str, QLabel] = {}

        # —— 布局容器 ──
        cl = QVBoxLayout(self)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)
        title = QLabel(config.OT_CARD_TITLE)
        title.setObjectName("cardTitle")
        cl.addWidget(title)
        hint = QLabel(config.OVERTIME_TIPS + "；工作日 ×1.5 · 休息日 ×2 · 法定节假日 ×3")
        hint.setObjectName("secHint")
        hint.setWordWrap(True)
        cl.addWidget(hint)

        # —— 各行 ──
        self._label_row(cl, "固定加班工资", "fixed_overtime_wage",
                        decimals=2, step=1.0, suffix="元", badge=None,
                        amount_lab=None)
        for kind in ("workday", "restday", "holiday"):
            display, _mult, fg, bg = config.OVERTIME_RATE[kind]
            attr = f"{kind}_ot_hours"
            self._ot_vals[kind] = QLabel(config.MONEY_FMT.format(0.0))
            self._ot_vals[kind].setObjectName("piTotal")
            label_text = {"workday": "工作日加班",
                          "restday": "休息日加班",
                          "holiday": "法定节假日加班"}[kind]
            self._label_row(cl, label_text, attr,
                            decimals=1, step=0.5, suffix="小时",
                            badge=(display, fg, bg),
                            amount_lab=self._ot_vals[kind])

        # —— 加班费基数 + 锁 ──
        ob_sp = NumberSpin(decimals=2, step=50.0, minimum=0)
        ob_sp.setObjectName("overtimeBase")
        ob_sp.setValue(float(getattr(book, "overtime_base") or 0.0))
        ob_sp.setSuffix(" 元")
        ob_sp.setMinimumWidth(90)
        ob_sp.setMaximumWidth(220)
        self._spins["overtime_base"] = ob_sp
        self._lock_btn = QPushButton("🔒 已锁定 · 冻结当前值")
        self._lock_btn.setObjectName("ghost")
        self._lock_btn.setCursor(Qt.PointingHandCursor)
        self._lock_btn.setToolTip(
            "锁定时自动等于月最低工资；点击解锁可手动改为不同值（与参数页加班费计算基数同步）")
        ob_lay = QHBoxLayout()
        ob_lay.setSpacing(8)
        ob_lab = QLabel("加班费基数（月）")
        ob_lab.setObjectName("fldLabel")
        ob_lay.addWidget(ob_lab)
        ob_lay.addStretch(1)
        ob_lay.addWidget(ob_sp)
        ob_lay.addWidget(self._lock_btn)
        cl.addLayout(ob_lay)
        ob_hint = QLabel("默认与月最低工资标准同步；如需特殊基数，请点击右侧「🔒」解锁后修改")
        ob_hint.setObjectName("secHint")
        ob_hint.setWordWrap(True)
        cl.addWidget(ob_hint)

        # —— 加班小计 ──
        self._total = QLabel("加班工资小计 ¥ 0.00")
        self._total.setObjectName("piTotal")
        cl.addWidget(self._total)

    # ---------------------------------------------------------------------
    # 行构造
    # ---------------------------------------------------------------------
    def _label_row(self, cl: QVBoxLayout, lab: str, attr: str, *,
                   decimals: int, step: float, suffix: str,
                   badge: tuple | None, amount_lab: QLabel | None):
        lay = QHBoxLayout()
        lay.setSpacing(8)
        title = QLabel(lab)
        title.setObjectName("fldLabel")
        lay.addWidget(title)
        lay.addStretch(1)
        if badge is not None:
            text, fg, bg = badge
            bg_lab = QLabel(text)
            bg_lab.setObjectName("otBadge")
            bg_lab.setStyleSheet(
                f"color:{fg};background:{bg};border-radius:7px;"
                f"padding:2px 7px;font-size:10px;font-weight:800;")
            lay.addWidget(bg_lab)
        sp = NumberSpin(decimals=decimals, step=step, minimum=0)
        sp.setValue(float(getattr(self._book, attr) or 0.0))
        if suffix:
            sp.setSuffix(f" {suffix}")
        sp.setMinimumWidth(90)
        sp.setMaximumWidth(220)
        self._spins[attr] = sp
        lay.addWidget(sp)
        if amount_lab is not None:
            lay.addWidget(amount_lab)
        cl.addLayout(lay)

    # ---------------------------------------------------------------------
    # 公开 API
    # ---------------------------------------------------------------------
    @property
    def spins(self) -> dict[str, NumberSpin]:
        return self._spins

    @property
    def total(self) -> QLabel:
        return self._total

    @property
    def lock_btn(self) -> QPushButton:
        return self._lock_btn

    def sync(self, r, b: model.MonthBook | None = None,
             auto_write_hours: bool = False):
        """根据结果刷新三档金额与加班小计。"""
        if r is None:
            return
        self._ot_vals["workday"].setText(
            config.MONEY_FMT.format(r.overtime_wage_workday))
        self._ot_vals["restday"].setText(
            config.MONEY_FMT.format(r.overtime_wage_restday))
        self._ot_vals["holiday"].setText(
            config.MONEY_FMT.format(r.overtime_wage_holiday))
        self._total.setText(f"加班工资小计 ¥ {r.overtime_wage_total:,.2f}")

        # 自动模式下回写到对应的 spin（保持所见即所得）
        if auto_write_hours and b is not None:
            if getattr(b, "ot_auto", False):
                for attr, val in (("workday_ot_hours", r.ot_hours_workday),
                                  ("restday_ot_hours", r.ot_hours_restday),
                                  ("holiday_ot_hours", r.ot_hours_holiday)):
                    sp = self._spins.get(attr)
                    if sp is not None and abs(sp.value() - val) > 1e-6:
                        sp.blockSignals(True)
                        sp.setValue(val)
                        sp.blockSignals(False)
