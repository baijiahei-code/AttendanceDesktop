"""工作台（总览）页渲染：hero 统计 / 合规。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)


from . import calc
from .widgets import Card


class OverviewPageMixin:
    def _fill_overview(self):
        page = self.overview_page
        if not hasattr(self, "_overview_lay"):
            self._overview_lay = QVBoxLayout(page)
            self._overview_lay.setContentsMargins(20, 16, 20, 20)
            self._overview_lay.setSpacing(12)
        lay = self._overview_lay
        self._clear_layout(lay)
        self.overview_lay = lay
        # 本页没有可编辑控件：锁定只由其它页的 _set_xxx_locked 处理，这里无需登记。

    def _render_overview(self, r):
        if not hasattr(self, "overview_lay"):
            return
        b = self._book
        if b is None:
            return
        c = r.counts
        lay = self.overview_lay
        self._clear_layout(lay)

        # —— 左列（单列占满）——
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)

        # hero 卡（变体 hero）
        hero = Card(title="", hint="", variant="hero")
        hero.setMinimumHeight(116)
        hb = hero.body_layout()
        t1 = QLabel(f"实际到手工资 · {b.year} 年 {b.month} 月")
        t1.setStyleSheet("color:rgba(255,255,255,200);font-size:12px;")
        tv = QLabel(f"¥ {r.take_home:,.2f}")
        tv.setObjectName("heroValue")
        tv.setStyleSheet("color:#FFFFFF;font-size:32px;font-weight:800;")
        ts = QLabel(f"应发 ¥ {r.gross_wage:,.2f} · 个人扣除 ¥ {r.personal_deductions_total:,.2f}"
                    f" · 请假扣 ¥ {r.leave_deduction_total:,.2f}")
        ts.setStyleSheet("color:rgba(255,255,255,180);font-size:12px;")
        hb.addWidget(t1)
        hb.addWidget(tv)
        hb.addWidget(ts)
        ll.addWidget(hero)

        # 4 个 stat 卡
        stats = QHBoxLayout()
        stats.setSpacing(8)
        for sc in (
            self._stat_card("应发工资合计", f"¥ {r.gross_wage:,.2f}"),
            self._stat_card("公司总成本",
                            f"¥ {r.gross_wage + r.company_social + r.company_fund:,.2f}"),
            self._stat_card("提供正常劳动", f"{c.normal_labor_days} 天"),
            self._stat_card("加班 / 请假",
                            f"{r.total_daily_ot_hours:,.1f}h / {r.daily_leave_hours:,.1f}h"),
        ):
            stats.addWidget(sc)
        ll.addLayout(stats)

        cols = QHBoxLayout()
        cols.setSpacing(12)
        cols.addWidget(self._build_compliance_card(r, b), 1)
        cols.addWidget(self._build_company_cost_card(r), 0)
        ll.addLayout(cols)

        lay.addWidget(left, 1)
        lay.addStretch(1)

    def _build_compliance_card(self, r, b):
        card = Card(title="合规判定", variant="default")
        body = card.body_layout()

        min_ok = r.min_wage_ok   # 判定口径唯一真相在 calc（不要在这里重算）
        wage_detail = (
            f"¥ {r.wage_components_total:,.2f} {'≥' if min_ok else '<'} "
            f"¥ {b.min_wage:,.2f}（月最低工资）"
        )

        c = r.counts
        work_time_parts = [
            f"月工时 {r.monthly_work_hours:,.1f}h/{calc.MAX_MONTHLY_WORK_HOURS:g}h",
            f"月加班 {r.total_daily_ot_hours:,.1f}h/{calc.MAX_MONTHLY_OVERTIME_HOURS:g}h",
            f"上班 {c.work} 天/{calc.MAX_MONTHLY_WORK_DAYS} 天",
        ]
        if r.daily_ot_over3_days > 0:
            work_time_parts.append(
                f"{r.daily_ot_over3_days} 天单日加班>{calc.MAX_DAILY_OVERTIME_H:g}h")
        else:
            # 合规：没有任何一天加班 >3h（判定口径见 calc.MAX_DAILY_OVERTIME_H）
            work_time_parts.append(f"单日加班≤{calc.MAX_DAILY_OVERTIME_H:g}h")
        work_time_detail = " · ".join(work_time_parts)

        items = [
            (min_ok, "计入最低工资标准的工资", wage_detail),
            (r.work_time_legal, "工时与加班合规", work_time_detail),
        ]
        for ok, title, detail in items:
            row = QHBoxLayout()
            row.setSpacing(10)
            mark = QLabel("✓" if ok else "!")
            mark.setFixedSize(20, 20)
            mark.setAlignment(Qt.AlignCenter)
            mark.setStyleSheet(
                f"background:{'#12B76A' if ok else '#F79009'};color:#fff;"
                f"border-radius:11px;font-weight:800;font-size:12px;")
            box = QVBoxLayout()
            box.setSpacing(0)
            a = QLabel(title)
            a.setStyleSheet("color:#101828;font-weight:600;font-size:12.5px;")
            d = QLabel(detail)
            d.setStyleSheet("color:#667085;font-size:11px;")
            box.addWidget(a)
            box.addWidget(d)
            row.addWidget(mark)
            row.addLayout(box)
            row.addStretch(1)
            body.addLayout(row)
        return card

    @staticmethod
    def _stat_card(title, value):
        """小统计块（variant=stat）。"""
        card = Card(title="", variant="stat")
        card.setMinimumHeight(86)
        body = card.body_layout()
        t = QLabel(title)
        t.setObjectName("statTitle")
        v = QLabel(value)
        v.setObjectName("statValue")
        body.addWidget(t)
        body.addWidget(v)
        body.addStretch(1)
        return card

    def _build_company_cost_card(self, r):
        card = Card(title="公司每小时成本（仅参考）", variant="default",
                    margins=(12, 10, 12, 10))
        body = card.body_layout()
        if r is None:
            v = QLabel("待核算：录入考勤与工资项后显示")
            v.setStyleSheet("color:#667085;font-size:12px;")
            body.addWidget(v)
            return card
        if r.company_hourly_cost <= 0:
            # 成本 = (应发 + 公司社保 + 公司公积金) ÷ (提供正常劳动天数 × 每日工时)；
            # 分母为 0（没录考勤 / 工时为 0）时 calc 给 0.0 —— 不能显示「¥ 0.00 / h」
            # （看着像“真的不要钱”），这里明确告知原因。
            v = QLabel("待录入考勤 / 工时后显示")
            v.setStyleSheet("font-weight:700;color:#98A2B3;font-size:13px;")
            body.addWidget(v)
            return card
        v = QLabel(f"¥ {r.company_hourly_cost:,.2f} / h  （参考最低 ¥ {self._book.parttime_min:,.2f} / h）")
        v.setStyleSheet("font-weight:700;color:#0F766E;font-size:13px;")
        body.addWidget(v)
        return card
