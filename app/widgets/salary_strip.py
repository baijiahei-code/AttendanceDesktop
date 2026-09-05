"""薪酬页顶部金额 strip —— 应发合计 / 计入最低工资 / 不计入 / 预计到手。

单一职责：4 列标题 + 4 列数值（受外部 :meth:`sync(r)` 调用刷新）。
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from .. import config


class SalaryStripWidget(QFrame):
    """顶部 4 列金额 strip。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

        self._vals: dict[str, QLabel] = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(22)
        for key, title in config.SALARY_STRIP_TITLES.items():
            col = QVBoxLayout()
            col.setSpacing(0)
            t = QLabel(title)
            t.setObjectName("fldLabel")
            v = QLabel(config.MONEY_FMT.format(0.0))
            v.setObjectName("salaryStripVal")
            col.addWidget(t)
            col.addWidget(v)
            lay.addLayout(col)
            self._vals[key] = v
        lay.addStretch(1)

    def sync(self, r):
        """根据上一次 calc 结果刷新 4 个数值。"""
        if r is None:
            return
        self._vals["gross"].setText(config.MONEY_FMT.format(r.gross_wage))
        self._vals["in"].setText(config.MONEY_FMT.format(r.in_wage_part))
        self._vals["out"].setText(config.MONEY_FMT.format(r.not_in_wage_part))
        self._vals["hand"].setText(config.MONEY_FMT.format(r.take_home))
