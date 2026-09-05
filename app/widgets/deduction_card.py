"""个人扣除卡片 —— 替代原 SalaryPageMixin._build_ded_card 内联方法。

结构：
* 标题 + 提示
* 自动个税 checkbox
* 个人社保 / 公积金（自动计算显示）
* 大病医疗补助 spin
* 个人所得税 spin
* 扣除合计

公开 attrs：spins, total, tax_auto
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout,
)

from .. import config, model
from ..ui import NumberSpin


class DeductionCardWidget(QFrame):
    """个人扣除卡片。"""

    def __init__(self, book: model.MonthBook, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._book = book
        self._spins: dict[str, NumberSpin] = {}

        cl = QVBoxLayout(self)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)
        title = QLabel(config.DED_CARD_TITLE)
        title.setObjectName("cardTitle")
        cl.addWidget(title)
        hint = QLabel("社保 / 公积金 = 基数 × 比例（自动）；基数与比例在「参数」页设置")
        hint.setObjectName("secHint")
        hint.setWordWrap(True)
        cl.addWidget(hint)

        self.tax_auto = QCheckBox("自动计算个税（月度预扣率表）")
        self.tax_auto.setObjectName("taxAuto")
        self.tax_auto.setCursor(Qt.PointingHandCursor)
        self.tax_auto.setToolTip(
            "按月度税率表自动预扣个税：\n"
            "计税基数 = 应发工资 − 5000（起征点）− 个人社保 − 个人公积金。\n"
            "不含专项附加扣除，需要精确申报时取消勾选手填。")
        self.tax_auto.setChecked(bool(getattr(book, "income_tax_auto", False)))
        cl.addWidget(self.tax_auto)

        # 信息行（仅显示）
        self._ps_social = QLabel(config.MONEY_FMT.format(0.0))
        self._ps_fund = QLabel(config.MONEY_FMT.format(0.0))
        self._info(cl, "个人社保（自动）", self._ps_social)
        self._info(cl, "个人公积金（自动）", self._ps_fund)

        self._spin(cl, "大病医疗补助（元）", "big_disease")
        self._spin(cl, "个人所得税（元）", "income_tax")

        self._total = QLabel("个人扣除合计 - ¥ 0.00")
        self._total.setObjectName("piTotal")
        cl.addWidget(self._total)

    # ---------------------------------------------------------------------
    def _info(self, cl: QVBoxLayout, lab: str, val_lab: QLabel):
        lay = QHBoxLayout()
        lay.setSpacing(8)
        a = QLabel(lab)
        a.setObjectName("fldLabel")
        lay.addWidget(a)
        lay.addStretch(1)
        lay.addWidget(val_lab)
        cl.addLayout(lay)

    def _spin(self, cl: QVBoxLayout, lab: str, attr: str):
        lay = QHBoxLayout()
        lay.setSpacing(8)
        a = QLabel(lab)
        a.setObjectName("fldLabel")
        lay.addWidget(a)
        lay.addStretch(1)
        sp = NumberSpin(decimals=2, step=1.0, minimum=0)
        sp.setValue(float(getattr(self._book, attr) or 0.0))
        sp.setMinimumWidth(90)
        sp.setMaximumWidth(220)
        self._spins[attr] = sp
        lay.addWidget(sp)
        cl.addLayout(lay)

    # ---------------------------------------------------------------------
    @property
    def spins(self) -> dict[str, NumberSpin]:
        return self._spins

    @property
    def total(self) -> QLabel:
        return self._total

    @property
    def ps_social(self) -> QLabel:
        return self._ps_social

    @property
    def ps_fund(self) -> QLabel:
        return self._ps_fund

    def sync(self, r, b: model.MonthBook | None = None):
        """根据结果刷新自动金额与扣除合计。"""
        if r is None:
            return
        if b is not None:
            self._ps_social.setText(
                f"{config.MONEY_FMT.format(r.personal_social)}"
                f"（{b.personal_social_rate:g} × {b.social_base:,.0f}）")
            self._ps_fund.setText(
                f"{config.MONEY_FMT.format(r.personal_fund)}"
                f"（{b.personal_fund_rate:g} × {b.fund_base:,.0f}）")
        self._total.setText(
            f"个人扣除合计 - ¥ {r.personal_deductions_total:,.2f}")

        # 自动个税回写到所得税 spin
        if b is not None and getattr(b, "income_tax_auto", False):
            sp = self._spins.get("income_tax")
            if sp is not None and abs(sp.value() - r.income_tax) > 1e-6:
                sp.blockSignals(True)
                sp.setValue(r.income_tax)
                sp.blockSignals(False)
